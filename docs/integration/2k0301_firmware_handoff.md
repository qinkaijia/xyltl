# 2K0301 与 2K1000LA MQTT 通信接口说明

本文档用于交给 2K0301 固件开发同学，实现 2K0301 与龙芯 2K1000LA 主控之间的无线数据通信与执行控制。传感器驱动细节由 2K0301 侧自行完成，本文只约定 2K0301 对 2K1000LA 暴露的 MQTT 接口。

## 总体链路

```text
传感器 / 执行器
  <-> 2K0301
  <-> Wi-Fi + MQTT
  <-> 2K1000LA
  <-> SafeCloud / Qt HMI / 语音 / LLM
```

当前网络记录：

- 2K0301：`192.168.43.40`，DHCP 动态获取。
- 2K1000LA：`192.168.43.36`，DHCP 动态获取。
- MQTT Broker：运行在 2K1000LA。
- Broker 地址：`192.168.43.36:1883`。
- 认证：无用户名/密码。

## Topic 约定

| 方向 | Topic | QoS | 说明 |
| --- | --- | --- | --- |
| 2K0301 -> 2K1000LA | `device/board_2k0301/sensor` | 1 | 传感器数据，1 Hz |
| 2K0301 -> 2K1000LA | `device/board_2k0301/heartbeat` | 1 | 心跳，0.5 Hz |
| 2K0301 -> 2K1000LA | `device/board_2k0301/ack` | 1 | 命令执行结果 |
| 2K0301 -> 2K1000LA | `device/board_2k0301/error` | 1 | 故障事件 |
| 2K1000LA -> 2K0301 | `device/board_2k0301/command` | 1 | 执行控制命令 |

后续多节点扩展时，可改为 `device/{device_id}/sensor` 等格式。

## 上行传感器数据

Topic：

```text
device/board_2k0301/sensor
```

真实示例：

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

字段含义：

| 字段 | 范围 / 含义 |
| --- | --- |
| `temperature` | 摄氏度，-40 到 125 |
| `humidity` | 0 到 100，%RH |
| `tvoc` | 0 到 60000，ppb |
| `eco2` | 400 到 60000，ppm |
| `mq3_value` | 乙醇浓度，mg/L，0 到 999 |
| `flame_detected` | `true` 表示检测到火焰 |
| `risk_score` | 0 到 100，301 侧综合风险指数 |

2K1000LA 会将以上数据转换为 SafeCloud `/api/evaluate` 所需的：

```json
{
  "metrics": {
    "temperature": 28.0,
    "humidity": 37.5,
    "gas": 0.05,
    "vibration": 0.0,
    "current": 0.0
  },
  "system_state": {
    "sensor_online": true,
    "source": "2k0301_mqtt"
  }
}
```

`gas` 由 2K1000LA 侧根据 `tvoc`、`eco2`、`mq3_value`、`risk_score` 归一化计算；如果 `flame_detected=true`，2K1000LA 强制 `gas=1.0`，用于触发高风险判断。

## 心跳

Topic：

```text
device/board_2k0301/heartbeat
```

示例：

```json
{
  "type": "heartbeat",
  "seq": 150,
  "device_id": "board_2k0301",
  "uptime_ms": 300000,
  "sensor_online": true,
  "actuator_online": true,
  "error_flags": []
}
```

2K1000LA 超过 5 秒未收到 `sensor_packet` 或心跳异常时，会把云端 payload 中的 `system_state.sensor_online` 置为 `false`。

## 下行命令

Topic：

```text
device/board_2k0301/command
```

风扇 / 排风：

```json
{"type":"command","seq":2001,"command":"fan_control","params":{"state":"on","speed":80,"duration_ms":30000}}
```

蜂鸣器：

```json
{"type":"command","seq":2002,"command":"buzzer_control","params":{"state":"on","pattern":"fast","duration_ms":10000}}
```

三色灯：

```json
{"type":"command","seq":2003,"command":"alarm_light","params":{"color":"red","mode":"blink","duration_ms":10000}}
```

设备复位：

```json
{"type":"command","seq":2004,"command":"device_reset","params":{"target":"actuator_state"}}
```

要求：

- 2K1000LA、SafeCloud 和语音链路统一发送 compact JSON；当前已验证的 301 程序对命令 JSON 空格比较敏感，固件后续增强解析器时也请继续兼容 compact 格式。
- 收到命令后立即解析并执行。
- 硬件未接时可以记录日志并返回 `ok=true`，但 message 中要说明。
- 未知命令或非法参数必须返回 `ok=false`。
- QoS 1 可能重复投递，301 侧需要按 `seq` 做幂等处理，避免重复执行危险动作。

## ACK

Topic：

```text
device/board_2k0301/ack
```

成功：

```json
{"type":"ack","seq":2001,"ok":true,"message":"fan_control on (未接硬件,命令已记录)"}
```

失败：

```json
{"type":"ack","seq":2001,"ok":false,"error_code":"UNKNOWN_COMMAND","message":"unknown command"}
```

## 错误上报

Topic：

```text
device/board_2k0301/error
```

示例：

```json
{"type":"error","seq":4001,"device_id":"board_2k0301","error_code":"SENSOR_ERROR","message":"SGP30 read timeout"}
```

建议错误码：

- `BAD_JSON`
- `UNKNOWN_TYPE`
- `UNKNOWN_COMMAND`
- `UNSUPPORTED_PARAM`
- `INVALID_PARAM`
- `SENSOR_ERROR`
- `ACTUATOR_ERROR`
- `BUS_ERROR`
- `MQTT_ERROR`
- `WIFI_ERROR`

## 本地安全兜底

无线通信不能替代本地安全逻辑。301 侧必须保留：

- 火焰检测为真时，本地立即蜂鸣器报警、红灯闪烁，可按策略启动排风。
- Wi-Fi 或 MQTT 断开时，继续采集传感器数据。
- 本地规则触发危险条件时，不等待 2K1000LA 或云端，直接执行本地报警动作。
- 收到非法命令时拒绝执行并返回失败 ACK。

## 301 侧自测清单

1. 上电后能连接手机热点。
2. 能连接 2K1000LA 上的 MQTT Broker：`192.168.43.36:1883`。
3. 每秒发布一次 `device/board_2k0301/sensor`。
4. 每 2 秒发布一次 `device/board_2k0301/heartbeat`。
5. 收到 `fan_control`、`buzzer_control`、`alarm_light`、`device_reset` 后能返回 ACK。
6. 收到未知命令能返回失败 ACK。
7. 断开传感器或通信异常时能发布 error，并且主循环不死锁。
8. 火焰或危险条件触发时，本地报警动作不依赖 2K1000LA 或云端。

## 2K1000LA 侧调试命令

2K1000LA 上安装 MQTT Broker：

```bash
sudo apt install mosquitto mosquitto-clients
sudo systemctl enable --now mosquitto
```

监听 301 上报：

```bash
mosquitto_sub -h localhost -t "device/board_2k0301/#" -v
```

模拟下发命令：

```bash
mosquitto_pub -h localhost \
  -t "device/board_2k0301/command" \
  -q 1 \
  -m '{"type":"command","seq":2001,"command":"fan_control","params":{"state":"on","speed":80,"duration_ms":30000}}'
```
