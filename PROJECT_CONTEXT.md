# PROJECT_CONTEXT.md

## 项目名称

基于龙芯双处理器与多 LLM 仲裁的密闭空间智能安全监护仪。

## 应用场景

面向化工储罐、地下管廊、受限空间作业等场景，实现环境监测、风险分级、声光报警、强制排风、语音交互、HMI 展示和云端多模型协同分析。

## 系统定位

本项目属于嵌入式设计竞赛方向：基于 LLM 的智能检测工业仪器设计。系统采用“端侧安全优先，云端智能增强”的架构：

- 2K0301：传感器采集与执行控制。
- 2K1000LA：主控、HMI、视觉、语音、云端通信、本地规则。
- SafeCloud：数据接收、远程展示、LLM 分析、报告和后续设备管理。

## 当前硬件

- 龙芯 2K1000LA：主控、HMI、视觉、语音、云端通信。
- 龙芯 2K0301：传感器采集与执行控制。
- 传感器：FC-01、SHT、SGP30、MQ-3。
- 执行器：三色灯、蜂鸣器、TB6612 + 直流电机。
- 交互：USB 声卡 / 播放器、语音唤醒与播报。

## 风险等级

当前 analyzer 使用 0/1/2 三级输出：

- `0`：正常
- `1`：预警
- `2`：报警

本地规则输出是安全下限。云端 LLM 和 JudgeModel 不允许降低本地规则判定出的报警等级。

## 当前进度

- 仓库基础框架、协议 Schema、模块 README 和脚本骨架已建立。
- SafeCloud 云端原型已实现设备、遥测、报警、命令和 Dashboard。
- SafeCloud 已新增 `POST /api/evaluate`，可调用 analyzer 对模拟传感器数据进行安全分析。
- SafeCloud Web 大屏已增加安全评估面板，可直接选择五类模拟场景调用 `/api/evaluate` 并展示模型明细。
- Analyzer 已接入 DeepSeek、Kimi、智谱、豆包、通义五种真实 API，并保留 mock 回退。
- Analyzer 已在龙芯 2K1000LA 板端完成真实 API 联调，单模型和多模型报警仲裁均通过。
- 语音 demo 已支持 manual、百度 ASR、讯飞 ASR 三种模式。
- 2K1000LA 侧 SafeCloud 轮询客户端已支持用户级 systemd 托管，默认持续写出 `runtime/latest_evaluate_response.json`。
- 2K1000LA 侧数据源已抽象为 `scenario/mock/2k0301`，其中 `2k0301` 已实现 Wi-Fi + MQTT 数据源入口，等待板端和 301 实测。
- Qt HMI 原型可基于 mock 数据展示状态，也可读取 `/api/evaluate` 输出文件展示云端分析结果和模型详情。
- Qt HMI 已支持 800x480 紧凑模式、屏幕选择和窗口几何参数，适配板端双屏调试。
- 语音 demo 已支持持续监听真实收音、listen-only 收音验证和 ALSA 录音设备选择。

## 下一步重点

1. 调优板端 VAD 参数和麦克风增益，并接入百度/讯飞 ASR 做端到端语音识别。
2. 使用 `--sensor-source 2k0301` 做 MQTT 实测，确认 301 上报数据能替换 mock 数据并进入 `/api/evaluate`。
3. 将 `/api/evaluate` 返回的 `final_status` 接入后续板间通信和本地执行控制。
4. 最后阶段再配置板端开机自启动。
5. 将关键报警动作继续保持在本地规则链路中，不依赖云端单点决策。

## 赛题回顾锚点

方向二赛题摘要已整理到 `docs/competition/loongson_direction2_requirements.md`。后续新增功能应持续服务“基于 LLM 的智能检测工业仪器设计”，2K0301 作为传感采集与执行控制从板，不把项目主线偏移到方向三。
