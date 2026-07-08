# voice

语音唤醒、识别和播报模块目录。当前阶段新增 `voice_text_player.py`，用于把 SafeCloud/analyzer 返回的 `final_status.voice_text` 接入播报链路。

## voice_text 播报

默认使用 print 模式，便于板端无 TTS 环境时联调：

```bash
python3 voice/voice_text_player.py --input-file runtime/latest_evaluate_response.json --mode print
```

也可以从标准输入读取：

```bash
cat runtime/latest_evaluate_response.json | python3 voice/voice_text_player.py --input-file - --mode print
```

如板端安装了语音合成工具，可切换：

```bash
VOICE_TTS_MODE=espeak python3 voice/voice_text_player.py --input-file runtime/latest_evaluate_response.json
VOICE_TTS_MODE=spd-say python3 voice/voice_text_player.py --input-file runtime/latest_evaluate_response.json
VOICE_TTS_MODE=baidu python3 voice/voice_text_player.py --input-file runtime/latest_evaluate_response.json
```

`baidu` 模式复用 `voice_llm_demo/tts.py`，需要在运行环境或 `voice_llm_demo/.env` 中配置 `BAIDU_API_KEY`、`BAIDU_SECRET_KEY`，并保证板端可用 `aplay` 播放。

预录音频模式：

```bash
mkdir -p voice/audio
# 可放入 normal.wav、warning.wav、alarm.wav、default.wav
VOICE_TTS_MODE=audio VOICE_AUDIO_DIR=voice/audio \
  python3 voice/voice_text_player.py --input-file runtime/latest_evaluate_response.json
```

`audio` 模式会根据文本中是否包含“正常 / 预警 / 报警”选择对应 wav，并通过 `aplay` 播放；缺少音频文件时回退打印。

如果 TTS 命令不可用，脚本会回退打印文本，不会让主流程崩溃。

## 与 2K1000LA 客户端联动

`app_2k1000la/cloud_client.py` 支持直接播报：

```bash
python3 app_2k1000la/cloud_client.py \
  --base-url http://192.168.14.20:8000 \
  --scenario-file tests/scenarios/evaluate/temperature_warning.json \
  --output-file runtime/latest_evaluate_response.json \
  --include-debug \
  --speak \
  --tts-mode print
```

常驻系统建议使用报警触发播报，避免每次轮询都重复播：

```bash
python3 app_2k1000la/cloud_client.py \
  --base-url http://192.168.43.5:8010 \
  --sensor-source 2k0301 \
  --mqtt-host 127.0.0.1 \
  --output-file runtime/latest_evaluate_response.json \
  --include-debug \
  --loop \
  --interval 2 \
  --speak-on-alert \
  --tts-mode baidu \
  --alert-cooldown-seconds 30
```

`--speak-on-alert` 会在 `need_voice_alert=true` 或 `alarm_level>0` 时播报 `final_status.voice_text`，同一风险默认 30 秒内不重复播报，风险原因变化会立即重新播报。

## 说明

命令行语音交互 demo 仍在 `voice_llm_demo/` 中维护，用于 VAD、ASR、LLM 和命令执行链路。
