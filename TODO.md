# TODO

## 已完成

- 建立仓库目录结构、AGENTS.md、PROJECT_CONTEXT.md 和协议 Schema 初稿。
- 建立 SafeCloud 云端最小原型和 Web Dashboard。
- 建立命令行语音 + LLM demo。
- 为语音 demo 增加 manual / 百度 / 讯飞 ASR 可切换后端。
- 建立 Analyzer 大模型调用与多模型协同分析模块。
- 在龙芯 2K1000LA 板端验证 Analyzer 真实 API 调用。
- 为 SafeCloud 增加 `/api/evaluate`，接入 Analyzer。

## 当前联调任务

1. 启动 Windows/云端 SafeCloud：`SAFECLOUD_HOST=0.0.0.0`。
2. 从龙芯板通过 HTTP 调用 `/api/evaluate`，发送模拟传感器 JSON。
3. 验证 mock 模式、单模型真实模式、多模型报警仲裁模式。
4. 记录板端到云端调用延迟和失败回退表现。

## 下一步建议

1. 将 `/api/evaluate` 返回的 `final_status` 接入 Qt HMI。
2. 将 `voice_text` 接入语音播报。
3. 增加场景化 mock 数据：正常、温度异常、气体异常、振动异常、传感器离线。
4. 为 2K1000LA 侧增加 HTTP 客户端模块，封装云端请求和超时回退。
5. 后续再接真实 2K0301 传感器采集与执行控制。
