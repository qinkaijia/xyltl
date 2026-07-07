# 2K1000LA 与电脑端 SafeCloud 通信协议说明

本文档约定龙芯 2K1000LA 主控板与电脑端 SafeCloud 云端原型之间的通信方式。后续 2K0301 接入后，2K1000LA 仍按本文档把本地传感器数据或 301 上报数据转换为统一云端请求。

当前板端地址：`192.168.43.40`。该地址只用于本轮调试记录，协议本身不依赖固定板端 IP。

## 总体链路

```text
2K0301 / mock 数据源
  -> 2K1000LA cloud_client.py
  -> HTTP POST /api/evaluate
  -> 电脑端 SafeCloud
  -> final_status
  -> 2K1000LA runtime/latest_evaluate_response.json
  -> Qt HMI / 语音播报 / 本地执行控制
```

2K1000LA 与电脑端云服务之间采用：

- 服务发现：UDP broadcast
- 主业务请求：HTTP JSON
- 云端服务端口：建议 `8010`
- UDP 发现端口：默认 `8011`
- 字符编码：UTF-8
- 数据格式：JSON

## 电脑端 SafeCloud 启动约定

电脑端运行 SafeCloud，监听局域网地址：

```bash
cd safecloud
uvicorn app.main:app --host 0.0.0.0 --port 8010
```

同时启动 UDP discovery responder：

```bash
cd safecloud
python discovery_responder.py \
  --bind-host 0.0.0.0 \
  --discovery-port 8011 \
  --service-port 8010
```

健康检查：

```text
GET http://<电脑IP>:8010/health
```

期望返回：

```json
{"status":"ok","service":"SafeCloud"}
```

电脑端 Web 大屏：

```text
http://<电脑IP>:8010/dashboard
```

## 2K1000LA 云端地址发现

2K1000LA 查找 SafeCloud 的优先级：

1. 命令行 `--base-url`
2. 环境变量 `SAFECLOUD_BASE_URL`
3. 板端缓存文件 `~/.xylt_safecloud.json`
4. UDP 广播自动发现
5. 全部失败时使用本地规则回退

UDP 发现请求：

```text
SAFECLOUD_DISCOVER
```

UDP 发现响应：

```json
{
  "service": "SafeCloud",
  "base_url": "http://192.168.43.x:8010"
}
```

收到 `base_url` 后，2K1000LA 必须再访问 `/health` 确认服务可用。确认成功后把地址写入：

```text
~/.xylt_safecloud.json
```

缓存示例：

```json
{
  "base_url": "http://192.168.43.x:8010",
  "updated_at": "2026-07-06T17:30:00"
}
```

## 2K1000LA 调用 SafeCloud

接口：

```text
POST /api/evaluate
Content-Type: application/json
```

完整 URL：

```text
http://<电脑IP>:8010/api/evaluate
```

### 请求字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `device_id` | string | 是 | 2K1000LA 整机设备 ID，例如 `board_2k1000la` |
| `timestamp` | string | 否 | ISO 8601 时间；不填时云端自动补当前时间 |
| `metrics` | object | 是 | 归一化后的环境与设备指标 |
| `system_state` | object | 否 | 端侧状态 |
| `use_real_llm` | boolean | 否 | 是否启用真实 LLM，默认 `false` |
| `force_model` | string | 否 | 指定模型：`deepseek/kimi/zhipu/doubao/qwen/mock`，默认空字符串自动路由 |
| `include_debug` | boolean | 否 | 是否返回调试信息，联调阶段建议 `true` |

### `metrics` 字段

当前云端 analyzer 使用以下字段：

| 字段 | 类型 | 单位 / 范围 | 来源 |
| --- | --- | --- | --- |
| `temperature` | number | 摄氏度 | 2K0301 或 mock |
| `humidity` | number | 0-100 | 2K0301 或 mock |
| `gas` | number | 建议 0-1 归一化浓度 | 由 2K1000LA 根据 TVOC/eCO2/MQ-3 换算 |
| `vibration` | number | 当前无真实传感器时填 `0.0` | 2K1000LA 补齐 |
| `current` | number | 当前无真实传感器时填 `0.0` | 2K1000LA 补齐 |

