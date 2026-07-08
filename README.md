# SafetyGuardian-Loongson

本仓库是"基于龙芯双处理器与多 LLM 仲裁的密闭空间智能安全监护仪"的工程框架与原型实现。

核心原则：端侧安全优先，云端智能增强。关键报警、排风等动作必须由本地规则兜底，LLM 负责解释、建议、仲裁和报告生成。

## 开发模式

- Windows 主机：代码编写、文档管理、Git 提交、云端服务联调。
- Linux VM：后续用于 LoongArch 交叉编译、依赖管理和本地服务测试。
- 龙芯 2K1000LA 开发板：运行验证 HMI、语音、视觉、云端通信等端侧模块。
- 龙芯 2K0301：后续负责传感器采集与执行控制。

## 整体系统启动方法

当前联调链路：

```text
2K0301/301 传感器与执行器
  -> MQTT Broker on 2K1000LA:1883
  -> 2K1000LA cloud_client.py
  -> Windows SafeCloud :8010
  -> Web Dashboard / Qt HMI / 语音控制
```

### 0. 当前网络记录

本轮可用地址：

```text
Windows/SafeCloud: 192.168.43.5:8010
2K1000LA:          192.168.43.36
2K0301/301:        192.168.43.40
MQTT Broker:       192.168.43.36:1883
```

如果手机热点或路由器变化，只需要把 Windows IP 和板端 IP 换成实际地址。2K1000LA 访问 SafeCloud 时也可以使用 UDP discovery 或 `SAFECLOUD_BASE_URL` 兜底。

### 1. 启动 Windows SafeCloud 和网页

在 Windows PowerShell：

```powershell
cd D:\xylt
$env:SAFECLOUD_MQTT_CONTROL_ENABLED="1"
$env:SAFECLOUD_2K0301_MQTT_HOST="192.168.43.36"
$env:SAFECLOUD_2K0301_MQTT_PORT="1883"
$env:SAFECLOUD_2K0301_ACK_TIMEOUT="4"
safecloud\.venv\Scripts\python.exe -m uvicorn safecloud.app.main:app --host 0.0.0.0 --port 8010
```

打开网页：

```text
本机查看：http://127.0.0.1:8010/dashboard
局域网查看：http://192.168.43.5:8010/dashboard
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8010/health
```

### 2. 启动 2K1000LA MQTT Broker

在 2K1000LA：

```bash
systemctl is-active mosquitto || sudo systemctl start mosquitto
```

确认监听：

```bash
ss -ltnp | grep :1883
```

### 3. 启动 301 主程序

在 301：

```bash
cd /home/root
./main
```

后台运行时：

```bash
cd /home/root
nohup ./main > /home/root/xylt_301.log 2>&1 &
```

确认只保留一个主程序：

```bash
ps | awk '$4=="main" {print}'
```

抓 MQTT 数据可在 2K1000LA 上运行：

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -q 1 -v -t 'device/#'
```

### 4. 启动 2K1000LA 云端桥接

在 2K1000LA：

```bash
cd ~/xylt
env PYTHONUNBUFFERED=1 PYTHONPATH=. python3 app_2k1000la/cloud_client.py \
  --base-url http://192.168.43.5:8010 \
  --sensor-source 2k0301 \
  --mqtt-host 127.0.0.1 \
  --mqtt-port 1883 \
  --output-file runtime/latest_evaluate_response.json \
  --include-debug \
  --loop \
  --interval 2 \
  --timeout 20
```

后台运行时：

```bash
cd ~/xylt
nohup sh -c 'env PYTHONUNBUFFERED=1 PYTHONPATH=. python3 app_2k1000la/cloud_client.py --base-url http://192.168.43.5:8010 --sensor-source 2k0301 --mqtt-host 127.0.0.1 --mqtt-port 1883 --output-file runtime/latest_evaluate_response.json --include-debug --loop --interval 2 --timeout 20' \
  > /tmp/xylt_cloud_client.log 2>&1 &
```

检查输出：

```bash
tail -f /tmp/xylt_cloud_client.log
tail -c 800 ~/xylt/runtime/latest_evaluate_response.json
```

### 4.5 启动 2K1000LA USB 摄像头视觉服务

云端豆包视觉模式：

```bash
cd ~/xylt
env PYTHONUNBUFFERED=1 PYTHONPATH=. python3 app_2k1000la/vision_service.py \
  --base-url http://192.168.43.5:8010 \
  --camera-index 0 \
  --mode cloud \
  --output-dir runtime/vision \
  --loop \
  --interval 5 \
  --include-debug
