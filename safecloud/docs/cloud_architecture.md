# SafeCloud 云端架构设计

## 设计目标

SafeCloud 面向工业智能环境监测与控制系统，当前目标是提供一个可演示、可运行、可扩展的云端原型。硬件尚未完成时，系统必须能通过模拟设备完成完整闭环：设备注册 -> 遥测上传 -> 云端存储 -> 报警判断 -> 控制指令下发 -> 设备回传执行结果。

## 技术选型

- 后端框架：FastAPI，便于快速生成 OpenAPI / Swagger 文档。
- 数据库：SQLite，适合比赛原型和单机演示，后续可迁移到 MySQL 或 PostgreSQL。
- ORM：SQLAlchemy 2.x，隔离数据库细节。
- 数据校验：Pydantic，负责 API 入参和返回结构。
- 设备通信：当前实现 HTTP API，预留 MQTT Topic。
- 实时展示：当前提供 Dashboard 聚合接口，后续可扩展 WebSocket。

## 模块划分

```text
app/main.py                FastAPI 入口
app/core/config.py         环境变量与阈值配置
app/db/                    数据库连接和初始化
app/models/                SQLAlchemy 数据表模型
app/schemas/               Pydantic API 模型
app/services/              业务逻辑
app/api/routes/            HTTP 路由
simulator/mock_device.py   模拟设备
```

## 数据流

1. 设备或模拟器调用 `POST /api/telemetry` 上传标准 JSON。
2. 云端按 `device_id` 自动维护设备在线状态和 `last_seen`。
3. 原始 `metrics` JSON 原样存储到 `telemetry_data.metrics`。
4. `alarm_service` 根据阈值配置检查数值型指标。
5. 超阈值时写入 `alarms` 表。
6. Web 大屏调用 `/api/dashboard/summary` 获取聚合数据。
7. 管理端调用 `POST /api/commands` 创建控制指令。
8. 设备轮询 `GET /api/commands/pending/{device_id}` 获取命令。
9. 设备执行后调用 `PUT /api/commands/{command_id}/result` 回传结果。

## 可扩展原则

- `metrics` 使用 JSON 字段，不绑定固定传感器数量或名称。
- 报警阈值当前在配置中，后续可迁移到数据库规则表。
- HTTP 轮询命令当前可运行，后续可平滑替换为 MQTT 下发。
- Dashboard 接口返回结构直接服务前端，同时保留 `extensions` 字段。
