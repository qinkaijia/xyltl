# 智能语音 + LLM 命令行 Demo

这是一个不依赖 Qt 的命令行版语音交互核心模块，用于在龙芯 2K1000LA 或 Linux 环境中跑通：

```text
VAD 自动录音 -> ASRClient 识别文本 -> MockLLM 意图识别 -> SafetyGuard 安全校验 -> 模拟或 MQTT 设备命令执行 -> 日志记录
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
    mqtt_executor.py
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

## 接入真实 301 控制

默认情况下命令仍然走模拟执行，便于离线调试。需要在 2K1000LA 上真实控制 301 时，增加 `--mqtt-control`：

```bash
cd ~/xylt
PYTHONPATH=. python3 voice_llm_demo/main.py \
  --manual-text 打开风扇 \
  --assistant-state-file runtime/voice_assistant_state.json \
  --context-status-file runtime/latest_evaluate_response.json \
  --mqtt-control \
  --mqtt-host 127.0.0.1 \
  --mqtt-ack-timeout 5
```

常用验证语句：

```text
打开风扇
打开蜂鸣器
红灯闪烁
```

本轮板端联调结果：

```text
打开风扇   -> FAN_CONTROL    -> fan_control ACK 成功
打开蜂鸣器 -> BUZZER_CONTROL -> buzzer_control ACK 成功
红灯闪烁   -> ALARM_LIGHT    -> alarm_light ACK 成功
```

正式演示时可把 `--mqtt-control` 与 `--continuous` 组合使用；录音设备通过 `.env` 中的 `AUDIO_DEVICE=plughw:1,0` 指定。语音文本仍会经过 `SafetyGuard`，关闭类或高风险类动作会按安全策略要求确认或拒绝。

## Qt 显示与大模型问答

语音助手每轮都会写出状态文件，供 Qt HMI 的 `--voice-file` 读取：

```bash
runtime/voice_assistant_state.json
```

状态文件包含：

```text
state / state_text
last_user_text
last_reply
last_intent
safety_message
execute_message
llm_provider
history
```

普通问答可接入真实大模型，硬件控制命令仍优先走本地规则和 SafetyGuard：

```bash
cd ~/xylt
export VOICE_USE_REAL_LLM=true
export VOICE_LLM_PROVIDER=doubao
export DOUBAO_API_KEY="你的豆包 Key"
export DOUBAO_API_URL="https://ark.cn-beijing.volces.com/api/v3/chat/completions"
export DOUBAO_MODEL="你的豆包模型名"

PYTHONPATH=. python3 voice_llm_demo/main.py \
  --manual-text 介绍一下这个系统 \
  --assistant-state-file runtime/voice_assistant_state.json \
  --context-status-file runtime/latest_evaluate_response.json \
  --real-llm \
  --llm-provider doubao \
  --max-history-turns 4 \
  --max-reply-chars 120
