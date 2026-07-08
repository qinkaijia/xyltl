# TODO

## 已完成

- 建立仓库目录结构、AGENTS.md、PROJECT_CONTEXT.md 和协议 Schema 初稿。
- 建立 SafeCloud 云端最小原型和 Web Dashboard。
- 建立命令行语音 + LLM demo。
- 为语音 demo 增加 manual / 百度 / 讯飞 ASR 可切换后端。
- 建立 Analyzer 大模型调用与多模型协同分析模块。
- 在龙芯 2K1000LA 板端验证 Analyzer 真实 API 调用。
- 为 SafeCloud 增加 `/api/evaluate`，接入 Analyzer。
- 完成板端通过 HTTP 调用 `/api/evaluate` 的 mock、单模型真实、多模型报警仲裁联调。
- 将 `/api/evaluate` 返回的 `final_status` 接入 Qt HMI 文件数据源。
- 将 `voice_text` 接入语音播报桥，默认 print，可切换 TTS 命令。
- 增加正常、温度异常、气体异常、振动异常、传感器离线五类场景化 mock 数据。
- 为 2K1000LA 侧增加 SafeCloud HTTP 客户端，封装云端请求和超时回退。
- 增加 SafeCloud UDP 自动发现、上次成功地址缓存和手动配置兜底。
- 将 2K1000LA HTTP 客户端扩展为 `--loop` 常驻轮询模式。
- Qt HMI 已展示云端响应延迟、分析模式和模型来源。
- 语音播报桥已支持 print、espeak、spd-say 和预录 wav 音频模式。
- 将 `--loop` 轮询客户端接入板端用户级 systemd 启动流程，默认输出 `runtime/latest_evaluate_response.json`。
- Qt HMI 已增加模型结果详情弹窗，可查看路由、本地规则、各模型输出和仲裁结果。
- Qt HMI 已增加 `--compact`、`--screen`、`--geometry`，适配 800x480 小屏和双屏窗口定位。
- 语音 demo 已增加持续监听 `--continuous`、只收音 `--listen-only` 和 `--audio-device`，板端 USB 声卡 `hw:1,0` 收音探针通过。
- 提取龙芯赛题方向二要求到 `docs/competition/loongson_direction2_requirements.md`，用于后续任务回顾。
- 2K1000LA 客户端已增加 `--sensor-source scenario/mock/2k0301`，其中 `2k0301` 已实现 MQTT 数据源入口。
- SafeCloud Web 大屏已增加 `/api/evaluate` 安全评估面板，可选择模拟场景并查看模型明细。
- SafeCloud Web Dashboard 已改为分页面控制台：监护总览、环境监测、AI 评估、告警控制。
- 2K1000LA 已安装并启动 Mosquitto，作为 301 MQTT Broker。
- 301 真实程序 `/home/root/main` 已成功连接 2K1000LA Broker 并发布传感器数据与心跳。
- 2K1000LA 已通过 `--sensor-source 2k0301` 读取真实 301 MQTT 数据并调用电脑 SafeCloud `/api/evaluate`。
- 2K1000LA 已成功向 301 下发 `fan_control` MQTT 命令，并收到 301 ACK。
- 2K1000LA 默认 MQTT topic 已统一为真实 301 使用的 `device/board_2k0301/...`。
- 完成约 5 分钟真实链路稳定性测试：301 -> 2K1000LA MQTT -> SafeCloud `/api/evaluate` -> `runtime/latest_evaluate_response.json`，共写出 155 次评估结果。
- Qt HMI 已通过 `--status-file runtime/latest_evaluate_response.json` 读取真实 301 输出文件的板端烟测。
- SafeCloud Web/命令 API 已支持直接下发 `fan_control`、`buzzer_control`、`alarm_light` 到 301，并展示 ACK 状态。
- 语音 demo 已支持将 `打开风扇`、`打开蜂鸣器`、`红灯闪烁` 转换为真实 MQTT 控制命令，2K1000LA 板端联调收到 301 ACK。
- Qt HMI 已通过 `--voice-file` 显示语音助手最近问题、模型回复、执行结果和助手状态。
- 语音 demo 已增加普通问答的大模型接入入口，并对历史轮数、问题长度、上下文长度和回复长度做限制。

## 当前联调任务

1. 继续观察 301 偶发 SGP30/I2C/ADC 提示，区分传感器噪声和通信故障。
2. 在板端配置真实 LLM API Key 环境变量，验证语音普通问答的真实大模型调用。
3. 做一次更长时间的赛前稳定性复测，重点记录 MQTT 重连、云端超时回退、301 重启恢复。
4. 将 Qt HMI 的控制入口按需要接入 `modules/control` 同一套命令客户端。
5. 最后阶段再做板端开机自启动编排。

## 下一步建议

1. P5：最后阶段再配置板端开机自启动，包括 Mosquitto、SafeCloud 客户端、HMI 和语音监听服务。
2. 做一次更长时间的赛前稳定性复测，重点记录 MQTT 重连、云端超时回退、301 重启恢复。
3. 根据现场屏幕交互需要，把 Qt HMI 的控制按钮接到已验证的 `modules/control`。
4. 保持本地规则链路优先，报警与排风动作不依赖云端单点决策。

详细命令与联调记录见 `NEXT_STEPS.md`。
