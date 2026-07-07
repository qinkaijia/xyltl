# MQTT Topic 预留设计

当前版本先使用 HTTP API，后续可增加 MQTT Broker。Topic 设计保持和 HTTP 数据结构一致。

## Topic 列表

| Topic | 方向 | QoS | 说明 |
|---|---|---|---|
| device/{device_id}/telemetry | 设备 -> 云端 | 1 | 上传遥测数据 |
| device/{device_id}/status | 设备 -> 云端 | 1 | 上报在线、离线、维护等状态 |
| device/{device_id}/alarm | 设备 -> 云端 | 1 | 设备本地报警上报 |
| device/{device_id}/command | 云端 -> 设备 | 1 | 云端下发控制命令 |
| device/{device_id}/command/result | 设备 -> 云端 | 1 | 命令执行结果回传 |

## telemetry 消息

```json
{
  "device_id": "gateway_001",
  "timestamp": "2026-07-01T12:00:00Z",
  "metrics": {
    "temperature": 26.5,
    "humidity": 58.2,
    "gas": 120
  }
}
```

对应 HTTP：`POST /api/telemetry`

## status 消息

```json
{
  "device_id": "gateway_001",
  "status": "online",
  "firmware_version": "v0.1.0",
  "timestamp": "2026-07-01T12:00:00Z"
}
```

对应 HTTP：`PUT /api/devices/{device_id}`

## command 消息

```json
{
  "command_id": "cmd-abc123",
  "device_id": "gateway_001",
  "command_type": "fan_control",
  "command_payload": {
    "state": "on"
  }
}
```

对应 HTTP：`GET /api/commands/pending/{device_id}`

## command/result 消息

```json
{
  "command_id": "cmd-abc123",
  "status": "executed",
  "result_message": "fan_control executed"
}
```

对应 HTTP：`PUT /api/commands/{command_id}/result`

## 从 HTTP 切换到 MQTT

1. 保持设备 ID、遥测 JSON、命令 JSON 不变。
2. 新增 MQTT 消费者，将 Topic 消息转交现有 service 层。
3. 云端创建命令后，同时写数据库并发布到 `device/{device_id}/command`。
4. 设备端从轮询改为订阅命令 Topic。
5. HTTP API 保留给 Web 管理端和小程序使用。
