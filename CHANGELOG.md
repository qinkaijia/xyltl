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
- 为 Qt HMI 增加 `FinalStatusDataProvider`，支持读取 `/api/evaluate` 响应文件显示 `final_status`。
- 增加 `voice/voice_text_player.py`，支持从 `voice_text` 做 print/espeak/spd-say 播报。
- 增加五类场景化 mock 数据和 SafeCloud 场景测试。
- 增加 2K1000LA SafeCloud HTTP 客户端，支持请求 `/api/evaluate`、写出响应、语音播报和本地超时回退。
- 增加 SafeCloud UDP 自动发现 responder，以及板端自动发现、缓存和手动配置兜底。
- 为板端客户端增加 `--loop` 常驻轮询模式。
- Qt HMI 增加云端延迟和模型来源显示。
- 语音播报桥增加预录 wav 音频模式。
- 增加 2K1000LA 用户级 systemd 轮询客户端安装脚本，默认输出 `runtime/latest_evaluate_response.json`。
- Qt HMI 增加模型结果详情弹窗，展示云端请求、模型路由、本地规则、各模型输出和仲裁结果。
- Qt HMI 增加紧凑小屏模式和屏幕/窗口几何参数，适配 800x480 + HDMI 双屏场景。
- 语音 demo 增加持续监听、只收音和 ALSA 设备选择参数，并增加固定时长录音探针。
- 增加赛题方向二要求摘要文档，用于约束后续功能不偏离“基于 LLM 的智能检测工业仪器设计”。
- 2K1000LA 客户端增加 `scenario/mock/2k0301` 数据源抽象，并为 `2k0301` 实现 Wi-Fi + MQTT 订阅与字段转换入口。
- SafeCloud Web Dashboard 增加 `/api/evaluate` 安全评估面板，支持从网页选择模拟场景并查看模型详情。
