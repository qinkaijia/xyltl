# NEXT_STEPS

本文记录当前真实联调状态、关键命令和下一步任务优先级。多轮开发后优先回看本文件，再看 `PROJECT_CONTEXT.md` 和 `TODO.md`。

## 当前结论

截至 2026-07-07，真实链路已跑通：

```text
2K0301 真实传感器程序
  -> MQTT Broker on 2K1000LA:1883
  -> 2K1000LA cloud_client.py --sensor-source 2k0301
  -> 电脑 SafeCloud /api/evaluate
  -> final_status JSON
```

本轮已完成 P0-P4 联调：

- P0：2K1000LA 默认 MQTT topic 已统一到真实 301 使用的 `device/board_2k0301/...`。
- P1：完成约 5 分钟连续稳定性测试，2K1000LA 共写出 155 次 `/api/evaluate` 结果。
- P2：`runtime/latest_evaluate_response.json` 已由 Qt HMI `--status-file` 读取烟测通过。
- P3：SafeCloud/Web 命令下发链路已打通，`fan_control`、`buzzer_control`、`alarm_light` 均收到 301 ACK。
- P4：语音链路已复用同一套 MQTT 控制客户端，`打开风扇`、`打开蜂鸣器`、`红灯闪烁` 均完成 LLM -> SafetyGuard -> 301 ACK。

同时已验证反向控制链路：

```text
2K1000LA publish command
  -> 301 device/board_2k0301/command
  -> 301 ACK
  -> device/board_2k0301/ack
```

## 当前网络角色

当前联调网络为手机热点 `192.168.43.0/24` 与 VMware NAT `192.168.242.0/24`：

| 角色 | 当前地址 | 用途 |
| --- | --- | --- |
| Windows 主机 | `192.168.43.5` | SafeCloud、文档、Git、联调控制 |
| Linux VM | `192.168.242.129` | 后续 301/LoongArch 编译与依赖整理 |
| 2K1000LA | `192.168.43.36` | MQTT Broker、HMI、cloud_client、语音/视觉主控 |
| 2K0301/301 | `192.168.43.40` | 传感器采集与执行控制 |

密码、API Key 等敏感信息不要写入仓库文档，按本地记录使用。

## 已验证服务

- Windows SafeCloud：`http://192.168.43.5:8010`
- SafeCloud UDP discovery：`8011`
- 2K1000LA Mosquitto：`0.0.0.0:1883`
- 301 主程序：`/root/xylt_301_main_nopaho`
- 2K1000LA 真实响应输出样例：`runtime/latest_evaluate_response.json`
- Qt HMI 文件数据源：`qt_hmi/build_qmake/display_qt_app --status-file runtime/latest_evaluate_response.json`
- SafeCloud 控制入口：`POST /api/commands`，启用 MQTT 后直接下发到 301 并返回 ACK。
- 语音真实控制入口：`voice_llm_demo/main.py --manual-text ... --mqtt-control --mqtt-host 127.0.0.1`
- 视觉输出文件：`runtime/vision/latest.jpg`、`runtime/vision/vision_state.json`
- 语音触发视觉入口：`runtime/vision/capture_request.json`
- 视觉 SD 卡归档：`/media/xylt/0403-0201/xylt_vision_archive`

2K1000LA 已安装：

- `mosquitto`
- `mosquitto-clients`
- `python3-paho-mqtt`

## 真实 MQTT Topic

301 当前程序实际使用 `device_id=board_2k0301`，因此真实 topic 是：

```text
device/board_2k0301/sensor
device/board_2k0301/heartbeat
device/board_2k0301/ack
device/board_2k0301/error
device/board_2k0301/command
```

注意：早期文档和 2K1000LA 默认配置曾使用 `device/2k0301/...`。当前已统一为真实 301 程序使用的 `device/board_2k0301/...`。

## 已跑通命令

### 电脑端 SafeCloud

```powershell
cd D:\xylt\safecloud
python -m uvicorn app.main:app --host 0.0.0.0 --port 8010
```

发现服务：

```powershell
cd D:\xylt\safecloud
python discovery_responder.py --bind-host 0.0.0.0 --discovery-port 8011 --service-port 8010
```

### 2K1000LA 读取真实 301 数据并调用云端

```bash
cd ~/xylt
PYTHONPATH=. python3 app_2k1000la/cloud_client.py \
  --base-url http://192.168.43.5:8010 \
  --sensor-source 2k0301 \
  --mqtt-host 127.0.0.1 \
  --mqtt-port 1883 \
  --mqtt-qos 1 \
  --mqtt-sensor-topic device/board_2k0301/sensor \
  --mqtt-heartbeat-topic device/board_2k0301/heartbeat \
  --mqtt-ack-topic device/board_2k0301/ack \
  --mqtt-error-topic device/board_2k0301/error \
  --mqtt-command-topic device/board_2k0301/command \
  --mqtt-first-timeout 18 \
  --mqtt-stale-after 8 \
  --output-file runtime/latest_evaluate_response.json \
  --include-debug \
  --timeout 20
```