```

支持的 provider：

```text
qwen    -> QWEN_API_KEY / QWEN_API_URL / QWEN_MODEL
doubao  -> DOUBAO_API_KEY / DOUBAO_API_URL / DOUBAO_MODEL
deepseek -> DEEPSEEK_API_KEY / DEEPSEEK_API_URL / DEEPSEEK_MODEL
kimi    -> KIMI_API_KEY / KIMI_API_URL / KIMI_MODEL
zhipu   -> ZHIPU_API_KEY / ZHIPU_API_URL / ZHIPU_MODEL
```

上下文限制：

```text
VOICE_MAX_HISTORY_TURNS=4
VOICE_MAX_QUESTION_CHARS=120
VOICE_MAX_REPLY_CHARS=180
VOICE_MAX_CONTEXT_CHARS=1600
```

这些限制用于控制传给模型的历史轮数、用户问题长度、设备状态上下文长度和最终语音回复长度，避免回答过长或泄露过多无关上下文。

Qt HMI 默认会自动启动同一套语音进程，也可以用右上角“启动语音/停止语音”按钮手动控制。Qt 会读取 `voice_llm_demo/.env`，GUI 非交互模式会自动设置 `ASR_FALLBACK_MANUAL=false`，因此 ASR 失败时会提示重说，不会等待手动输入。若需要关闭自动启动，可在启动 Qt 前设置 `VOICE_AUTOSTART=false`。

正式演示建议开启唤醒词和播报：

```bash
VOICE_AUTOSTART=true
VOICE_WAKE_REQUIRED=true
VOICE_WAKE_WORDS=小龙,你好小龙,龙芯助手,小龙在吗,在吗
VOICE_WAKE_WINDOW_SECONDS=10
VOICE_TTS_MODE=baidu
VOICE_TTS_MAX_CHARS=180
```

连续监听时，说“你好小龙，介绍一下当前系统”会去掉唤醒词后进入 ASR/LLM 流程。只说“你好小龙”或“在吗”时，助手会播报“我在，请说”，并打开 `VOICE_WAKE_WINDOW_SECONDS` 秒唤醒窗口；窗口内下一句话无需重复唤醒词。每次回答完成后会继续延长同样的追问窗口，超过窗口时间未继续说话才结束对话。播报使用百度 TTS 生成 wav，再通过板端 `aplay` 播放。

## 持续监听真实收音

正式演示时可使用持续监听模式，不再每轮按 Enter：

```bash
AUDIO_DEVICE=plughw:1,0 python3 main.py --continuous
```

说明：

- `--continuous` 会一直监听麦克风，VAD 检测到人声后自动录音、ASR、LLM 分析和安全校验。
- `AUDIO_DEVICE` 对应 ALSA 设备名；板端 USB 声卡建议使用 `plughw:1,0`，让 ALSA 自动转换为 ASR 需要的 16k/16bit/单声道。
- 如果不设置 `AUDIO_DEVICE`，使用系统默认录音设备。
- 当前仍保留 manual ASR 兜底；未配置云端 ASR 时，录音完成后会要求手动输入识别文本。
- 如果只想验证实时收音，不进入 ASR/LLM，可加 `--listen-only`：

```bash
AUDIO_DEVICE=plughw:1,0 python3 main.py --continuous --listen-only
```

现场噪声导致误触发时，可临时调高阈值：

```bash
MIN_ABSOLUTE_THRESHOLD=800 THRESHOLD_RATIO=4.0 \
  AUDIO_DEVICE=plughw:1,0 python3 main.py --continuous --listen-only
```

先做麦克风探针测试：

```bash
python3 tools/audio_capture_probe.py --device plughw:1,0 --seconds 2 --output data/recorded/probe.wav
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
AUDIO_DEVICE=plughw:1,0
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

如果密钥缺失、网络失败或百度返回错误码，程序不会崩溃。命令行交互模式会回退到 manual 输入；Qt/后台等非交互模式会返回空文本并提示重新说或检查配置，避免进程卡住。

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

如果密钥缺失、网络失败、WebSocket 连接失败或讯飞返回错误码，程序不会崩溃。命令行交互模式会回退到 manual 输入；Qt/后台等非交互模式会返回空文本并提示重新说或检查配置。

## 麦克风测试命令

```bash
arecord -l
python3 tools/audio_capture_probe.py --device plughw:1,0 --seconds 2 --output data/recorded/probe.wav
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
AUDIO_DEVICE=plughw:1,0 python3 main.py --continuous
```

### 录音一直不停止

可能环境噪声过大，或麦克风增益太高。可在 `config.py` 中调整：

- `THRESHOLD_RATIO`
- `MIN_ABSOLUTE_THRESHOLD`
- `END_SILENCE_SECONDS`
- `MAX_RECORD_SECONDS`

这些参数也支持同名环境变量，方便板端现场调试。

### 说话或播报中途停止

- 如果是“我还没说完，录音就结束”，通常是说话中间停顿被 VAD 当作静音。可增大 `END_SILENCE_SECONDS`，当前默认 `1.8` 秒；也可增大 `MAX_RECORD_SECONDS`，当前默认 `15` 秒。
- 如果是“助手回答播报到一半就停”，通常是播报字符上限或 `aplay` 播放超时。当前 `VOICE_TTS_MAX_CHARS` 默认 `180`，百度 TTS 播放超时会随文本长度放宽。
- Qt 启动的语音进程日志在仓库根目录的 `runtime/voice_assistant_process.log`，交互 JSON 日志在 `voice_llm_demo/logs/demo.log`。

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

## 真实 LLM 输出结构

`LLMClient` 已支持 Qwen、Doubao、DeepSeek、Kimi、Zhipu 的真实 Chat Completions 调用。普通问答会调用真实模型；硬件执行命令仍优先由本地 `MockLLM`/规则解析，以保证安全动作不依赖云端自由生成。真实模型和本地解析都保持同一返回结构：

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
