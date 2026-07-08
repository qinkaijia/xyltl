# qt_hmi

基于 Qt5 Widgets + CMake 的工业监测仪表盘。HMI 通过 `IDataProvider` 抽象接入数据源，当前支持两种模式：

- 默认 `MockDataProvider`：独立生成模拟状态。
- `FinalStatusDataProvider`：读取 SafeCloud/analyzer 的 `final_status` JSON，显示真实分析结果。

## 编译

CMake 方式：

```bash
cd qt_hmi
mkdir -p build
cd build
cmake ..
make -j$(nproc)
```

板端如果没有 `cmake`，可直接使用 `qmake`：

```bash
cd qt_hmi
qmake display_qt.pro
make -j$(nproc)
```

板端已有 Qt 5.15.2 时可直接使用系统 Qt。

## 运行 mock 模式

```bash
./build/display_qt_app
./build/display_qt_app --fullscreen
```

## 接入 final_status

`app_2k1000la/cloud_client.py` 可把 `/api/evaluate` 响应写入文件，例如：

```bash
python3 app_2k1000la/cloud_client.py \
  --base-url http://192.168.14.20:8000 \
  --scenario-file tests/scenarios/evaluate/gas_alarm.json \
  --output-file runtime/latest_evaluate_response.json \
  --include-debug
```

HMI 读取该文件：

```bash
./build/display_qt_app --status-file ../runtime/latest_evaluate_response.json
```

如果文件内容是完整响应：

```json
{
  "final_status": {
    "alarm_level": 2,
    "voice_text": "当前设备处于报警状态。",
    "sensor_metrics": {
      "temperature": 31.0,
      "humidity": 58.0,
      "tvoc": 2600,
      "eco2": 2400,
      "mq3_value": 0.86,
      "flame_detected": false,
      "risk_score": 78
    }
  }
}
```

或直接是 `final_status` 对象，HMI 都可以解析。

## 显示内容

- HMI 使用分页布局，适配 800x480 小屏：总览、环境监测、AI分析、日志、语音。
- 环境监测页集中显示温度、湿度、TVOC、eCO2、MQ-3、火焰、风险 7 个检测量，底部显示采集板在线状态、来源、更新时间和原始温湿度。
- 协议字段仍使用英文键，HMI 展示层统一显示中文标签和值，例如 `flame_detected=false` 显示为“未检测”，不会直接显示 `false`。
- 当 301 上报 `temperature=-999`、`humidity=-1` 或心跳 `sensor_online=false` 时，HMI 显示“离线”，保留原始值到详情，不把哨兵值当正常数据展示。
- `reason` 和 `suggestion` 显示在中部信息区。
- `voice_text` 在底部状态栏展示，后续可与语音播报模块联动。
- `--voice-file` 可读取语音助手状态文件，在界面中显示最近问题、模型回复、执行结果和助手状态。
- 点击右上角“启动语音”可直接拉起 `voice_llm_demo/main.py --continuous`；再次点击会停止语音助手进程。
- 语音页在监听、识别、思考或执行时显示轻量三点动画。
- 当输入文件包含 `debug.client.elapsed_ms` 和 `debug.model_results` 时，HMI 会展示云端响应延迟和模型来源。
- 点击右上角“模型详情”可查看 `/api/evaluate` 返回的调试信息，包括云端请求、模型路由、本地规则、各模型输出和仲裁结果。
- 报警/预警会写入报警日志。

## 模型详情

模型详情弹窗依赖 `cloud_client.py --include-debug` 写出的完整响应。推荐板端联调命令：

```bash
python3 app_2k1000la/cloud_client.py \
  --scenario-file tests/scenarios/evaluate/gas_alarm.json \
  --output-file runtime/latest_evaluate_response.json \
  --include-debug \
  --loop \
  --interval 2
```

HMI 读取同一个输出文件：

```bash
./build_qmake/display_qt_app --fullscreen --status-file runtime/latest_evaluate_response.json
```

## 小屏和双屏显示

板端如果同时接了 800x480 小屏和 HDMI，X11 可能把两个屏幕拼成一个大桌面。可显式指定屏幕和窗口尺寸：

```bash
./build_qmake/display_qt_app \
  --compact \
  --screen DPI-1 \
  --geometry 780x450+10+10 \
  --status-file runtime/latest_evaluate_response.json \
  --voice-file runtime/voice_assistant_state.json
```

说明：

- `--compact`：降低字号、间距和日志区高度，适配 800x480。
- `--screen DPI-1`：优先把窗口放到板载小屏；HDMI 通常是 `HDMI-1`。
- `--geometry 780x450+10+10`：窗口模式；如果窗口管理器支持，才可以拖拽。
- `--fullscreen` 是展台/锁屏模式，窗口不能拖拽，属于正常现象。
- 800x480 小屏展示建议优先使用 `--compact --fullscreen`；如果需要窗口模式，可尝试 `--geometry 760x430+5+5`。

## 语音助手显示

HMI 既可以读取外部启动的语音助手状态，也可以自行启动语音监听。默认情况下，Qt 启动后会自动拉起语音助手；右上角“启动语音/停止语音”按钮可手动控制。若只想手动启动，可在启动 Qt 前设置 `VOICE_AUTOSTART=false`。Qt 启动语音时会：

- 从仓库根目录运行 `voice_llm_demo/main.py --continuous`。
- 读取 `voice_llm_demo/.env` 中的 `ASR_MODE`、ASR 密钥、`VOICE_LLM_PROVIDER` 和各模型密钥。
- 写入 `runtime/voice_assistant_state.json`，供界面实时显示。
- 设置 `ASR_FALLBACK_MANUAL=false`，避免 GUI 非交互模式下 ASR 失败后卡在手动输入。
- 默认启用唤醒词与百度 TTS 播报；推荐唤醒词：`小龙`、`你好小龙`、`龙芯助手`、`小龙在吗`、`在吗`。
- 单独说出唤醒词后，会打开 `VOICE_WAKE_WINDOW_SECONDS` 秒唤醒窗口，窗口内下一句话无需重复唤醒词。
- 每次回答完成后会继续延长追问窗口，超过窗口时间未继续说话才回到待唤醒。

如果程序不是从仓库目录启动，可指定根目录：

```bash
export XYLT_REPO_ROOT=/home/xylt/xylt
```

手动启动语音助手进程的等价命令：

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

HMI 启动时读取同一个状态文件：

```bash
./display_qt_app \
  --compact \
  --geometry 780x450+10+10 \
  --status-file /home/xylt/xylt/runtime/latest_evaluate_response.json \
  --voice-file /home/xylt/xylt/runtime/voice_assistant_state.json
```

状态文件字段包括 `state`、`last_user_text`、`last_reply`、`last_intent`、`execute_message`、`llm_provider` 和最近问答历史。