连续稳定性测试命令：

```bash
cd ~/xylt
env PYTHONUNBUFFERED=1 PYTHONPATH=. python3 app_2k1000la/cloud_client.py \
  --base-url http://192.168.43.5:8010 \
  --sensor-source 2k0301 \
  --mqtt-host 127.0.0.1 \
  --mqtt-port 1883 \
  --output-file runtime/latest_evaluate_response.json \
  --include-debug \
  --loop \
  --interval 2 \
  --timeout 20
```

### 301 手动运行主程序

```bash
/root/xylt_301_main_nopaho
```

短时测试可用：

```bash
timeout -s INT 12 /root/xylt_301_main_nopaho
```

### 2K1000LA 抓 MQTT

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -q 1 -v -t 'device/#'
```

### 2K1000LA 下发测试命令

```bash
mosquitto_pub -h 127.0.0.1 -p 1883 -q 1 \
  -t device/board_2k0301/command \
  -m '{"type":"command","seq":2001,"command":"fan_control","params":{"state":"on","speed":60,"duration_ms":1000}}'
```

ACK 样例：

```json
{"type":"ack","seq":2001,"ok":true,"message":"fan_control on (未接硬件,命令已记录)"}
```

注意：当前 301 命令解析对 JSON 空格比较敏感，云端和语音链路统一使用 compact JSON：

```json
{"type":"command","seq":2001,"command":"fan_control","params":{"state":"on","speed":60,"duration_ms":1000}}
```

不要把命令 payload 改回带空格的格式，否则 301 可能解析为未知命令并返回失败 ACK。

### Windows SafeCloud 直接下发命令

启动 SafeCloud 时打开 MQTT 控制：

```powershell
cd D:\xylt
$env:SAFECLOUD_MQTT_CONTROL_ENABLED="1"
$env:SAFECLOUD_2K0301_MQTT_HOST="192.168.43.36"
$env:SAFECLOUD_2K0301_MQTT_PORT="1883"
$env:SAFECLOUD_2K0301_ACK_TIMEOUT="4"
safecloud\.venv\Scripts\python.exe -m uvicorn safecloud.app.main:app --host 0.0.0.0 --port 8010
```

API 验证：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8010/api/commands `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"device_id":"board_2k0301","command_type":"fan_control","command_payload":{"state":"on","speed":60,"duration_ms":1000}}'
```

本轮实测结果：

| 命令 | 结果 |
| --- | --- |
| `fan_control` | `delivery_status=ack_ok`，301 日志 `ACK OK` |
| `buzzer_control` | `delivery_status=ack_ok`，301 日志 `ACK OK` |
| `alarm_light` | `delivery_status=ack_ok`，301 日志 `ACK OK` |

### 2K1000LA 语音链路触发控制

先用 `--manual-text` 跑通语音后半段，避免 ASR 噪声影响判断：

```bash
cd ~/xylt
PYTHONPATH=. python3 voice_llm_demo/main.py \
  --manual-text 打开风扇 \
  --mqtt-control \
  --mqtt-host 127.0.0.1 \
  --mqtt-ack-timeout 5
```

本轮实测通过：

```text
打开风扇   -> FAN_CONTROL    -> 301 ACK 成功
打开蜂鸣器 -> BUZZER_CONTROL -> 301 ACK 成功
红灯闪烁   -> ALARM_LIGHT    -> 301 ACK 成功
```

### 2K1000LA 视觉服务与语音联动

SafeCloud 侧使用火山方舟 Responses API：

```text
DOUBAO_VISION_API_URL=https://ark.cn-beijing.volces.com/api/v3/responses
DOUBAO_VISION_MODEL=doubao-seed-2-0-lite-260428
DOUBAO_VISION_API_TYPE=responses
```

板端视觉服务：

```bash
cd ~/xylt
env PYTHONUNBUFFERED=1 PYTHONPATH=. python3 app_2k1000la/vision_service.py \
  --base-url http://192.168.43.5:8010 \
  --camera-index 0 \
  --mode cloud \
  --output-dir runtime/vision \
  --periodic-upload-seconds 300 \
  --capture-request-file runtime/vision/capture_request.json \
  --archive-dir /media/xylt/0403-0201/xylt_vision_archive \
  --loop \
  --interval 1 \
  --include-debug
