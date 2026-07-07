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
    "voice_text": "当前设备处于报警状态。"
  }
}
```

或直接是 `final_status` 对象，HMI 都可以解析。

## 显示内容

- 温度、湿度、气体、振动、云端状态、系统状态。
- `reason` 和 `suggestion` 显示在中部信息区。
- `voice_text` 在底部状态栏展示，后续可与语音播报模块联动。
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
  --status-file runtime/latest_evaluate_response.json
```

说明：

- `--compact`：降低字号、间距和日志区高度，适配 800x480。
- `--screen DPI-1`：优先把窗口放到板载小屏；HDMI 通常是 `HDMI-1`。
- `--geometry 780x450+10+10`：窗口模式，可拖拽；不要同时加 `--fullscreen`。
- `--fullscreen` 是展台/锁屏模式，窗口不能拖拽，属于正常现象。
