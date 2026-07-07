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

## 当前联调任务

1. 在板端使用 `app_2k1000la/cloud_client.py` 轮询 SafeCloud `/api/evaluate`。
2. 将输出文件 `runtime/latest_evaluate_response.json` 交给 Qt HMI 的 `--status-file`。
3. 在 SafeCloud Web 大屏直接运行五类模拟场景，确认 `final_status`、模型详情和 HMI 展示一致。
4. 将 `voice_text` 交给 `voice/voice_text_player.py` 或后续 TTS 模块。
5. 记录请求延迟、超时回退和现场展示效果。

## 下一步建议

1. 现场继续调 VAD 参数和麦克风增益，确认说话触发准确、环境噪声不误触发。
2. 将持续收音后的 wav 接入百度或讯飞 ASR 做端到端语音识别测试。
3. 后续按实测日志验证 `--sensor-source 2k0301`，重点检查 MQTT 订阅、离线判定、gas 归一化和 ACK 展示。
4. 最后阶段再配置板端开机自启动，包括 HMI、SafeCloud 客户端和语音监听服务。
5. 保持本地规则链路优先，报警与排风动作不依赖云端单点决策。
