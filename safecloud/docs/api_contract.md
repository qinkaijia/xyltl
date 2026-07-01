# SafeCloud API 合约

基础地址：`http://127.0.0.1:8000`

## 设备接口

### 创建设备

- 方法：`POST`
- URL：`/api/devices`
- 作用：注册网关、传感器节点或模拟设备。

请求示例：

```json
{
  "device_id": "gateway_001",
  "device_name": "一号边缘网关",
  "device_type": "gateway",
  "location": "实验室演示舱",
  "status": "online",
  "firmware_version": "v0.1.0",
  "description": "比赛演示设备"
}
```

返回示例：

```json
{
  "device_id": "gateway_001",
  "device_name": "一号边缘网关",
  "device_type": "gateway",
  "location": "实验室演示舱",
  "status": "online",
  "last_seen": null,
  "firmware_version": "v0.1.0",
  "description": "比赛演示设备",
  "created_at": "2026-07-01T12:00:00Z",
  "updated_at": "2026-07-01T12:00:00Z"
}
```

硬件接入注意：`device_id` 必须稳定，建议烧录或写入配置文件，不要每次启动随机生成。

### 查询设备列表

- 方法：`GET`
- URL：`/api/devices`
- 作用：返回所有设备。

### 查询单个设备

- 方法：`GET`
- URL：`/api/devices/{device_id}`
- 作用：返回设备详情。

### 更新设备

- 方法：`PUT`
- URL：`/api/devices/{device_id}`
- 作用：更新设备名称、位置、状态、固件版本等字段。

请求示例：

```json
{
  "status": "offline",
  "description": "维护中"
}
```

## 遥测接口

### 上传遥测数据

- 方法：`POST`
- URL：`/api/telemetry`
- 作用：设备端上传标准化环境指标。

请求示例：

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

返回示例：

```json
{
  "telemetry": {
    "id": 1,
    "device_id": "gateway_001",
    "timestamp": "2026-07-01T12:00:00Z",
    "metrics": {
      "temperature": 26.5,
      "humidity": 58.2,
      "gas": 120
    },
    "raw_payload": {
      "device_id": "gateway_001",
      "timestamp": "2026-07-01T12:00:00Z",
      "metrics": {
        "temperature": 26.5,
        "humidity": 58.2,
        "gas": 120
      }
    },
    "created_at": "2026-07-01T12:00:01Z"
  },
  "generated_alarms": []
}
```

硬件接入注意：云端不关心 GPIO、I2C、SPI 或具体传感器型号，只接收边缘侧标准化后的 JSON。

### 查询最新遥测

- 方法：`GET`
- URL：`/api/telemetry/latest/{device_id}`
- 作用：返回某设备最新一条数据。

### 查询历史遥测

- 方法：`GET`
- URL：`/api/telemetry/history/{device_id}`
- 参数：`start_time`、`end_time`、`limit`
- 作用：按时间范围查询历史数据。

示例：

```text
GET /api/telemetry/history/gateway_001?limit=100
```

## 报警接口

### 查询报警列表

- 方法：`GET`
- URL：`/api/alarms`
- 参数：`status`
- 作用：查询全部报警，可按状态过滤。

### 查询设备报警

- 方法：`GET`
- URL：`/api/alarms/{device_id}`
- 参数：`status`
- 作用：查询某设备报警。

### 处理报警

- 方法：`PUT`
- URL：`/api/alarms/{alarm_id}/handle`
- 作用：将报警标记为已处理。

请求示例：

```json
{
  "result_message": "现场已确认并恢复通风"
}
```

## 控制命令接口

### 创建控制命令

- 方法：`POST`
- URL：`/api/commands`
- 作用：云端向设备创建待执行命令。

请求示例：

```json
{
  "device_id": "gateway_001",
  "command_type": "fan_control",
  "command_payload": {
    "state": "on"
  }
}
```

### 设备查询待执行命令

- 方法：`GET`
- URL：`/api/commands/pending/{device_id}`
- 作用：设备端轮询云端命令。返回后命令状态会从 `pending` 更新为 `sent`。

### 回传命令执行结果

- 方法：`PUT`
- URL：`/api/commands/{command_id}/result`
- 作用：设备执行完成后回传结果。

请求示例：

```json
{
  "status": "executed",
  "result_message": "fan_control executed"
}
```

## Dashboard 接口

### 系统总览

- 方法：`GET`
- URL：`/api/dashboard/summary`
- 作用：提供 Web 大屏可直接使用的聚合数据。

返回示例：

```json
{
  "device_total": 1,
  "online_device_total": 1,
  "active_alarm_total": 2,
  "latest_telemetry": [],
  "recent_alarms": [],
  "device_status": {
    "online": 1
  },
  "metric_names": [
    "temperature",
    "humidity",
    "gas"
  ],
  "extensions": {
    "frontend_hint": "Ready for ECharts/Vue/React dashboards"
  }
}
```
