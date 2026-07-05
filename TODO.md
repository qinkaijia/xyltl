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

## 当前联调任务

1. 在板端使用 `app_2k1000la/cloud_client.py` 轮询 SafeCloud `/api/evaluate`。
2. 将输出文件 `runtime/latest_evaluate_response.json` 交给 Qt HMI 的 `--status-file`。
3. 将 `voice_text` 交给 `voice/voice_text_player.py` 或后续 TTS 模块。
4. 记录请求延迟、超时回退和现场展示效果。

## 下一步建议

1. 将 `--loop` 轮询客户端接入 systemd 或 2K1000LA 主控进程启动流程。
2. 为 Qt HMI 增加模型结果详情弹窗或独立页面。
3. 录制并放置正式比赛用 `normal/warning/alarm/default.wav`。
4. 从真实 2K0301 采集数据生成 `metrics`，逐步替换场景化 mock。
5. 保持本地规则链路优先，报警与排风动作不依赖云端单点决策。
