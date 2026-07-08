# 完整系统启动手册

本文用于下次快速启动“基于龙芯双处理器与多 LLM 仲裁的密闭空间智能安全监护仪”整套系统。目标是按步骤恢复：

```text
2K0301/301 传感器采集与执行控制
  -> 2K1000LA Mosquitto MQTT Broker
  -> 2K1000LA 云端桥接 / Qt HMI / 语音 / 视觉
  -> Windows SafeCloud
  -> Web Dashboard
```

原则：只保留一条真实数据链路，不同时启动 mock 轮询和真实 301 程序；API Key、SSH 密码不写入仓库。

## 0. 当前默认地址

当前联调网络记录：

```text
Windows / SafeCloud: 192.168.43.5:8010
2K1000LA:            192.168.43.36
2K0301 / 301:        192.168.43.40
MQTT Broker:         192.168.43.36:1883
Web Dashboard:       http://127.0.0.1:8010/dashboard
```

如果更换手机热点或路由器，这些地址可能变化。先确认 Windows、2K1000LA、301 均在同一局域网，再把下面命令里的 IP 替换成实际地址。

## 1. 启动 Windows SafeCloud

在 Windows PowerShell 中执行：

```powershell
cd D:\xylt\safecloud

$env:SAFECLOUD_MQTT_CONTROL_ENABLED="1"
$env:SAFECLOUD_2K0301_MQTT_HOST="192.168.43.36"
$env:SAFECLOUD_2K0301_MQTT_PORT="1883"
$env:SAFECLOUD_2K0301_ACK_TIMEOUT="4"

Start-Process -FilePath ".\.venv\Scripts\python.exe" -WorkingDirectory "." -WindowStyle Hidden -ArgumentList @("-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8010")
Start-Process -FilePath ".\.venv\Scripts\python.exe" -WorkingDirectory "." -WindowStyle Hidden -ArgumentList @("discovery_responder.py","--bind-host","0.0.0.0","--discovery-port","8011","--service-port","8010")
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8010/health
```

期望返回：

```json
{"status":"ok","service":"SafeCloud"}
```

打开网页：

```text
本机: http://127.0.0.1:8010/dashboard
局域网: http://192.168.43.5:8010/dashboard
```

常用页面：

```text
环境监测: http://127.0.0.1:8010/dashboard#monitor
视觉巡检: http://127.0.0.1:8010/dashboard#vision
告警控制: http://127.0.0.1:8010/dashboard#operations
```

## 2. 启动 2K1000LA

2K1000LA 已部署 systemd 开机自启动。正常情况下开机后只需要检查：

```bash
ssh xylt@192.168.43.36

systemctl is-active mosquitto.service xylt-cloud-client.service xylt-vision.service xylt-hmi.service
systemctl is-enabled mosquitto.service xylt-cloud-client.service xylt-vision.service xylt-hmi.service
```

期望均为：

```text
active
enabled
```

如果需要手动重启 2K1000LA 端服务：

```bash
sudo systemctl restart mosquitto.service
sudo systemctl restart xylt-cloud-client.service xylt-vision.service xylt-hmi.service
```

2K1000LA 服务含义：

| 服务 | 作用 |
| --- | --- |
| `mosquitto.service` | MQTT Broker，监听 `1883` |
| `xylt-cloud-client.service` | 读取 301 MQTT 数据，调用 Windows SafeCloud `/api/evaluate` |
| `xylt-vision.service` | USB 摄像头实时预览、定时/按需抓拍、云端/本地视觉模式 |
| `xylt-hmi.service` | Qt HMI，自动拉起语音助手 |

检查进程：

```bash
ps -eo pid,ppid,etimes,cmd | grep -E '([c]loud_client.py|[v]ision_service.py|[d]isplay_qt_app|[v]oice_llm_demo/main.py|[a]record)' || true
```

期望能看到：

```text
cloud_client.py
vision_service.py
display_qt_app
voice_llm_demo/main.py
arecord
```

如果网络变化，修改 2K1000LA 的 SafeCloud 地址：

```bash
sudo nano /etc/xylt/2k1000la.env
sudo systemctl restart xylt-cloud-client.service xylt-vision.service
```

关键配置项：

```bash
SAFECLOUD_BASE_URL=http://192.168.43.5:8010
```

## 3. 启动 301

301 已部署 systemd 开机自启动。当前真实采集程序为：

```bash
/home/root/main
```

不要同时启动旧程序：

```bash
/root/xylt_301_main_nopaho
```

