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
- Analyzer 已接入 DeepSeek、Kimi、智谱、豆包、通义五种真实 API；真实模式下调用失败会显式记录错误并由本地规则兜底，不再生成 mock 占位结果。
- Analyzer 已在龙芯 2K1000LA 板端完成真实 API 联调，单模型和多模型报警仲裁均通过。
- 语音 demo 已支持 manual、百度 ASR、讯飞 ASR 三种模式。
- 2K1000LA 侧 SafeCloud 轮询客户端已支持用户级 systemd 托管，默认持续写出 `runtime/latest_evaluate_response.json`。
- 2K1000LA 侧数据源已抽象为 `scenario/mock/2k0301`，其中 `2k0301` 已完成真实 MQTT 数据源联调。
- Qt HMI 原型可基于 mock 数据展示状态，也可读取 `/api/evaluate` 输出文件展示云端分析结果和模型详情。
- Qt HMI 已支持 800x480 紧凑模式、屏幕选择和窗口几何参数，适配板端双屏调试。
- 语音 demo 已支持持续监听真实收音、listen-only 收音验证和 ALSA 录音设备选择。
- SafeCloud Web Dashboard 已优化为分页面控制台，分为监护总览、环境监测、AI 评估、告警控制。
- 2K1000LA 已安装并运行 Mosquitto，作为 301 与主控之间的 MQTT Broker。
- 301 `/home/root/main` 已能向 2K1000LA 发布真实传感器数据和心跳。
- 2K1000LA `cloud_client.py --sensor-source 2k0301` 已能读取真实 301 数据并调用电脑 SafeCloud `/api/evaluate`。
- 2K1000LA 向 301 发布 `fan_control` 命令并收到 ACK 的双向 MQTT 控制链路已验证。
- 2K1000LA 默认 MQTT topic 已统一为真实 301 程序使用的 `device/board_2k0301/...`。
- 真实链路已完成约 5 分钟稳定性测试，2K1000LA 共写出 155 次 `/api/evaluate` 结果到 `runtime/latest_evaluate_response.json`。
- Qt HMI 已在板端通过 `--status-file runtime/latest_evaluate_response.json` 读取真实 301 输出文件的烟测。
- SafeCloud/Web 控制链路已接入 `modules/control`，可通过 `POST /api/commands` 下发 `fan_control`、`buzzer_control`、`alarm_light` 并返回 301 ACK。
- 语音 demo 已接入真实 MQTT 控制链路，板端实测 `打开风扇`、`打开蜂鸣器`、`红灯闪烁` 均完成 LLM -> SafetyGuard -> 301 ACK。
- Qt HMI 已增加语音助手显示区，可通过 `--voice-file runtime/voice_assistant_state.json` 显示最近问题、模型回复、执行结果和助手状态。
- 语音 demo 已增加普通问答的大模型接入入口，支持 `qwen/doubao/deepseek/kimi/zhipu`，并限制历史轮数、问题长度、上下文长度和回复长度。
- SafeCloud Web 和 Qt HMI 已按 301 真实 payload 显示 `temperature/humidity/tvoc/eco2/mq3_value/flame_detected/risk_score`，界面层统一使用中文标签和值。
- 2026-07-08 复测时，301 原 C++ 程序未在板上运行；已在 301 上用 `/root/xylt_mqtt_tools/xylt_301_mqtt_mock.sh` 建立 `device/board_2k0301/...` MQTT mock 桥接，2K1000LA 已收到 sensor/heartbeat，并验证 `fan_control` ACK。301 C++ 工程已复制到 Linux VM `~/xylt_301/Loongson_2K300_301_LIB`，原厂 `build.sh` 卡在缺少目标架构 Paho MQTT C `MQTTClient.h/libpaho-mqtt3c`。详见 `docs/integration/2k0301_current_runtime_notes.md`。

## 下一步重点

1. 赛前做更长时间稳定性复测，重点看 MQTT 重连、云端超时回退和 301 重启恢复。
2. 在板端配置真实大模型 API Key 环境变量，做语音问答的真实云端调用复测。
3. 根据现场交互需求，把 Qt HMI 控制按钮接入已验证的 `modules/control` 命令客户端。
4. 最后阶段再配置板端开机自启动。
5. 将关键报警动作继续保持在本地规则链路中，不依赖云端单点决策。

当前真实联调细节和命令见 `NEXT_STEPS.md`。
301 当前运行与编译记录见 `docs/integration/2k0301_current_runtime_notes.md`。

## 赛题回顾锚点

方向二赛题摘要已整理到 `docs/competition/loongson_direction2_requirements.md`。后续新增功能应持续服务“基于 LLM 的智能检测工业仪器设计”，2K0301 作为传感采集与执行控制从板，不把项目主线偏移到方向三。

## 2026-07-08 2K0301 真实程序联调状态

- 已采用“去 Paho”方案改造 301 侧 `lq_mqtt.*`，运行时通过 301 上的 `/root/xylt_mqtt_tools/mosquitto_pub` 和 `mosquitto_sub` 访问 2K1000LA MQTT Broker。
- 301 工程已在 Linux VM `~/xylt_301/Loongson_2K300_301_LIB/main` 交叉编译通过，轻量版二进制不再链接 OpenCV、NCNN、Paho，仅依赖系统基础动态库。
- 当前部署到 301 的真实程序为 `/root/xylt_301_main_nopaho`，mock bridge 已停用。
- 2K1000LA 已收到真实 301 程序发布的 `device/board_2k0301/sensor` 与 `device/board_2k0301/heartbeat`。
- 已验证 2K1000LA 发布 `fan_control` 命令后，301 返回 `device/board_2k0301/ack`，双向 MQTT 链路打通。
- 当前观测：SHT30 温湿度可读；SGP30 eCO2/TVOC 读数已变化，但湿度补偿写入仍有 I2C 失败提示；MQ-3 ADC 偶发 timeout。后续硬件稳定性测试应优先检查 SGP30 湿度补偿写入路径、I2C 可靠性与 ADC 通道。
- 详细运行命令、日志路径和验证样例见 `docs/integration/2k0301_current_runtime_notes.md`。
