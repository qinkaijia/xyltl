# SafeCloud 开发计划

## 第一阶段：云端基础框架

- FastAPI 项目结构。
- SQLite 数据库连接。
- 设备、遥测、报警、命令模型。
- 基础 API。
- Swagger 文档自动生成。

当前状态：已完成最小可运行原型。

## 第二阶段：模拟设备联调

- `simulator/mock_device.py` 定时上传模拟数据。
- 模拟数据触发阈值报警。
- 云端创建指令。
- 模拟设备轮询指令并回传结果。

当前状态：已完成基础脚本，可继续增加场景化数据。

## 第三阶段：Web 大屏接口

- Dashboard Summary。
- 最新数据列表。
- 报警统计。
- 设备在线 / 离线状态。
- 后续接入 ECharts、Vue 或 React。

当前状态：已提供 `/api/dashboard/summary`。

## 第四阶段：真实硬件接入

- 龙芯派或边缘网关通过 HTTP 上传数据。
- 设备端轮询控制命令。
- 本地传感器字段映射为标准 `metrics`。
- 本地报警与云端报警协同。

## 第五阶段：MQTT 与移动端扩展

- 引入 MQTT Broker。
- 将 HTTP 遥测入口和 MQTT 消费者复用同一 service 层。
- 增加 WebSocket 实时推送。
- 微信小程序复用现有 API 查询设备、遥测和报警。
