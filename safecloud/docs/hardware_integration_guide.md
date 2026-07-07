# 硬件接入指南

## 接入原则

真实硬件完成前，云端不绑定 GPIO、串口、I2C、SPI 或具体传感器型号。龙芯派或边缘网关只需把本地采集结果标准化为 JSON 并调用 HTTP API。

## 设备端需要实现的 HTTP 请求

1. 启动时注册或更新设备：`POST /api/devices` 或 `PUT /api/devices/{device_id}`。
2. 定时上传传感器数据：`POST /api/telemetry`。
3. 定时查询待执行命令：`GET /api/commands/pending/{device_id}`。
4. 执行命令后回传结果：`PUT /api/commands/{command_id}/result`。

## 遥测上传格式

```json
{
  "device_id": "gateway_001",
  "timestamp": "2026-07-01T12:00:00Z",
  "metrics": {
    "temperature": 26.5,
    "humidity": 58.2,
    "gas": 120,
    "light": 300,
    "noise": 45
  }
}
```

`metrics` 字段可自由扩展。后续新增电压、电流、PM2.5、TVOC 等指标时，直接添加键值即可。

## 设备 ID 规划

建议格式：

- 网关：`gateway_001`
- 龙芯 2K1000LA：`2k1000la_001`
- 龙芯 2K0301：`2k301_001`
- 传感器节点：`sensor_node_001`

同一设备 ID 不应频繁变化，否则历史数据和命令无法稳定关联。

## 控制命令轮询

设备端定时请求：

```text
GET /api/commands/pending/{device_id}
```

拿到命令后，根据 `command_type` 和 `command_payload` 映射到本地动作。例如：

```json
{
  "command_type": "fan_control",
  "command_payload": {
    "state": "on"
  }
}
```

执行完成后回传：

```json
{
  "status": "executed",
  "result_message": "fan enabled"
}
```

## 模拟设备与真实硬件的对应关系

`simulator/mock_device.py` 模拟了真实硬件需要做的四件事：

1. 注册设备。
2. 上传遥测。
3. 查询命令。
4. 回传命令结果。

真实硬件程序后续可以直接替换这个脚本的数据来源和执行动作。

## MQTT 扩展

切换到 MQTT 时，设备端需要：

- 发布遥测到 `device/{device_id}/telemetry`。
- 订阅 `device/{device_id}/command`。
- 发布执行结果到 `device/{device_id}/command/result`。

HTTP API 仍建议保留，供 Web 后台、小程序和调试工具使用。

## 必须保持稳定的接口

- `device_id`
- `POST /api/telemetry` 请求结构
- `GET /api/commands/pending/{device_id}` 返回结构
- `PUT /api/commands/{command_id}/result` 请求结构

可 mock 的部分：

- 具体传感器字段。
- 控制动作实际执行。
- 报警阈值配置。
- MQTT 通道。
