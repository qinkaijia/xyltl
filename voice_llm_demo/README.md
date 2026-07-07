# 智能语音 + LLM 命令行 Demo

这是一个不依赖 Qt 的命令行版语音交互核心模块，用于在龙芯 2K1000LA 或 Linux 环境中跑通：

```text
VAD 自动录音 -> ASRClient 识别文本 -> MockLLM 意图识别 -> SafetyGuard 安全校验 -> 模拟设备命令执行 -> 日志记录
```

当前支持三种 ASR 模式：

- `manual`：手动输入模拟 ASR 文本，调试兜底。
- `baidu`：百度短语音识别 REST API。
- `xfyun`：讯飞语音听写 WebSocket API。

## 目录结构

```text
voice_llm_demo/
  main.py
  config.py
  requirements.txt
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
  tools/
    audio_capture_probe.py
```

## 安装依赖

录音依赖系统命令 `arecord`。云端 ASR 推荐安装 Python 包：

```bash
cd ~/voice_llm_demo
pip3 install -r requirements.txt
```

说明：

- 百度 ASR 优先使用 `requests`，如果系统没有安装 `requests`，会自动降级使用 Python 标准库 `urllib`。
- 讯飞 ASR 使用 WebSocket，必须安装 `websocket-client`。

如果板子 apt 或 pip 下载失败，不要先改网络配置，先记录错误信息；开发板厂商源或外部服务器异常很常见。

## 运行方法

```bash
cd ~/voice_llm_demo
python3 main.py
```

启动后：

```text
智能语音 + LLM 命令行 Demo 已启动
按 Enter 开始一次语音交互，输入 q 退出
```

按 Enter 后程序会监听麦克风并自动录音，随后调用 `ASRClient.transcribe(audio_path)`。ASR 返回文本后，主流程继续交给 LLM、SafetyGuard 和 CommandDispatcher。

## 持续监听真实收音

正式演示时可使用持续监听模式，不再每轮按 Enter：

```bash
python3 main.py --continuous --audio-device hw:1,0
```

说明：

- `--continuous` 会一直监听麦克风，VAD 检测到人声后自动录音、ASR、LLM 分析和安全校验。
- `--audio-device` 对应 `arecord -l` 中的设备号；例如板端 USB 声卡常见为 `hw:1,0`。
- 如果不传 `--audio-device`，使用系统默认录音设备。
- 当前仍保留 manual ASR 兜底；未配置云端 ASR 时，录音完成后会要求手动输入识别文本。
- 如果只想验证实时收音，不进入 ASR/LLM，可加 `--listen-only`：

```bash
python3 main.py --continuous --listen-only --audio-device hw:1,0
```

现场噪声导致误触发时，可临时调高阈值：

```bash
MIN_ABSOLUTE_THRESHOLD=800 THRESHOLD_RATIO=4.0 \
  python3 main.py --continuous --listen-only --audio-device hw:1,0
```

先做麦克风探针测试：

```bash
python3 tools/audio_capture_probe.py --device hw:1,0 --seconds 2 --output data/recorded/probe.wav
aplay data/recorded/probe.wav
```

探针会输出 RMS 和峰值；如果峰值很低，优先检查是否选错设备、麦克风静音或输入增益太低。

## 切换 ASR 模式

在 `config.py` 中修改：

```python
ASR_MODE = "manual"
ASR_MODE = "baidu"
ASR_MODE = "xfyun"
```

`main.py` 不需要修改。

也可以在项目目录创建不会提交到 Git 的 `.env` 文件：

```bash
ASR_MODE=baidu
BAIDU_API_KEY=你的百度API_KEY
BAIDU_SECRET_KEY=你的百度SECRET_KEY
XFYUN_APP_ID=你的讯飞APPID
XFYUN_API_KEY=你的讯飞API_KEY
XFYUN_API_SECRET=你的讯飞API_SECRET
```

程序启动时会自动读取 `~/voice_llm_demo/.env`。请不要把真实密钥提交到代码仓库。

## manual 模式

默认配置：

```python
ASR_MODE = "manual"
```

录音完成后会提示：

