# SafeCloud 云端架构设计

## 设计目标

SafeCloud 面向工业智能环境监测与控制系统，当前目标是提供一个可演示、可运行、可扩展的云端原型。硬件尚未全部完成时，系统必须能通过模拟设备完成闭环：

```text
设备注册 -> 遥测上传 -> 云端存储 -> 本地规则/LLM 分析 -> 报警状态 -> Dashboard 展示 -> 控制命令下发
```

## 技术选型

- 后端框架：FastAPI，便于快速生成 OpenAPI / Swagger 文档。
- 数据库：SQLite，适合比赛原型和单机演示。
- ORM：SQLAlchemy 2.x。
- 数据校验：Pydantic 2.x。
- 设备通信：当前实现 HTTP API，后续可扩展 MQTT 或 WebSocket。
- LLM 分析：通过 `modules/analyzer` 统一调用，不把各供应商逻辑写进 SafeCloud 路由。

## 模块划分

```text
app/main.py                  FastAPI 入口
app/core/config.py           环境变量与阈值配置
app/db/                      数据库连接和初始化
app/models/                  SQLAlchemy 数据模型
app/schemas/                 Pydantic API 模型
app/services/                业务逻辑
app/api/routes/              HTTP 路由
web/                         Dashboard 静态前端
simulator/mock_device.py     模拟设备
```

## 数据流

### 普通遥测入库

1. 设备调用 `POST /api/telemetry` 上传标准 JSON。
2. 云端按 `device_id` 维护设备在线状态和 `last_seen`。
3. 原始 `metrics` JSON 存入数据库。
4. `alarm_service` 根据阈值配置生成报警记录。
5. Dashboard 通过 `/api/dashboard/summary` 获取聚合数据。

### Analyzer 风险评估

1. 板端或模拟设备调用 `POST /api/evaluate`。
2. SafeCloud 将 `metrics` 和 `system_state` 转换为 analyzer 输入。
3. Analyzer 执行 RuleEngine、TaskClassifier、ModelRouter。
4. 当 `use_real_llm=true` 时，按路由调用 DeepSeek、Kimi、智谱、豆包或通义；失败显式记录错误并由本地规则兜底，不生成 mock 占位结果。
5. JudgeModel 融合结果，SafetyGuard 保证不降低本地规则等级。
6. SafeCloud 返回 `final_status`，供 HMI、语音播报和后续控制链路使用。

## 可扩展原则

- `metrics` 使用 JSON 字段，不绑定固定传感器数量或名称。
- `protocol/` 字段不随意修改；需要修改时同步 Schema、README、测试数据和 PROJECT_CONTEXT。
- 云端 LLM 只做增强分析，不作为唯一安全执行依据。
- HTTP 轮询当前可运行，后续可平滑扩展到 WebSocket/MQTT。