```

如果希望网页上的“视觉巡检”页面直接切换云端/本地/关闭模式，改用：

```bash
env PYTHONUNBUFFERED=1 PYTHONPATH=. python3 app_2k1000la/vision_service.py \
  --base-url http://192.168.43.5:8010 \
  --camera-index 0 \
  --follow-cloud-mode \
  --output-dir runtime/vision \
  --loop
```

本地 YOLO 兜底模式需要先准备 `loongson-safety-vision`：

```bash
export LOONGSON_SAFETY_VISION_DIR=$HOME/loongson-safety-vision
python3 app_2k1000la/vision_service.py --mode local --loop
```

视觉服务会写出 `runtime/vision/latest.jpg`、`runtime/vision/vision_state.json` 和 `runtime/vision/mode_request.json`。

### 5. 启动 Qt HMI

在 2K1000LA 图形桌面已经启动时，通过 SSH 启动：

```bash
cd ~/xylt
DISPLAY=:0 XAUTHORITY=/home/xylt/.Xauthority QT_QPA_PLATFORM=xcb \
  ./qt_hmi/display_qt_app \
  --compact \
  --geometry 780x450+10+10 \
  --status-file /home/xylt/xylt/runtime/latest_evaluate_response.json \
  --voice-file /home/xylt/xylt/runtime/voice_assistant_state.json \
  --vision-file /home/xylt/xylt/runtime/vision/vision_state.json
```

后台运行时：

```bash
cd ~/xylt
nohup env DISPLAY=:0 XAUTHORITY=/home/xylt/.Xauthority QT_QPA_PLATFORM=xcb \
  ./qt_hmi/display_qt_app \
  --compact \
  --geometry 780x450+10+10 \
  --status-file /home/xylt/xylt/runtime/latest_evaluate_response.json \
  --voice-file /home/xylt/xylt/runtime/voice_assistant_state.json \
  --vision-file /home/xylt/xylt/runtime/vision/vision_state.json \
  > /tmp/xylt_qt_hmi.out 2> /tmp/xylt_qt_hmi.err &
```

如果窗口显示不全，优先使用 `--compact --fullscreen`；窗口模式可调整 `--geometry`，例如 `760x430+5+5`。全屏/无窗口管理器环境下不能拖拽窗口是正常现象。

Qt 界面默认会自动启动语音监听进程，也可以用右上角“启动语音/停止语音”按钮手动控制。语音进程从仓库根目录启动 `voice_llm_demo/main.py --continuous`，读取 `voice_llm_demo/.env` 中的 ASR、LLM 和 MQTT 配置，并把状态写入 `runtime/voice_assistant_state.json`。如果需要关闭自动启动，可在启动 Qt 前设置 `VOICE_AUTOSTART=false`。如果可执行文件不在仓库内运行，可设置：

```bash
export XYLT_REPO_ROOT=/home/xylt/xylt
```

新版 Qt HMI 采用分页布局：总览、环境监测、AI 分析、视觉、日志、语音助手独立页面。环境监测页集中显示温度、湿度、TVOC、eCO2、MQ-3、火焰、风险；视觉页显示 USB 摄像头关键帧、人员 PPE 结果，并可写入云端/本地/关闭模式请求；语音页在监听/思考/执行时显示三点动画。

### 6. 语音控制验证

语音助手会把状态和最近问答写入 `runtime/voice_assistant_state.json`，Qt HMI 通过 `--voice-file` 显示“监听、思考、回复、执行结果”。

先用文本绕过 ASR，验证后半段控制链路：

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

问答测试：

```bash
cd ~/xylt
PYTHONPATH=. python3 voice_llm_demo/main.py \
  --manual-text 介绍一下这个系统 \
  --assistant-state-file runtime/voice_assistant_state.json \
  --context-status-file runtime/latest_evaluate_response.json \
  --real-llm \
  --llm-provider doubao \
  --max-history-turns 4 \
  --max-reply-chars 120
