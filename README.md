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

## 当前状态

已完成：

- 仓库结构、Agent 开发规范、协议 Schema 初稿。
- SafeCloud 最小可运行云端原型：设备、遥测、报警、命令、Dashboard。
- SafeCloud `/api/evaluate`：接入 analyzer，可通过 HTTP 对模拟传感器数据做规则判断和多 LLM 分析。
- Analyzer 模块：RuleEngine、TaskClassifier、ModelRouter、真实 LLM API 客户端、JudgeModel、SafetyGuard、JSON 输出。
- Analyzer 已在龙芯 2K1000LA 板端完成真实 API 联调：DeepSeek、Kimi、智谱、豆包、通义均可调用。
- 语音命令行 demo：VAD 录音、manual / 百度 / 讯飞 ASR 可切换、MockLLM、安全校验和模拟命令执行。
- Qt HMI 原型和 SafeCloud Web Dashboard 原型。

下一步：

- 用板端 HTTP 客户端调用 Windows/云端 SafeCloud `/api/evaluate`。
- 将 `/api/evaluate` 返回的 `final_status` 接入 Qt、语音播报和后续板间通信。
- 逐步用真实传感器和执行器替换 mock 数据。
