# CHANGELOG

## Unreleased

- 初始化 SafetyGuardian-Loongson 项目框架、协议 Schema 和模块目录。
- 增加 SafeCloud 云端原型，支持设备管理、遥测上传、阈值报警、命令轮询、Dashboard 汇总和模拟设备。
- 增加 SafeCloud Web Dashboard。
- 增加 `POST /api/evaluate`，接入 `modules/analyzer`，可对模拟传感器 JSON 返回统一安全状态。
- 增加命令行语音 + LLM demo，支持 VAD 录音、ASR、LLM 分析、安全校验和模拟命令执行。
- 为语音 demo 增加 manual、百度短语音识别、讯飞语音听写三种 ASR 模式。
- 增加 Analyzer 多模型协同分析模块，包含本地规则、模型路由、真实 LLM API 客户端、裁决和 SafetyGuard。
- 在龙芯 2K1000LA 板端验证 Analyzer 真实 API 调用：DeepSeek、Kimi、智谱、豆包、通义均通过。