两者同时运行会向同一 MQTT topic 发布数据，导致 Qt/Web 在线状态和数值跳变。

检查 301 服务：

```bash
ssh root@192.168.43.40

systemctl status xylt-301-main.service
systemctl is-active xylt-301-main.service
ps -eo pid,ppid,etimes,cmd | grep -E '[/]home/root/main|[x]ylt_301_main' || true
```

如果 Windows 不能直接 SSH 到 301，但 2K1000LA 能看到 301，可通过 2K1000LA 跳板：

```bash
ssh -J xylt@192.168.43.36 root@192.168.43.40
```

重启 301 采集服务：

```bash
systemctl restart xylt-301-main.service
journalctl -u xylt-301-main.service --no-pager --lines=40
```

## 4. 验证 301 到 2K1000LA 的 MQTT

在 2K1000LA 上执行：

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -q 1 -C 5 -v -t 'device/board_2k0301/#'
```

期望看到：

```text
device/board_2k0301/sensor ...
device/board_2k0301/heartbeat ...
```

正常 sensor payload 应包含：

```json
{
  "temperature": 27.8,
  "humidity": 48.6,
  "tvoc": 15,
  "eco2": 434,
  "mq3_value": 0.038,
  "flame_detected": false,
  "risk_score": 15
}
```

如果看到：

```text
temperature=-999.0
humidity=-1.0
sensor_online=false
```

说明 MQTT 通信正常，但 301 侧 SHT30/I2C 传感器初始化失败。优先检查 301 的 SHT30 供电、I2C-5、`PIN_50/51` 接线，然后重启 `xylt-301-main.service`。

## 5. 验证 2K1000LA 到 SafeCloud

在 2K1000LA 上查看最终状态文件：

```bash
python3 - <<'PY'
import json
from pathlib import Path
p = Path('/home/xylt/xylt/runtime/latest_evaluate_response.json')
data = json.loads(p.read_text())
fs = data.get('final_status', {})
for key in [
    'timestamp', 'status_text', 'alarm_level', 'sensor_source',
    'sensor_online', 'actuator_online', 'cloud_connected',
    'temperature', 'humidity', 'tvoc', 'eco2',
    'mq3_value', 'flame_detected', 'risk_score', 'reason',
]:
    print(key, fs.get(key))
