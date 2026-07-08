# vision

## USB 摄像头视觉安全评估

当前视觉模块采用“云端优先、本地兜底、互斥运行”的方式：

- `cloud`：2K1000LA 只抓取 USB 摄像头关键帧并压缩为 JPEG，上传到 SafeCloud，由豆包视觉模型判断人员、安全帽、口罩、反光背心和火焰风险。
- `local`：在 2K1000LA 本地调用 `loongson-safety-vision` 的 YOLO/NCNN 推理脚本。该模式占用内存较高，只在需要断网兜底或现场演示本地推理时启用。
- `off`：关闭视觉分析并释放摄像头/推理资源。

板端服务文件：

```bash
python3 app_2k1000la/vision_service.py --help
```

云端模式示例：

```bash
python3 app_2k1000la/vision_service.py \
  --base-url http://<SafeCloud主机IP>:8010 \
  --camera-index 0 \
  --mode cloud \
  --output-dir runtime/vision \
  --loop \
  --interval 5 \
  --include-debug
```

本地 YOLO 模式示例：

```bash
export LOONGSON_SAFETY_VISION_DIR=$HOME/loongson-safety-vision
python3 app_2k1000la/vision_service.py \
  --camera-index 0 \
  --mode local \
  --output-dir runtime/vision \
  --loop \
  --interval 5
```

如果需要从网页切换模式，板端视觉服务启动时加：

```bash
python3 app_2k1000la/vision_service.py --follow-cloud-mode --loop
```

输出文件：

- `runtime/vision/latest.jpg`：最新关键帧，供 Qt HMI 展示。
- `runtime/vision/vision_state.json`：最新视觉评估结果，供 Qt HMI 轮询。
- `runtime/vision/mode_request.json`：Qt HMI 写入的模式切换请求。

本地 YOLO 依赖：

- 需要 OpenCV：板端优先使用 `sudo apt install python3-opencv`。
- 需要克隆并编译 `loongson-safety-vision`，保证目录中存在 `safety_check.py`、`yolo_detect`、`best320_opt.param`、`best320_opt.bin`。
- 云端和本地不要同时跑；服务每一轮只执行当前模式，`off` 会释放摄像头句柄。

摄像头与视觉识别模块目录。

当前仅保留工程框架：

- `src/`：视觉处理代码。
- `models/`：模型文件。
- `test_images/`：测试图片。

后续实现人员、安全帽、火焰等识别能力，并以 mock 数据支持独立测试。
