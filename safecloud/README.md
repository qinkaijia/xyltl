# SafeCloud 云端原型

SafeCloud 是本项目的云端系统原型，负责设备管理、遥测接收、历史数据存储、阈值报警、控制指令下发和 Dashboard 数据聚合。

当前版本不依赖真实硬件，真实龙芯派或边缘网关后续只需要按 HTTP API 或预留 MQTT Topic 接入标准 JSON 数据。

## 功能

- 设备新增、查询和状态更新。
- 动态 `metrics` 遥测数据上传，不写死传感器字段。
- SQLite 存储设备、遥测、报警和命令。
- 简单阈值报警，阈值可通过环境变量配置。
- 云端创建控制指令，设备轮询待执行指令并回传结果。
- Dashboard Summary 接口，便于后续 Web 大屏展示。
- 模拟设备脚本，可定时上传数据并执行命令。

## 目录

```text
safecloud/
  app/
    main.py
    core/config.py
    db/
    models/
    schemas/
    services/
    api/routes/
  simulator/mock_device.py
  docs/
  requirements.txt
  .env.example
```

## 启动方式

Linux / macOS:

```bash
cd safecloud
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.db.init_db
uvicorn app.main:app --reload
```

Windows PowerShell:

```powershell
cd safecloud
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.db.init_db
uvicorn app.main:app --reload
```

启动后访问：

- 健康检查：http://127.0.0.1:8000/health
- Swagger API：http://127.0.0.1:8000/docs

## 快速测试

创建设备：

```bash
curl -X POST http://127.0.0.1:8000/api/devices \
  -H "Content-Type: application/json" \
  -d '{"device_id":"gateway_001","device_name":"一号边缘网关","device_type":"gateway","location":"实验室演示舱","status":"online"}'
```

上传遥测：

```bash
curl -X POST http://127.0.0.1:8000/api/telemetry \
  -H "Content-Type: application/json" \
  -d '{"device_id":"gateway_001","timestamp":"2026-07-01T12:00:00Z","metrics":{"temperature":48.5,"humidity":58.2,"gas":360,"light":300}}'
```

查询最新数据：

```bash
curl http://127.0.0.1:8000/api/telemetry/latest/gateway_001
```

创建控制指令：

```bash
curl -X POST http://127.0.0.1:8000/api/commands \
  -H "Content-Type: application/json" \
  -d '{"device_id":"gateway_001","command_type":"fan_control","command_payload":{"state":"on"}}'
```

查询 Dashboard：

```bash
curl http://127.0.0.1:8000/api/dashboard/summary
```

## 模拟设备

在另一个终端运行：

```bash
cd safecloud
python simulator/mock_device.py --base-url http://127.0.0.1:8000 --device-id gateway_001 --interval 5
```

模拟设备会：

- 自动创建或复用设备。
- 定时生成动态环境指标并上传。
- 查询待执行控制命令。
- 模拟执行命令并回传执行结果。

## 文档

- `docs/cloud_architecture.md`：云端架构设计。
- `docs/api_contract.md`：HTTP API 合约。
- `docs/database_schema.md`：数据库结构。
- `docs/mqtt_topics.md`：MQTT Topic 预留。
- `docs/hardware_integration_guide.md`：真实硬件接入指南。
- `docs/development_plan.md`：后续开发计划。
