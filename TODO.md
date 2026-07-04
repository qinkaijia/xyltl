# TODO

## 第一阶段

1. 创建仓库目录结构。
2. 写入 `AGENTS.md` 与 `PROJECT_CONTEXT.md`。
3. 写入 `protocol/` 下的 JSON Schema 初稿。
4. 编写 M1 传感器采集模块 mock 版本。
5. 编写 M2 执行控制模块 mock 版本。
6. 编写一键 build/deploy/run 脚本雏形。
7. 连接真实硬件并逐步替换 mock 数据。

## 当前完成

- 项目框架已建立。
- SafeCloud 云端最小可运行原型和 Web Dashboard 已建立。
- 命令行版语音 + LLM demo 已建立。
- 嵌入式、HMI、视觉、语音等业务模块尚未实现。

## 下一步建议

1. 运行 SafeCloud、Web Dashboard 和 `simulator/mock_device.py` 做云端闭环联调。
2. 增加场景化 mock 数据，覆盖正常、温湿度异常、气体异常等测试场景。
3. 为 Web Dashboard 增加历史曲线和报警处理按钮。
4. 在龙芯板上运行 `voice_llm_demo`，验证 `arecord`、麦克风和手动 ASR 流程。
5. 为龙芯板补齐 Python 包安装方式，确保 `websocket-client` 可用于讯飞 ASR。
6. 配置百度或讯飞真实密钥，做云端 ASR 联调。
7. 再开始真实龙芯硬件接入。
