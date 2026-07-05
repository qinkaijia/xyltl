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

## 当前联调任务

1. 在板端使用 `app_2k1000la/cloud_client.py` 轮询 SafeCloud `/api/evaluate`。
2. 将输出文件 `runtime/latest_evaluate_response.json` 交给 Qt HMI 的 `--status-file`。
3. 将 `voice_text` 交给 `voice/voice_text_player.py` 或后续 TTS 模块。
4. 记录请求延迟、超时回退和现场展示效果。

## 下一步建议

1. 将 2K1000LA HTTP 客户端改造成常驻服务或主控进程子模块。
2. 在 Qt HMI 中增加云端响应延迟、分析模式和模型来源展示。
3. 为语音播报接入板端实际 TTS 工具或预录音频播报。
4. 从真实 2K0301 采集数据生成 `metrics`，逐步替换场景化 mock。
5. 保持本地规则链路优先，报警与排风动作不依赖云端单点决策。
