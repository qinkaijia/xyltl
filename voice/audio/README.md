# 预录播报音频

可在本目录放入以下 wav 文件，供 `VOICE_TTS_MODE=audio` 使用：

- `normal.wav`
- `warning.wav`
- `alarm.wav`
- `default.wav`

板端脚本会通过 `aplay` 播放；文件缺失时自动回退打印 `voice_text`。
