# app_2k1000la

2K1000LA 主控侧应用目录。当前阶段先提供可在板端运行的 SafeCloud HTTP 客户端，用于联调云端 `/api/evaluate` 和本地超时回退。

## SafeCloud 客户端

文件：`cloud_client.py`

功能：

- 读取场景化 mock JSON。
- 调用 SafeCloud `POST /api/evaluate`。
- 将返回结果写入本地 JSON，供 Qt HMI 使用。
- 请求失败、超时或返回异常时，使用端侧本地阈值规则生成 `local_http_fallback`。
- 可选 `--speak`，把 `final_status.voice_text` 交给 `voice/voice_text_player.py` 播报。

示例：

```bash
python3 app_2k1000la/cloud_client.py \
  --base-url http://192.168.14.20:8000 \
  --scenario-file tests/scenarios/evaluate/temperature_warning.json \
  --output-file runtime/latest_evaluate_response.json \
  --include-debug \
  --speak \
  --tts-mode print
```

真实 LLM 调试：

```bash
python3 app_2k1000la/cloud_client.py \
  --base-url http://192.168.14.20:8000 \
  --scenario-file tests/scenarios/evaluate/gas_alarm.json \
  --output-file runtime/latest_evaluate_response.json \
  --use-real-llm \
  --include-debug
```

超时回退测试：

```bash
python3 app_2k1000la/cloud_client.py \
  --base-url http://192.168.14.20:8999 \
  --scenario-file tests/scenarios/evaluate/gas_alarm.json \
  --timeout 2 \
  --output-file runtime/fallback_response.json
```

## 测试

```bash
PYTHONPATH=. python -m pytest app_2k1000la/tests
```

## 后续

- 将该客户端封装到 2K1000LA 主控常驻进程。
- 从真实 2K0301 采集数据生成 `metrics`。
- 将 `final_status` 同步给 Qt HMI、语音播报和本地执行控制。