```

语音触发抓拍问答：

```bash
cd ~/xylt
PYTHONPATH=. python3 voice_llm_demo/main.py \
  --manual-text 现在穿戴规范吗 \
  --assistant-state-file runtime/voice_assistant_state.json \
  --context-status-file runtime/latest_evaluate_response.json \
  --real-llm \
  --llm-provider doubao \
  --tts-mode baidu
```

回答应同时包含 PPE 判断和 301 环境指标结论。30 秒内重复同类问题默认复用最近视觉结果；“重新拍/再看一下/拍一下”会强制抓拍。

## 已知问题

1. **301 传感器提示**：运行时偶发 `SGP30 写入湿度补偿失败`、`ADC_CH0 timeout`、`I2C 写入 3 字节失败`，但主程序会继续上报 MQTT 数据。
2. **旧轮询进程干扰**：首次稳定性测试发现板端残留 `gas_alarm.json` 轮询进程会覆盖输出文件；已停止旧用户服务并清理残留进程。
3. **systemd 暂缓启用**：当前阶段手动联调更直观，正式开机自启动放到最后统一编排。
4. **301 稳定性仍需复测**：首次脏环境测试期间 301 曾重启一次；清理旧进程后的 5 分钟测试未复现。
5. **301 残留进程会干扰 ACK**：若 301 上残留多个 `xylt_301_main_nopaho` 进程，需清理到只保留一个实例。BusyBox `ps` 下可用 `ps | grep '[x]ylt_301_main_nopaho'` 检查。
6. **中文命令通过 SSH here-doc 可能乱码**：远程自动测试语音时可用 Unicode 转义，实际终端交互或 ASR 返回正常 UTF-8 文本即可。

## 本轮稳定性结果

测试时间：2026-07-07 约 19:00。

- 301：`/root/xylt_301_main_nopaho` 连续运行到 `timeout -s INT` 正常退出，累计报警次数为 0。
- 2K1000LA：`cloud_client.py --sensor-source 2k0301 --loop --interval 2` 自然结束。
- SafeCloud：持续返回 `debug.client.ok=true`，最终 `base_url=http://192.168.43.5:8010`。
- 结果数量：2K1000LA 日志中共出现 155 条 `evaluate_result`。
- 延迟：尾段请求延迟约 33-55 ms，测试中观测到的常见范围约 31-73 ms。
- 最终 JSON：`runtime/latest_evaluate_response.json`，`device_id=board_2k0301`，`alarm_level=0`，`status_text=正常`，`analysis_mode=rule_fallback`。
- Qt HMI：`QT_QPA_PLATFORM=offscreen timeout 5 ./build_qmake/display_qt_app --compact --geometry 780x450+10+10 --status-file /home/xylt/xylt/runtime/latest_evaluate_response.json` 启动烟测通过；退出码 `124` 为 timeout 主动结束。

## 下一步优先级

### P0 统一 Topic 和默认配置（已完成）

- 已将 2K1000LA 默认 MQTT topic 改为 `device/board_2k0301/...`。
- 已同步更新 `app_2k1000la/README.md`、`docs/integration/*`、测试用例和根目录辅助文档。

### P1 做 5-10 分钟连续稳定性测试（已完成）

- 301 持续运行 `/root/xylt_301_main_nopaho`。
- 2K1000LA 使用 `cloud_client.py --sensor-source 2k0301 --loop`。
- 已确认 MQTT、SafeCloud、输出 JSON 在本轮约 5 分钟测试中持续刷新。

### P2 Qt HMI 接入真实输出文件（已完成）

- 输出已收敛到 `runtime/latest_evaluate_response.json`。
- Qt HMI 可通过 `--status-file` 读取真实 301 温湿度、风险等级、云端状态。

### P3 Web/Qt 增加控制与 ACK 展示（已完成）

- SafeCloud `POST /api/commands` 已支持直接 MQTT 下发到 301。
- Web Dashboard 告警控制页已显示最近一次 ACK、耗时和错误信息。
- 本轮真实验证 `fan_control`、`buzzer_control`、`alarm_light` 均为 `ack_ok`。

### P4 再接语音链路（已完成）

- 语音 demo 已增加 `--mqtt-control`、`--mqtt-host`、`--manual-text`。
- `打开风扇`、`打开蜂鸣器`、`红灯闪烁` 已在 2K1000LA 上走完整控制闭环。

### P5 最后做开机自启动

- 固化 `mosquitto`。
- 固化 `cloud_client.py --loop`。
- 固化 Qt HMI。
- 根据比赛现场网络保留 SafeCloud 自动发现或手动 `SAFECLOUD_BASE_URL`。
