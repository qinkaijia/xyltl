# SafetyGuardian-Loongson

基于龙芯 2K1000LA、2K0301 与多 LLM 仲裁的密闭空间智能安全监护仪项目框架。

本仓库当前已建立基础项目框架，并开始实现云端 SafeCloud 原型。

## 开发模式

- Windows 主机：代码编写、文档管理、Git 提交、AI Agent 协作。
- Ubuntu Linux VM：LoongArch 交叉编译、依赖管理、本地服务测试。
- 龙芯开发板：2K1000LA 与 2K0301 程序运行、验证和日志采集。

## 顶层模块

- `firmware_2k301/`：2K0301 传感器采集与执行控制。
- `app_2k1000la/`：2K1000LA 主控应用。
- `qt_hmi/`：HMI 显示界面。
- `vision/`：摄像头与视觉识别。
- `voice/`：语音唤醒、识别和播报。
- `voice_llm_demo/`：命令行版语音 + LLM 交互核心模块。
- `safecloud/`：云端 SafeCloud 服务与多 LLM 仲裁。
- `protocol/`：统一通信协议 JSON Schema。
- `scripts/`：环境检查、构建、部署、运行和日志脚本。
- `tests/`：系统级 mock 数据、集成测试和场景测试。
- `tools/`：辅助调试工具。

## 当前状态

已完成：

- 仓库目录结构。
- Agent 开发规范初稿。
- 项目背景与模块边界说明。
- 四类协议 Schema 初稿。
- 各模块 README 占位。
- 自动化脚本雏形。
- SafeCloud 最小可运行云端原型：设备、遥测、报警、命令、Web Dashboard 和模拟设备。
- 命令行版语音 + LLM demo：VAD 录音、手动 ASR、MockLLM、安全校验、模拟设备命令执行。

后续按 `TODO.md` 逐步实现 mock 流程与真实硬件接入。