```text
录音已保存：data/recorded/input_xxx.wav
请手动输入模拟 ASR 识别文本：
```

可测试文本：

```text
开始检测
当前状态怎么样
为什么报警
上传数据
生成报告
停止检测
```

## 百度 ASR 模式

1. 在 `config.py` 中设置：

```python
ASR_MODE = "baidu"
```

2. 配置环境变量：

```bash
export BAIDU_API_KEY="你的百度API_KEY"
export BAIDU_SECRET_KEY="你的百度SECRET_KEY"
```

3. 运行：

```bash
python3 main.py
```

百度模式会先获取 OAuth `access_token`，再调用短语音识别接口。当前录音格式为：

```text
wav / 16000 Hz / 16 bit / 单声道
```

如果密钥缺失、网络失败或百度返回错误码，程序不会崩溃，会打印中文错误并回退到 manual 输入。

## 讯飞 ASR 模式

1. 在 `config.py` 中设置：

```python
ASR_MODE = "xfyun"
```

2. 配置环境变量：

```bash
export XFYUN_APP_ID="你的讯飞APPID"
export XFYUN_API_KEY="你的讯飞API_KEY"
export XFYUN_API_SECRET="你的讯飞API_SECRET"
```

3. 运行：

```bash
python3 main.py
```

讯飞模式会读取 wav 文件中的 PCM 数据，通过 WebSocket 按帧发送：

- 首帧：`status = 0`
- 中间帧：`status = 1`
- 尾帧：`status = 2`

如果密钥缺失、网络失败、WebSocket 连接失败或讯飞返回错误码，程序不会崩溃，会打印中文错误并回退到 manual 输入。

## 麦克风测试命令

```bash
arecord -l
python3 tools/audio_capture_probe.py --device hw:1,0 --seconds 2 --output data/recorded/probe.wav
arecord -q -f S16_LE -r 16000 -c 1 -d 4 test.wav
aplay test.wav
python3 main.py
```

## 常见错误排查

### 未找到 arecord

```bash
which arecord
arecord -l
```

如果确实缺少工具，通常需要安装 `alsa-utils`。在开发板上如果 apt 源不可用，不要先改网络配置，先记录错误信息，因为可能是厂商源服务器问题。

### arecord 找不到声卡

```bash
lsusb
cat /proc/asound/cards
arecord -l
alsamixer
```

确认麦克风或 USB 声卡已插好，输入通道没有静音。

如果板端同时存在板载声卡和 USB 声卡，推荐显式指定设备：

```bash
python3 main.py --list-audio
python3 main.py --continuous --audio-device hw:1,0
```

### 录音一直不停止

可能环境噪声过大，或麦克风增益太高。可在 `config.py` 中调整：

- `THRESHOLD_RATIO`
- `MIN_ABSOLUTE_THRESHOLD`
- `END_SILENCE_SECONDS`
- `MAX_RECORD_SECONDS`

这些参数也支持同名环境变量，方便板端现场调试。

### 百度 ASR 报错

检查：

```bash
echo "$BAIDU_API_KEY"
echo "$BAIDU_SECRET_KEY"
ping aip.baidubce.com
```

常见原因：

- API Key 或 Secret Key 配错。
- 应用未开通语音识别能力。
- 网络无法访问百度云接口。
- 音频格式不是 16k/16bit/单声道 wav。

### 讯飞 ASR 报错

检查：

```bash
echo "$XFYUN_APP_ID"
echo "$XFYUN_API_KEY"
echo "$XFYUN_API_SECRET"
```

常见原因：

- APPID、APIKey、APISecret 不匹配。
- 系统时间不准，导致鉴权失败。
- WebSocket 连接被网络环境拦截。
- 音频格式不是 16k/16bit/单声道 PCM/wav。

## 接入真实 LLM

当前 `LLMClient` 默认调用 `MockLLM`。后续接入真实 LLM 时：

1. 将 `USE_REAL_LLM` 改为 `True`。
2. 在 `llm/llm_client.py` 中把 `_analyze_http()` 对接真实 LLM 服务。
3. 保持返回结构不变：

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
