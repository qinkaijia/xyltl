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
- SafeCloud 云端最小可运行原型已建立。
- 嵌入式、HMI、视觉、语音等业务模块尚未实现。

## 下一步建议

1. 运行 SafeCloud 和 `simulator/mock_device.py` 做云端闭环联调。
2. 增加场景化 mock 数据，覆盖正常、温湿度异常、气体异常等测试场景。
3. 将 SafeCloud Dashboard 接口接入 Web 大屏。
4. 再开始真实龙芯硬件接入。