```

真实大模型需要在启动语音进程前配置对应环境变量，推荐写入不会提交到 Git 的 `voice_llm_demo/.env`。真实 LLM 模式下，密钥、网络或模型调用失败会在 Qt/终端显示明确错误，不会回退成本地占位回答：

```bash
export VOICE_USE_REAL_LLM=true
export VOICE_LLM_PROVIDER=doubao
export DOUBAO_API_KEY="你的豆包 Key"
export DOUBAO_API_URL="https://ark.cn-beijing.volces.com/api/v3/chat/completions"
export DOUBAO_MODEL="你的豆包模型名"
```

正式收音时还需要配置 ASR：

```bash
export ASR_MODE=baidu
export AUDIO_DEVICE=plughw:1,0
export VOICE_AUTOSTART=true
export VOICE_WAKE_REQUIRED=true
export VOICE_WAKE_WORDS=小龙,你好小龙,龙芯助手,小龙在吗,在吗
export VOICE_WAKE_WINDOW_SECONDS=10
export VOICE_TTS_MODE=baidu
export BAIDU_API_KEY="你的百度 API Key"
export BAIDU_SECRET_KEY="你的百度 Secret Key"
```

Qt 启动的语音进程是非交互模式，若云端 ASR 失败，会提示重说或检查配置，不会卡在手动输入。单独说“小龙”或“在吗”会打开 `VOICE_WAKE_WINDOW_SECONDS` 秒唤醒窗口，窗口内下一句话无需重复唤醒词；每次回答完成后也会自动续同样的追问窗口，超过窗口时间未继续说话才回到待唤醒。当前语音识别是“一句话录完后识别”，不是流式字幕；如果要边说边显示文字，需要后续接入流式 ASR。

常驻 `cloud_client --loop` 建议用于快速刷新状态，不建议每 10 秒都启用真实多模型评测。正式评测或演示 AI 结论时，再通过网页按钮或单次命令启用真实 LLM，可避免传感器离线/异常时频繁调用云端导致界面变慢。

也可将 `--llm-provider` 改为 `doubao`、`deepseek`、`kimi`、`zhipu`，并配置对应 `DOUBAO_API_KEY`、`DEEPSEEK_API_KEY`、`KIMI_API_KEY`、`ZHIPU_API_KEY`。

上下文限制默认值：

```text
VOICE_MAX_HISTORY_TURNS=4
VOICE_MAX_QUESTION_CHARS=120
VOICE_MAX_REPLY_CHARS=180
VOICE_MAX_CONTEXT_CHARS=1600
```

已验证语句：

```text
打开风扇
打开蜂鸣器
红灯闪烁
介绍一下这个系统
```

正式收音可改为：

```bash
PYTHONPATH=. python3 voice_llm_demo/main.py \
  --continuous \
  --assistant-state-file runtime/voice_assistant_state.json \
  --context-status-file runtime/latest_evaluate_response.json \
  --real-llm \
  --llm-provider doubao \
  --mqtt-control \
  --mqtt-host 127.0.0.1