### `system_state` 字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `sensor_online` | boolean | 2K0301 或传感器链路是否在线 |
| `cloud_connected` | boolean | 2K1000LA 认为云端是否在线 |
| `voice_state` | string | 语音状态，例如 `idle/listening/speaking` |
| `user_question` | string | 可选，语音或文本交互问题 |
| `request_report` | boolean | 可选，是否请求报告类分析 |

## 请求示例

Mock 或 301 正常数据：

```json
{
  "device_id": "board_2k1000la",
  "metrics": {
    "temperature": 31.5,
    "humidity": 52.0,
    "gas": 0.23,
    "vibration": 0.0,
    "current": 0.0
  },
  "system_state": {
    "sensor_online": true,
    "cloud_connected": true,
    "voice_state": "idle"
  },
  "use_real_llm": false,
  "force_model": "",
  "include_debug": true
}
```

2K0301 离线：

```json
{
  "device_id": "board_2k1000la",
  "metrics": {
    "temperature": 0.0,
    "humidity": 0.0,
    "gas": 0.0,
    "vibration": 0.0,
    "current": 0.0
  },
  "system_state": {
    "sensor_online": false,
    "cloud_connected": true,
    "voice_state": "idle"
  },
  "include_debug": true
}
```

## SafeCloud 响应字段

接口返回：

```json
{
  "final_status": {
    "timestamp": "2026-07-06 17:30:00",
    "device_id": "board_2k1000la",
    "alarm_level": 0,
    "status_text": "正常",
    "temperature": 31.5,
    "humidity": 52.0,
    "gas": 0.23,
    "vibration": 0.0,
    "current": 0.0,
    "reason": "所有关键指标处于正常范围",
    "suggestion": "系统运行正常，保持常规监测。",
    "voice_text": "当前设备运行正常。所有关键指标处于正常范围。系统运行正常，保持常规监测。",
    "cloud_connected": true,
    "need_cloud_upload": false,
    "need_voice_alert": false,
    "analysis_mode": "mock_multi_llm",
    "source": {
      "rule_engine": true,
      "llm_analyzer": true,
      "judge_model": true,
      "safety_guard": true
    }
  },
  "debug": {
    "task_type": "normal_monitoring",
    "router": {},
    "rule_result": {},
    "model_results": [],
    "judge_result": {},
    "client": {
      "ok": true,
      "elapsed_ms": 67,
      "base_url": "http://192.168.43.x:8010"
    }
  }
}
```

`debug` 只在请求 `include_debug=true` 时返回。2K1000LA 本地 `cloud_client.py` 会在收到响应后补充 `debug.client`，用于显示云端连接状态、延迟和目标地址。

## 2K1000LA 本地输出文件

2K1000LA 将完整响应写入：

```text
runtime/latest_evaluate_response.json
```

Qt HMI 和语音播报模块读取该文件。文件内容就是上文响应 JSON，不额外包一层。

推荐命令：

```bash
cd ~/xylt
python3 app_2k1000la/cloud_client.py \
  --sensor-source mock \
  --output-file runtime/latest_evaluate_response.json \
  --include-debug \
  --loop \
  --interval 2
```

如果需要手动指定电脑端云服务：

```bash
python3 app_2k1000la/cloud_client.py \
  --sensor-source mock \
  --base-url http://<电脑IP>:8010 \
  --output-file runtime/latest_evaluate_response.json \
  --include-debug \
  --loop \
  --interval 2
```

## 异常与回退

2K1000LA 调用 SafeCloud 失败时不能崩溃。必须生成本地回退响应：

```json
{
  "final_status": {
    "alarm_level": 2,
    "status_text": "报警",
    "analysis_mode": "local_http_fallback",
    "cloud_connected": false,
    "reason": "传感器离线，无法确认现场状态",
    "suggestion": "云端请求失败，已启用端侧本地规则兜底；请保持现场巡检，关键动作按本地规则执行。",
    "need_voice_alert": true
  },
  "debug": {
    "client": {
      "ok": false,
      "elapsed_ms": 2000,
      "base_url": "http://<电脑IP>:8010",
      "error": "timed out"
    }
  }
}
```