PY
```

关键期望：

```text
sensor_source 2k0301_mqtt
cloud_connected True
```

如果 `sensor_online=False`，网页会显示传感器离线报警，这是正确保护行为。

## 6. 验证网页

打开：

```text
http://127.0.0.1:8010/dashboard#monitor
```

环境监测页应显示：

```text
温度
湿度
TVOC
eCO2
MQ-3 乙醇
火焰检测
综合风险
```

打开：

```text
http://127.0.0.1:8010/dashboard#vision
```

视觉巡检页应显示：

```text
USB 摄像头关键帧
人员安全评估
云端豆包 / 本地 YOLO / 关闭视觉
```

## 7. 验证命令下发

在 Windows PowerShell 中执行一个安全烟测命令，关闭风扇：

```powershell
$body = @{
  device_id = "board_2k0301"
  command_type = "fan_control"
  command_payload = @{ state = "off" }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri http://127.0.0.1:8010/api/commands -Method Post -ContentType "application/json" -Body $body
```

期望：

```text
delivery_status = ack_ok
transport_target = 192.168.43.36:1883
```

不要用蜂鸣器或报警灯作为常规烟测，以免现场误报警。

## 8. 验证语音助手

Qt HMI 启动后会自动拉起语音助手。检查进程：

```bash
ps -eo pid,ppid,etimes,cmd | grep -E '([v]oice_llm_demo/main.py|[a]record)' || true
```

查看原始日志：

```bash
tail -n 80 /home/xylt/xylt/runtime/voice_assistant_process.log
```

默认唤醒词：

```text
小龙
你好小龙
龙芯助手
小龙在吗
在吗
```

语音链路特性：

- 唤醒后进入约 10 秒连续追问窗口。
- 普通问答使用真实 LLM。
- 视觉问题会触发抓拍，例如“现在穿戴规范吗”“现场有没有安全隐患”。
- 语音状态写入 `runtime/voice_assistant_state.json`，Qt HMI 会显示最近问题、回复和执行结果。

## 9. 验证视觉

视觉服务默认：

- 实时写入 `runtime/vision/live.jpg`
- 抓拍关键帧写入 `runtime/vision/latest.jpg`
- 视觉结果写入 `runtime/vision/vision_state.json`
- 每 5 分钟自动云端检测一次
- 语音或 Qt 手动拍照可触发立即检测

检查文件：

```bash
ls -lh /home/xylt/xylt/runtime/vision/
```

查看视觉状态：

```bash
python3 - <<'PY'
import json
from pathlib import Path
p = Path('/home/xylt/xylt/runtime/vision/vision_state.json')
data = json.loads(p.read_text())
vs = data.get('vision_status', data)
for key in ['timestamp', 'mode', 'backend', 'camera_online', 'person_detected', 'ppe_status', 'summary', 'latency_ms']:
    print(key, vs.get(key))
PY
```

## 10. 常见故障

### 网页打不开

检查 Windows SafeCloud：

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8010
Invoke-RestMethod http://127.0.0.1:8010/health
```

如果端口被旧进程占用，按 PID 停掉旧进程后重新启动 SafeCloud。

### 网页显示 301 离线

在 2K1000LA 上检查 MQTT：

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -q 1 -C 3 -v -t 'device/board_2k0301/#'
```

如果没有任何消息：

- 检查 301 是否连回同一热点。
- 检查 301 IP 是否变化。
- 检查 `xylt-301-main.service` 是否运行。

### Windows 不能 SSH 到 301

有时 Windows 到 301 不通，但 2K1000LA 能看到 301。先在 2K1000LA 上检查：

```bash
ip neigh show
ping -c 2 -W 1 192.168.43.40
```

如果 2K1000LA 可达，可用跳板：

```bash
ssh -J xylt@192.168.43.36 root@192.168.43.40
```

### 温湿度显示“暂无数据”

如果 MQTT 中出现：

```text
temperature=-999.0
humidity=-1.0
sensor_online=false
```

通信是通的，问题在 301 侧传感器。检查：

- SHT30 供电。
- I2C-5 接线。
- `PIN_50/51`。
- 301 日志中的 `SHT30 未检测到传感器`、`I2C 读取 6 字节失败`。

可尝试：

```bash
systemctl restart xylt-301-main.service
journalctl -u xylt-301-main.service --no-pager --lines=60
```

### Web 数值突然跳成假报警

检查 2K1000LA 是否残留旧 mock 用户服务：

```bash
systemctl --user list-units --type=service --all | grep -Ei 'xylt|safecloud|cloud'
systemctl --user disable --now xylt-safecloud-client.service
```

当前真实链路应只保留系统级：

```bash
systemctl status xylt-cloud-client.service
```

### 语音助手退出

Qt HMI 已配置 `VOICE_AUTORESTART=true`，语音子进程异常退出后会自动重启。若没有恢复：

```bash
sudo systemctl restart xylt-hmi.service
tail -n 80 /home/xylt/xylt/runtime/voice_assistant_process.log
```

### 更换网络后

需要同步修改：

1. Windows 启动 SafeCloud 时的 `SAFECLOUD_2K0301_MQTT_HOST`。
2. 2K1000LA `/etc/xylt/2k1000la.env` 中的 `SAFECLOUD_BASE_URL`。
3. 301 程序内或运行环境里的 MQTT Broker 地址，当前应指向 `192.168.43.36:1883`。

## 11. 停止系统

停止 Windows SafeCloud：关闭对应 Python 进程或按端口清理。

停止 2K1000LA 服务：

```bash
sudo systemctl stop xylt-hmi.service xylt-vision.service xylt-cloud-client.service
```

停止 301 服务：

```bash
systemctl stop xylt-301-main.service
```

需要恢复开机自启动时：

```bash
sudo systemctl enable --now xylt-cloud-client.service xylt-vision.service xylt-hmi.service
systemctl enable --now xylt-301-main.service
```

## 12. 启动完成判定

完整系统可认为启动成功，当且仅当：

- SafeCloud `/health` 返回 `ok`。
- 2K1000LA 四个服务均为 `active`。
- 301 `xylt-301-main.service` 为 `active`。
- 2K1000LA 能收到 `device/board_2k0301/sensor` 和 `heartbeat`。
- `runtime/latest_evaluate_response.json` 中 `sensor_source=2k0301_mqtt`。
- Web Dashboard 能显示中文环境指标。
- Qt HMI 显示同一组指标。
- 语音助手进程和 `arecord` 存在。
- 视觉页能显示 `live.jpg` 或最新关键帧。
- `POST /api/commands` 能收到 301 `ack_ok`。
