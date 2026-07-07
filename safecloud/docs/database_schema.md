# 数据库结构设计

当前使用 SQLite，表结构通过 SQLAlchemy 模型定义。

## devices

设备表，记录边缘网关、传感器节点和模拟设备。

| 字段 | 类型 | 含义 |
|---|---|---|
| device_id | string | 主键，稳定设备 ID |
| device_name | string | 设备显示名称 |
| device_type | string | 设备类型，如 gateway、sensor_node、mock_gateway |
| location | string | 安装位置 |
| status | string | online、offline、maintenance 等 |
| last_seen | datetime | 最近一次遥测或心跳时间 |
| firmware_version | string | 固件版本 |
| description | text | 备注 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

索引：`device_id` 主键，`status` 用于 Dashboard 统计。

## telemetry_data

遥测数据表，保存设备上报的标准化环境数据。

| 字段 | 类型 | 含义 |
|---|---|---|
| id | integer | 主键，自增 |
| device_id | string | 逻辑外键，关联 devices.device_id |
| timestamp | datetime | 设备采样时间 |
| metrics | JSON | 动态指标，如温度、湿度、气体、噪声等 |
| raw_payload | JSON | 原始上报请求，便于排查 |
| created_at | datetime | 云端入库时间 |

索引：`device_id`、`timestamp`。

`metrics` 使用 JSON 的原因：

- 硬件尚未定型，不应把传感器字段写死到数据库列。
- 不同设备可上报不同指标集合。
- 后续新增传感器时不需要立即改表。
- 原型阶段更适合快速演示和扩展。

后续如果某些指标需要高频分析，可增加派生宽表或时序数据库。

## alarms

报警表，记录阈值报警和后续扩展的规则报警。

| 字段 | 类型 | 含义 |
|---|---|---|
| alarm_id | string | 主键，格式如 alm-xxxx |
| device_id | string | 关联设备 |
| alarm_type | string | threshold、rule、cloud_judge 等 |
| alarm_level | string | info、warning、critical |
| alarm_message | text | 报警说明 |
| metric_name | string | 触发指标名称 |
| metric_value | float | 触发指标值 |
| threshold_value | float | 阈值 |
| status | string | active、handled |
| created_at | datetime | 创建时间 |
| handled_at | datetime | 处理时间 |

索引：`device_id`、`status`、`alarm_level`。

## commands

控制命令表，记录云端下发给设备端的指令。

| 字段 | 类型 | 含义 |
|---|---|---|
| command_id | string | 主键，格式如 cmd-xxxx |
| device_id | string | 目标设备 |
| command_type | string | 命令类型，如 fan_control |
| command_payload | JSON | 命令参数 |
| status | string | pending、sent、executed、failed |
| created_at | datetime | 创建时间 |
| sent_at | datetime | 设备取走命令的时间 |
| executed_at | datetime | 设备回传结果时间 |
| result_message | text | 执行结果说明 |

索引：`device_id`、`status`、`command_type`。

## 迁移到 MySQL / PostgreSQL

- 将 `SAFECLOUD_DATABASE_URL` 改为目标数据库连接串。
- PostgreSQL 可直接使用 JSONB 增强查询能力。
- MySQL 建议使用 8.0 及以上版本，支持 JSON 字段和函数。
- 生产环境应引入 Alembic 管理数据库迁移。
- 大量遥测数据建议按时间分区或迁移到时序数据库。