```

### 7. 停止命令

Windows 停 SafeCloud：在运行窗口按 `Ctrl+C`。

2K1000LA 停云端桥接和 Qt：

```bash
pkill -f 'app_2k1000la/cloud_client.py'
pkill -x display_qt_app
```

301 停主程序：

```bash
for pid in $(ps | awk '$4=="main" {print $1}'); do kill "$pid"; done
```

## 顶层模块

- `firmware_2k301/`：2K0301 传感器采集与执行控制（基于龙邱科技 2K301 核心板开源库）。
- `app_2k1000la/`：2K1000LA 主控应用。
- `qt_hmi/`：Qt 5 HMI 显示界面。
- `vision/`：摄像头与视觉识别模块占位。
- `voice/`：语音唤醒、识别和播报模块占位。
- `voice_llm_demo/`：命令行语音 + LLM 交互核心模块。
- `safecloud/`：云端 SafeCloud 服务、Dashboard、设备 API 和 `/api/evaluate` 分析接口。
- `modules/analyzer/`：本地规则 + 多 LLM 协同分析 + SafetyGuard 模块。
- `protocol/`：统一通信协议 JSON Schema。
- `scripts/`：环境检查、部署、运行和日志脚本。
- `hardware_refs/`：龙芯开发板和硬件参考资料。
- `docs/competition/`：赛题要求摘要和方向约束文档。

## firmware_2k301 说明

`firmware_2k301/Loongson_2K300_301_LIB` 是龙邱科技提供的龙芯 2K301 核心板软件开源库（V2.1.0），包含：

- **driver/**：I2C 驱动（MPU6050、ICM42688、LSM6DSR、VL53L0X、SHT30、SGP30 等）、TFT/IPS 屏幕驱动
- **libraries/**：通用库（GPIO、PWM、I2C、SPI、UART、CANFD、NCNN、UDP/TCP 网络通信等）
- **example/**：24 个示例 Demo
- **main/**：主程序工程（CMake 构建，适用于龙芯 2K301 核心板）
- **user_app/**：用户应用（MQ3 传感器监测、WiFi 连接等）

工程使用 Linux + VSCode + LoongArch 交叉编译工具链开发。

## 当前状态

已完成：

- 仓库结构、Agent 开发规范、协议 Schema 初稿。
- SafeCloud 最小可运行云端原型：设备、遥测、报警、命令、Dashboard。
- SafeCloud `/api/evaluate`：接入 analyzer，可通过 HTTP 对模拟传感器数据做规则判断和多 LLM 分析。
- Analyzer 模块：RuleEngine、TaskClassifier、ModelRouter、真实 LLM API 客户端、JudgeModel、SafetyGuard、JSON 输出。
- Analyzer 已在龙芯 2K1000LA 板端完成真实 API 联调：DeepSeek、Kimi、智谱、豆包、通义均可调用。
- 语音命令行 demo：VAD 录音、manual / 百度 / 讯飞 ASR 可切换、MockLLM、安全校验和模拟命令执行。
- Qt HMI 原型和 SafeCloud Web Dashboard 原型。
- SafeCloud Web Dashboard 已增加安全评估面板，可直接选择模拟场景调用 `/api/evaluate`。
- 板端 SafeCloud 轮询客户端已支持用户级 systemd 托管，默认持续写出 `runtime/latest_evaluate_response.json`。
- 板端 SafeCloud 轮询客户端已抽象 `scenario/mock/2k0301` 数据源，`2k0301` MQTT 数据源已完成真实 301 联调。
- Qt HMI 已可读取该输出文件，并提供模型结果详情弹窗查看路由、模型输出和仲裁结果。
- Qt HMI 已支持 800x480 紧凑显示、屏幕选择和窗口几何参数。
- Qt HMI 和 SafeCloud Web 已按 301 真实 payload 展示温度、湿度、TVOC、eCO2、MQ-3、火焰检测、综合风险，界面层统一使用中文标签和值。
- 语音命令行 demo 已支持持续监听真实收音、listen-only 收音探针和 ALSA 设备选择。
- 2K1000LA 已作为 MQTT Broker 接收 301 真实数据，并将数据转发到 SafeCloud `/api/evaluate`。
- 2K1000LA 到 301 的 MQTT 命令下发和 ACK 回传已验证。
- SafeCloud Web Dashboard 已优化为分页面控制台：监护总览、环境监测、AI 评估、告警控制。
- 2K1000LA 默认 MQTT topic 已统一为 `device/board_2k0301/...`，与真实 301 程序一致。
- 真实链路已完成约 5 分钟稳定性测试，2K1000LA 共写出 155 次评估结果到 `runtime/latest_evaluate_response.json`。
- Qt HMI 已通过 `--status-file runtime/latest_evaluate_response.json` 完成板端真实数据源烟测。
- SafeCloud Web/命令 API 已能通过 MQTT 下发 `fan_control`、`buzzer_control`、`alarm_light` 到 301，并显示 ACK。
- 语音 demo 已能将 `打开风扇`、`打开蜂鸣器`、`红灯闪烁` 走完整 LLM/SafetyGuard/MQTT 控制链路并收到 301 ACK。

下一步：

- 做更长时间的赛前稳定性复测，重点看 MQTT 重连、云端超时回退和 301 重启恢复。
- 根据现场交互需要，把 Qt HMI 控制按钮接入已验证的 `modules/control` 命令客户端。
- 最后阶段再做 2K1000LA 开机自启动编排。

详细联调状态和下一步清单见：`NEXT_STEPS.md`。
