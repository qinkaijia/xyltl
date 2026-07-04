# 智能语音 + LLM 命令行 Demo

这是一个不依赖 Qt 的命令行版语音交互核心模块，用于在龙芯 2K1000LA 或 Linux 环境中先跑通“录音 -> 手动 ASR -> MockLLM 意图识别 -> 安全校验 -> 模拟设备命令执行 -> 日志记录”的闭环。

当前版本默认不接真实 ASR、不接真实 LLM、不接真实传感器。后续可以把 `ASRClient`、`LLMClient`、`DeviceState` 和 `CommandDispatcher` 替换为真实实现。

## 目录结构

```text
voice_llm_demo/
  main.py
  config.py
  recorder/
    vad_recorder.py
  asr/
    asr_client.py
  llm/
    mock_llm.py
    llm_client.py
  device/
    device_state.py
    command_dispatcher.py
  safety/
    safety_guard.py
  data/recorded/
  logs/
  README.md
```

## 运行方法

```bash
cd ~/voice_llm_demo
python3 main.py
```

如果是在本仓库中运行：

```bash
cd voice_llm_demo
python3 main.py
```

启动后：

```text
智能语音 + LLM 命令行 Demo 已启动
按 Enter 开始一次语音交互，输入 q 退出
```

按 Enter 后程序会监听麦克风并自动录音。录音完成后，当前版本会提示手动输入模拟 ASR 文本。

可测试文本：

```text
开始检测
当前状态怎么样
为什么报警
上传数据
生成报告
停止检测
```

## 依赖说明

代码尽量只使用 Python 标准库。录音依赖 Linux 的 ALSA 命令行工具 `arecord`。

常用检查命令：

```bash
arecord -l
arecord -q -f S16_LE -r 16000 -c 1 -d 4 test.wav
aplay test.wav
python3 main.py
```

## 麦克风测试方法

1. 运行 `arecord -l` 查看录音设备。
2. 运行 `arecord -q -f S16_LE -r 16000 -c 1 -d 4 test.wav` 录 4 秒。
3. 运行 `aplay test.wav` 回放。
4. 如果能听到声音，再运行 `python3 main.py`。

## 常见问题

### 未找到 arecord

说明系统可能没有安装 ALSA 工具。可先检查：

```bash
which arecord
arecord -l
```

如果确实缺少工具，通常需要安装 `alsa-utils`。在开发板上如果 apt 源不可用，不要先改网络配置，先记录错误信息，因为可能是厂商源服务器问题。

### arecord 找不到声卡

检查 USB 声卡或麦克风是否插好：

```bash
lsusb
cat /proc/asound/cards
arecord -l
```

也可以用 `alsamixer` 检查输入音量是否被静音。

### 录音一直不停止

可能环境噪声过大，或麦克风增益太高。可以在 `config.py` 中调整：

- `THRESHOLD_RATIO`
- `MIN_ABSOLUTE_THRESHOLD`
- `END_SILENCE_SECONDS`
- `MAX_RECORD_SECONDS`

### 录音太短

可以适当降低 `MIN_ABSOLUTE_THRESHOLD` 或提高麦克风增益。

## 接入真实 ASR

当前 `config.py` 中：

```python
USE_REAL_ASR = False
ASR_API_URL = "http://127.0.0.1:8000/api/asr"
```

后续接入真实 ASR 时：

1. 将 `USE_REAL_ASR` 改为 `True`。
2. 在 `asr/asr_client.py` 中把 `_transcribe_http()` 对接真实接口协议。
3. 保持 `transcribe(audio_path) -> str` 接口不变，主程序无需修改。

## 接入真实 LLM

当前 `LLMClient` 默认调用 `MockLLM`。后续接入真实 LLM 时：

1. 将 `USE_REAL_LLM` 改为 `True`。
2. 在 `llm/llm_client.py` 中把 `_analyze_http()` 对接真实 LLM 服务。
3. 确保真实 LLM 返回字段包含：

```python
{
    "type": "control | query | analysis | report | error",
    "intent": "START_DETECTION",
    "need_execute": True,
    "need_confirm": False,
    "params": {},
    "reply": "好的，已开始设备检测。"
}
```

无论是真实 LLM 还是 MockLLM，输出都会经过 `SafetyGuard` 独立校验。