回退规则：

- `sensor_online=false`：直接报警。
- 温度、气体、湿度、振动、电流超过本地阈值：按本地阈值预警或报警。
- 云端不可用时，HMI 和语音仍使用本地回退结果。
- 报警、排风等关键动作不能依赖云端成功返回。

## 2K0301 接入后的转换入口

当前 2K1000LA 客户端支持：

```bash
--sensor-source scenario
--sensor-source mock
--sensor-source 2k0301
```

`app_2k1000la/sensor_source.py` 中的 `Future2K0301Source` 已作为 MQTT 数据源入口。它订阅 301 上报 Topic，把 MQTT payload 转换为同一类 `/api/evaluate` 请求。

当前 301 侧网络与 MQTT 约定：

| 项目 | 当前值 |
| --- | --- |
| 2K0301 IP | `192.168.43.39`，DHCP 动态获取 |
| 2K1000LA IP | `192.168.43.40`，DHCP 动态获取 |
| MQTT Broker | 运行在 2K1000LA |
| Broker 地址 | 301 侧连接 `192.168.43.40:1883`，2K1000LA 本地客户端连接 `127.0.0.1:1883` |
| 认证 | 无用户名/密码 |
| QoS | 全部 Topic 当前约定 QoS 1 |

Topic：

| 方向 | Topic | 说明 |
| --- | --- | --- |
| 301 -> 1000LA | `device/2k0301/sensor` | 传感器数据，1 Hz |
| 301 -> 1000LA | `device/2k0301/heartbeat` | 心跳，0.5 Hz |
| 301 -> 1000LA | `device/2k0301/ack` | 命令 ACK |
| 301 -> 1000LA | `device/2k0301/error` | 故障事件 |
| 1000LA -> 301 | `device/2k0301/command` | 执行命令 |

301 上报字段到云端字段的第一版映射：

| 2K0301 字段 | 2K1000LA / SafeCloud 字段 |
| --- | --- |
| `temperature` | `metrics.temperature` |
| `humidity` | `metrics.humidity` |
| `tvoc` / `eco2` / `mq3_value` / `risk_score` | `metrics.gas`，取归一化最大值 |
| `flame_detected=true` | 本地直接提升风险并触发报警命令 |
| 心跳超时 | `system_state.sensor_online=false` |

301 示例 payload：

```json
{
  "type": "sensor_packet",
  "seq": 0,
  "payload": {
    "device_id": "board_2k0301",
    "timestamp": "2026-07-06T13:25:30",
    "temperature": 28.0,
    "humidity": 37.5,
    "tvoc": 5,
    "eco2": 400,
    "mq3_value": 0.004,
    "flame_detected": false,
    "risk_score": 5
  }
}
```

## 联调检查清单

电脑端：

```bash
curl http://127.0.0.1:8010/health
```

2K1000LA：

```bash
ping <电脑IP>
python3 app_2k1000la/cloud_client.py \
  --sensor-source mock \
  --base-url http://<电脑IP>:8010 \
  --output-file runtime/latest_evaluate_response.json \
  --include-debug
```

MQTT 数据源本地转换命令：

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

检查输出：

- 终端出现 `safecloud_base_url=... source=cli/env/cache/discovery`
- 终端出现 `evaluate_result level=... mode=... elapsed_ms=...`
- `runtime/latest_evaluate_response.json` 存在
- JSON 中 `debug.client.ok=true`
- Web 大屏 `http://<电脑IP>:8010/dashboard` 可打开
- Qt HMI 使用 `--status-file runtime/latest_evaluate_response.json` 能显示同一状态

## 当前网络记录

本轮用户报告：

```text
2K1000LA: 192.168.43.40
2K0301: 192.168.43.39
MQTT Broker: 192.168.43.40:1883
```

电脑端 IP 以实际 WLAN 地址为准。推荐通过 UDP discovery 或 `SAFECLOUD_BASE_URL` 传入，不在代码中写死。
