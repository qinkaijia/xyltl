# SafeCloud API 合约

基础地址：`http://127.0.0.1:8000`

局域网板端联调时，将 `127.0.0.1` 替换为运行 SafeCloud 的主机 IP，例如 `http://192.168.14.20:8000`。

## 健康检查

- 方法：`GET`
- URL：`/health`
- 返回：

```json
{
  "status": "ok",
  "service": "SafeCloud"
}
```

## 设备接口

### 创建设备

- 方法：`POST`
- URL：`/api/devices`
- 作用：注册网关、传感器节点或模拟设备。

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

### 查询设备

- `GET /api/devices`
- `GET /api/devices/{device_id}`
- `PUT /api/devices/{device_id}`

## 遥测接口

### 上传遥测

- 方法：`POST`
- URL：`/api/telemetry`
- 作用：设备端上传标准化环境指标，云端写入数据库并执行简单阈值报警。

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

### 查询遥测

- `GET /api/telemetry/latest/{device_id}`
- `GET /api/telemetry/history/{device_id}?limit=100`

## Analyzer 评估接口

### 评估当前风险

- 方法：`POST`
- URL：`/api/evaluate`
- 作用：调用 `modules/analyzer`，对标准化后的传感器数据执行本地规则、模型路由、LLM 分析、裁决和 SafetyGuard。

请求：

```json
{
  "device_id": "board_2k1000la",
  "metrics": {
    "temperature": 31.0,
    "humidity": 58.0,
    "tvoc": 2600,
    "eco2": 2400,
    "mq3_value": 0.86,
    "flame_detected": false,
    "risk_score": 78
  },
  "system_state": {
    "cloud_connected": true,
    "voice_state": "idle",
    "sensor_online": true
  },
  "use_real_llm": false,
  "force_model": "",
  "include_debug": true
}
```

字段说明：

- `metrics`：端侧标准化后的传感器指标。301 当前主字段为 `temperature/humidity/tvoc/eco2/mq3_value/flame_detected/risk_score`；`gas` 可由 2K1000LA 或 SafeCloud 根据这些字段归一化得到。
- `use_real_llm`：`false` 时使用 mock 调试，`true` 时调用真实 API；真实 API 失败会显式写入 `debug.model_results[].error`，不会回退 mock 占位结果。
- `force_model`：可选 `deepseek`、`kimi`、`zhipu`、`doubao`、`qwen`、`mock`，用于逐个供应商调试。
- `include_debug`：是否返回路由、规则和模型输出调试信息。

返回：

```json
{
  "final_status": {
    "device_id": "board_2k1000la",
    "alarm_level": 1,
    "status_text": "预警",
    "sensor_metrics": {
      "temperature": 31.0,
      "humidity": 58.0,
      "tvoc": 2600,
      "eco2": 2400,
      "mq3_value": 0.86,
      "flame_detected": false,
      "risk_score": 78
    },
    "need_cloud_upload": true,
    "need_voice_alert": true,
    "analysis_mode": "mock_multi_llm"
  },
  "debug": {
    "task_type": "warning",
    "router": {
      "selected_models": ["doubao"]
    }
  }
}
```

安全约束：LLM 和 JudgeModel 不允许降低 RuleEngine 判定出的报警等级。

## 视觉评估接口

### 上传摄像头关键帧并评估 PPE

- 方法：`POST`
- URL：`/api/vision/evaluate`
- 作用：接收 2K1000LA USB 摄像头 JPEG 关键帧，云端模式下调用豆包视觉模型，返回人员、安全帽、口罩、反光背心、火焰等安全评估结果。

请求：

```json
{
  "device_id": "board_2k1000la",
  "timestamp": "2026-07-08T12:00:00+08:00",
  "image_base64": "...",
  "image_mime": "image/jpeg",
  "mode": "cloud",
  "sensor_snapshot": {
    "temperature": 25.0,
    "humidity": 55.0,
    "tvoc": 120,
    "eco2": 450,
    "mq3_value": 0.123,
    "flame_detected": false,
    "risk_score": 0
  },
  "include_debug": true
}
```

返回：

```json
{
  "vision_status": {
    "device_id": "board_2k1000la",
    "mode": "cloud",
    "backend": "doubao_vision",
    "camera_online": true,
    "person_detected": true,
    "helmet_detected": true,
    "mask_detected": false,
    "reflective_vest_detected": true,
    "fire_detected": false,
    "ppe_status": "fail",
    "missing_ppe": ["口罩"],
    "summary": "检测到人员未佩戴口罩。",
    "latency_ms": 1200,
    "image_available": true
  },
  "debug": null
}
```

### 查询最近视觉结果和模式

- `GET /api/vision/latest`
- `GET /api/vision/latest-image`
- `GET /api/vision/mode`
- `POST /api/vision/mode`，请求体：`{"mode":"cloud"}`，可选值为 `cloud/local/off`。

约束：`local` YOLO 推理在 2K1000LA 板端运行，SafeCloud 只负责保存模式请求和云端视觉评估；云端和本地视觉推理不应同时运行。

## 报警接口

- `GET /api/alarms`
- `GET /api/alarms/{device_id}`
- `PUT /api/alarms/{alarm_id}/handle`

## 控制命令接口

- `POST /api/commands`
- `GET /api/commands/pending/{device_id}`
- `PUT /api/commands/{command_id}/result`

## Dashboard 接口

- `GET /api/dashboard/summary`
