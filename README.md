# SafetyGuardian-Loongson

本仓库是“基于龙芯双处理器与多 LLM 仲裁的密闭空间智能安全监护仪”的工程框架与原型实现。

核心原则：端侧安全优先，云端智能增强。关键报警、排风等动作必须由本地规则兜底，LLM 负责解释、建议、仲裁和报告生成。

## 开发模式

- Windows 主机：代码编写、文档管理、Git 提交、云端服务联调。
- Linux VM：后续用于 LoongArch 交叉编译、依赖管理和本地服务测试。
- 龙芯 2K1000LA 开发板：运行验证 HMI、语音、视觉、云端通信等端侧模块。
- 龙芯 2K0301：后续负责传感器采集与执行控制。

## 顶层模块

- `firmware_2k301/`：2K0301 传感器采集与执行控制。
- `app_2k1000la/`：2K1000LA 主控应用。
- `qt_hmi/`：Qt 5 HMI 显示界面。
- `vision/`：摄像头与视觉识别模块占位。
- `voice/`：语音唤醒、识别和播报模块占位。
- `voice_llm_demo/`：命令行语音 + LLM 交互核心模块。
- `safecloud/`：云端 SafeCloud 服务、Dashboard、设备 API 和 `/api/evaluate` 分析接口。
- `modules/analyzer/`：本地规则 + 多 LLM 协同分析 + SafetyGuard 模块。
- `protocol/`：统一通信协议 JSON Schema。
- `scripts/`：环境检查、部署、运行和日志脚本。
- `hardware_refs/`：龙芯开发板和硬件参考资料。
- `docs/competition/`：赛题要求摘要和方向约束文档。

## 当前状态

已完成：

- 仓库结构、Agent 开发规范、协议 Schema 初稿。
- SafeCloud 最小可运行云端原型：设备、遥测、报警、命令、Dashboard。
- SafeCloud `/api/evaluate`：接入 analyzer，可通过 HTTP 对模拟传感器数据做规则判断和多 LLM 分析。
- Analyzer 模块：RuleEngine、TaskClassifier、ModelRouter、真实 LLM API 客户端、JudgeModel、SafetyGuard、JSON 输出。
- Analyzer 已在龙芯 2K1000LA 板端完成真实 API 联调：DeepSeek、Kimi、智谱、豆包、通义均可调用。
- 语音命令行 demo：VAD 录音、manual / 百度 / 讯飞 ASR 可切换、MockLLM、安全校验和模拟命令执行。
- Qt HMI 原型和 SafeCloud Web Dashboard 原型。
- SafeCloud Web Dashboard 已增加安全评估面板，可直接选择模拟场景调用 `/api/evaluate`。
- 板端 SafeCloud 轮询客户端已支持用户级 systemd 托管，默认持续写出 `runtime/latest_evaluate_response.json`。
- 板端 SafeCloud 轮询客户端已抽象 `scenario/mock/2k0301` 数据源，`2k0301` 已实现 MQTT 数据源入口，等待板端实测。
- Qt HMI 已可读取该输出文件，并提供模型结果详情弹窗查看路由、模型输出和仲裁结果。
- Qt HMI 已支持 800x480 紧凑显示、屏幕选择和窗口几何参数。
- 语音命令行 demo 已支持持续监听真实收音、listen-only 收音探针和 ALSA 设备选择。

下一步：

- 调优板端 VAD 参数并接入百度/讯飞 ASR 做端到端语音识别。
- 使用 `--sensor-source 2k0301` 做 MQTT 实测，确认 301 上报数据能替换 mock `metrics`。
- 将 `final_status` 继续接入后续板间通信和本地执行控制。
- 逐步用真实传感器和执行器替换 mock 数据。
