# app_2k1000la

2K1000LA 主控侧应用目录。当前阶段先提供可在板端运行的 SafeCloud HTTP 客户端，用于联调云端 `/api/evaluate` 和本地超时回退。

## SafeCloud 客户端

文件：`cloud_client.py`

通信协议说明：`docs/integration/2k1000la_safecloud_protocol.md`

功能：

- 读取场景化 mock JSON。
- 支持 `scenario`、`mock`、`2k0301` 三种数据源入口，其中 `2k0301` 通过 MQTT 读取 301 上报数据。
- 自动发现或手动调用 SafeCloud `POST /api/evaluate`。
- 将返回结果写入本地 JSON，供 Qt HMI 使用。
- 请求失败、超时或返回异常时，使用端侧本地阈值规则生成 `local_http_fallback`。
- 可选 `--speak`，把 `final_status.voice_text` 交给 `voice/voice_text_player.py` 播报。
- 可选 `--loop`，作为简易常驻轮询进程运行。

## 数据源模式

`cloud_client.py` 支持三类数据源，云端、HMI 和语音链路保持同一份 `/api/evaluate` payload：

- `--sensor-source scenario`：读取一个场景文件，默认 `tests/scenarios/evaluate/normal.json`。
- `--sensor-source mock`：按正常、温度预警、气体报警、振动报警、传感器离线五类场景循环输出。
- `--sensor-source 2k0301`：订阅本机或指定 Broker 上的 2K0301 MQTT Topic。

依赖安装：

```bash
pip3 install -r app_2k1000la/requirements.txt
```

循环 mock 示例：

```bash
python3 app_2k1000la/cloud_client.py \
  --sensor-source mock \
  --output-file runtime/latest_evaluate_response.json \
  --include-debug \
  --loop \
  --interval 2
```

真实 2K0301 MQTT 示例：

```bash
python3 app_2k1000la/cloud_client.py \
  --sensor-source 2k0301 \
  --mqtt-host 127.0.0.1 \
  --mqtt-port 1883 \
  --output-file runtime/latest_evaluate_response.json \
  --include-debug \
  --loop \
  --interval 1
```

当前 301 侧约定：

- 301 IP：`192.168.43.39`，DHCP 动态获取。
- 2K1000LA IP：当前记录为 `192.168.43.40`，DHCP 动态获取。
- Broker：运行在 2K1000LA，301 连接 `192.168.43.40:1883`，2K1000LA 本地客户端默认连接 `127.0.0.1:1883`。
- 认证：无。
- Topic：`device/2k0301/sensor`、`device/2k0301/heartbeat`、`device/2k0301/ack`、`device/2k0301/error`、`device/2k0301/command`，QoS 1。

2K1000LA 会把 301 上报的 `temperature/humidity/tvoc/eco2/mq3_value/risk_score/flame_detected` 转换为云端 `metrics`。其中 `gas` 取 TVOC、eCO2、MQ-3、`risk_score` 的归一化最大值；`flame_detected=true` 时强制 `gas=1.0`，触发本地/云端高风险判断。

## 自动网络适配

客户端查找 SafeCloud 的优先级：

1. 命令行 `--base-url`
2. 环境变量 `SAFECLOUD_BASE_URL`
3. 上次成功连接缓存 `~/.xylt_safecloud.json`
4. UDP 广播自动发现，默认端口 `8011`
5. 全部失败时走本地规则回退

自动发现用法：

```bash
python3 app_2k1000la/cloud_client.py \
  --sensor-source scenario \
  --scenario-file tests/scenarios/evaluate/temperature_warning.json \
  --output-file runtime/latest_evaluate_response.json \
  --include-debug
```

手动覆盖：

```bash
export SAFECLOUD_BASE_URL=http://192.168.43.5:8010
```

示例：

```bash
python3 app_2k1000la/cloud_client.py \
  --base-url http://192.168.14.20:8000 \
  --sensor-source scenario \
  --scenario-file tests/scenarios/evaluate/temperature_warning.json \
  --output-file runtime/latest_evaluate_response.json \
  --include-debug \
  --speak \
  --tts-mode print
```

常驻轮询：

```bash
python3 app_2k1000la/cloud_client.py \
  --sensor-source mock \
  --output-file runtime/latest_evaluate_response.json \
  --include-debug \
  --loop \
  --interval 2
```

## 接入 systemd 用户服务

板端可用用户级 systemd 托管轮询客户端。安装脚本会根据当前仓库位置生成 service，不需要在仓库里写死绝对路径。

```bash
cd ~/xylt
chmod +x app_2k1000la/scripts/install_safecloud_client_user_service.sh
app_2k1000la/scripts/install_safecloud_client_user_service.sh
```

默认行为：

- 运行 `app_2k1000la/cloud_client.py --loop`。
- 每 2 秒请求一次 SafeCloud `/api/evaluate`。
- 默认使用 `XYLT_SENSOR_SOURCE=mock` 循环模拟数据。
- 输出到 `runtime/latest_evaluate_response.json`，供 Qt HMI 的 `--status-file` 读取。
- 使用 `SAFECLOUD_BASE_URL`、缓存和 UDP 自动发现做网络适配。

配置文件位于：

```bash
~/.config/xylt/safecloud-client.env
```

可调整示例：

```bash
SAFECLOUD_BASE_URL=http://192.168.14.20:8010
XYLT_SENSOR_SOURCE=mock
XYLT_2K0301_MQTT_HOST=127.0.0.1
XYLT_2K0301_MQTT_PORT=1883
XYLT_2K0301_MQTT_QOS=1
XYLT_2K0301_FIRST_TIMEOUT=8
XYLT_2K0301_STALE_AFTER=5
XYLT_SCENARIO_FILE=tests/scenarios/evaluate/gas_alarm.json
XYLT_OUTPUT_FILE=runtime/latest_evaluate_response.json
XYLT_INTERVAL=2
```

查看状态和日志：

```bash
systemctl --user status xylt-safecloud-client.service
journalctl --user -u xylt-safecloud-client.service -f
```

如果比赛现场要求断开 SSH 后仍保持运行，需要在板端确认用户服务 linger，或由 2K1000LA 主控进程直接拉起同一条 `cloud_client.py --loop` 命令。

真实 LLM 调试：

```bash
python3 app_2k1000la/cloud_client.py \
  --base-url http://192.168.14.20:8000 \
  --sensor-source scenario \
  --scenario-file tests/scenarios/evaluate/gas_alarm.json \
  --output-file runtime/latest_evaluate_response.json \
  --use-real-llm \
  --include-debug
```

超时回退测试：

```bash
python3 app_2k1000la/cloud_client.py \
  --base-url http://192.168.14.20:8999 \
  --sensor-source scenario \
  --scenario-file tests/scenarios/evaluate/gas_alarm.json \
  --timeout 2 \
  --output-file runtime/fallback_response.json
```

## 测试

```bash
PYTHONPATH=. python -m pytest app_2k1000la/tests
```

## 后续

- 将该客户端封装到 2K1000LA 主控常驻进程。
- 根据 301 实测日志继续调优 MQTT 断线重连、离线判定和执行命令 ACK 展示。
- 将 `final_status` 同步给 Qt HMI、语音播报和本地执行控制。
