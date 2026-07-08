from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app_2k1000la.cloud_client import DEFAULT_BASE_URL, default_cache_file, resolve_base_url


DEFAULT_OUTPUT_DIR = REPO_ROOT / "runtime" / "vision"
DEFAULT_MODE_FILE = DEFAULT_OUTPUT_DIR / "mode_request.json"
DEFAULT_LOCAL_VISION_DIRS = [
    REPO_ROOT / "loongson-safety-vision",
    REPO_ROOT / "vision" / "loongson-safety-vision",
]


def now_text() -> str:
    return datetime.now().isoformat(timespec="seconds")


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def request_json(base_url: str, path: str, payload: Optional[dict[str, Any]] = None, timeout: float = 30.0) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def read_mode_file(path: Path, fallback: str) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        mode = str(data.get("mode", "")).strip().lower()
        if mode in {"cloud", "local", "off"}:
            return mode
    except (OSError, json.JSONDecodeError):
        pass
    return fallback


def fetch_cloud_mode(base_url: str, timeout: float, fallback: str) -> str:
    try:
        data = request_json(base_url, "/api/vision/mode", timeout=timeout)
        mode = str(data.get("mode", "")).strip().lower()
        if mode in {"cloud", "local", "off"}:
            return mode
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        pass
    return fallback


def error_status(mode: str, backend: str, message: str, image_path: Path | None = None, elapsed_ms: int = 0) -> dict[str, Any]:
    return {
        "vision_status": {
            "device_id": "board_2k1000la",
            "timestamp": now_text(),
            "mode": mode,
            "backend": backend,
            "camera_online": False,
            "person_detected": False,
            "helmet_detected": None,
            "mask_detected": None,
            "reflective_vest_detected": None,
            "fire_detected": False,
            "ppe_status": "error",
            "missing_ppe": [],
            "summary": message,
            "confidence": 0.0,
            "detections": [],
            "latency_ms": elapsed_ms,
            "image_available": image_path is not None,
            "image_path": str(image_path) if image_path else "",
            "error": message,
        }
    }


class CameraSource:
    def __init__(self, camera_index: int, width: int, height: int, test_image: str = "") -> None:
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.test_image = test_image
        self._cv2 = None
        self._capture = None

    def open(self) -> None:
        if self.test_image:
            self._ensure_cv2()
            return
        if self._capture is not None:
            return
        cv2 = self._ensure_cv2()
        capture = cv2.VideoCapture(self.camera_index)
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"无法打开 USB 摄像头 index={self.camera_index}")
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._capture = capture

    def read(self) -> Any:
        cv2 = self._ensure_cv2()
        if self.test_image:
            frame = cv2.imread(self.test_image)
            if frame is None:
                raise RuntimeError(f"无法读取测试图片: {self.test_image}")
            return frame
        self.open()
        ok, frame = self._capture.read()
        if not ok or frame is None:
            raise RuntimeError("摄像头读取失败")
        return frame

    def release(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def _ensure_cv2(self) -> Any:
        if self._cv2 is not None:
            return self._cv2
        try:
            import cv2  # type: ignore
        except ImportError as exc:
            raise RuntimeError("缺少 OpenCV，请在板端安装 python3-opencv 或 opencv-python") from exc
        self._cv2 = cv2
        return self._cv2


class VisionLoop:
    def __init__(self, args: argparse.Namespace, base_url: str) -> None:
        self.args = args
        self.base_url = base_url
        self.output_dir = Path(args.output_dir)
        self.image_path = self.output_dir / "latest.jpg"
        self.state_path = self.output_dir / "vision_state.json"
        self.mode_file = Path(args.mode_file)
        self.camera = CameraSource(args.camera_index, args.width, args.height, args.test_image)
        self.local_runner = LocalYoloRunner(args.local_vision_dir)

    def run_once(self) -> dict[str, Any]:
        started = time.time()
        mode = self.current_mode()
        if mode == "off":
            self.camera.release()
            state = error_status("off", "off", "视觉模块已关闭。")
            state["vision_status"].update({"ppe_status": "unknown", "error": "", "camera_online": False})
            self.write_state(state)
            return state

        try:
            self.camera.open()
            frame = self.camera.read()
            image_bytes = encode_jpeg(frame, self.image_path, self.args.jpeg_quality)
        except Exception as exc:  # noqa: BLE001 - resident process writes a state file instead of crashing.
            self.camera.release()
            state = error_status(mode, "camera", str(exc), elapsed_ms=int((time.time() - started) * 1000))
            self.write_state(state)
            return state

        if mode == "local":
            state = self.local_runner.evaluate(frame, self.image_path, started)
            self.write_state(state)
            return state

        state = self.evaluate_cloud(image_bytes, started)
        self.write_state(state)
        return state

    def current_mode(self) -> str:
        mode = self.args.mode
        mode = read_mode_file(self.mode_file, mode)
        if self.args.follow_cloud_mode:
            mode = fetch_cloud_mode(self.base_url, self.args.timeout, mode)
        return mode if mode in {"cloud", "local", "off"} else "cloud"

    def evaluate_cloud(self, image_bytes: bytes, started: float) -> dict[str, Any]:
        payload = {
            "device_id": "board_2k1000la",
            "timestamp": now_text(),
            "image_base64": base64.b64encode(image_bytes).decode("ascii"),
            "image_mime": "image/jpeg",
            "mode": "cloud",
            "sensor_snapshot": load_sensor_snapshot(Path(self.args.sensor_snapshot_file)),
            "include_debug": self.args.include_debug,
        }
        try:
            state = request_json(self.base_url, "/api/vision/evaluate", payload, timeout=self.args.timeout)
            status = state.setdefault("vision_status", {})
            status.setdefault("image_path", str(self.image_path))
            status.setdefault("latency_ms", int((time.time() - started) * 1000))
            status["image_available"] = True
            return state
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            return error_status(
                "cloud",
                "safecloud",
                f"SafeCloud 视觉请求失败: {exc}",
                image_path=self.image_path,
                elapsed_ms=int((time.time() - started) * 1000),
            )

    def write_state(self, state: dict[str, Any]) -> None:
        status = state.setdefault("vision_status", {})
        status.setdefault("image_path", str(self.image_path if self.image_path.exists() else ""))
        write_json_atomic(self.state_path, state)


class LocalYoloRunner:
    def __init__(self, local_vision_dir: str) -> None:
        self.local_vision_dir = local_vision_dir
        self._module = None

    def evaluate(self, frame: Any, image_path: Path, started: float) -> dict[str, Any]:
        try:
            module = self._load_module()
            result = module.check_frame(frame)
            return normalize_local_yolo_result(result, image_path, started)
        except Exception as exc:  # noqa: BLE001
            return error_status(
                "local",
                "local_yolo",
                f"本地 YOLO 推理失败: {exc}",
                image_path=image_path,
                elapsed_ms=int((time.time() - started) * 1000),
            )

    def _load_module(self) -> Any:
        if self._module is not None:
            return self._module
        repo_dir = self._resolve_repo_dir()
        script = repo_dir / "safety_check.py"
        if not script.exists():
            script = repo_dir / "src" / "safety_check.py"
        if not script.exists():
            raise RuntimeError(f"未找到 safety_check.py: {repo_dir}")

        spec = importlib.util.spec_from_file_location("loongson_safety_check", script)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"无法加载 safety_check.py: {script}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        module.DETECT_BIN = str(first_existing([
            repo_dir / "yolo_detect",
            repo_dir / "build" / "yolo_detect",
            repo_dir / "build" / "src" / "yolo_detect",
        ]))
        module.PARAM = str(first_existing([
            repo_dir / "best320_opt.param",
            repo_dir / "models" / "best320_opt.param",
        ]))
        module.BIN = str(first_existing([
            repo_dir / "best320_opt.bin",
            repo_dir / "models" / "best320_opt.bin",
        ]))
        self._module = module
        return module

    def _resolve_repo_dir(self) -> Path:
        candidates = []
        if self.local_vision_dir:
            candidates.append(Path(self.local_vision_dir))
        env_dir = os.environ.get("LOONGSON_SAFETY_VISION_DIR", "").strip()
        if env_dir:
            candidates.append(Path(env_dir))
        candidates.extend(DEFAULT_LOCAL_VISION_DIRS)
        for path in candidates:
            if path.exists():
                return path
        raise RuntimeError("未找到 loongson-safety-vision 目录，请设置 LOONGSON_SAFETY_VISION_DIR")


def encode_jpeg(frame: Any, image_path: Path, quality: int) -> bytes:
    import cv2  # type: ignore

    quality = max(30, min(95, int(quality)))
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("JPEG 编码失败")
    image_bytes = encoded.tobytes()
    image_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = image_path.with_suffix(".jpg.tmp")
    tmp_path.write_bytes(image_bytes)
    tmp_path.replace(image_path)
    return image_bytes


def normalize_local_yolo_result(result: dict[str, Any], image_path: Path, started: float) -> dict[str, Any]:
    detections = result.get("detections") if isinstance(result.get("detections"), list) else []
    labels = {str(item.get("name") or item.get("label") or "").lower() for item in detections if isinstance(item, dict)}
    person = "person" in labels
    helmet = "helmet" in labels if person else None
    mask = "mask" in labels if person else None
    vest = "vest" in labels if person else None
    missing = []
    raw_missing = result.get("missing") if isinstance(result.get("missing"), list) else []
    for item in raw_missing:
        text = str(item)
        if "helmet" in text or "安全帽" in text:
            missing.append("安全帽")
        elif "mask" in text or "口罩" in text:
            missing.append("口罩")
        elif "vest" in text or "反光" in text:
            missing.append("反光背心")
        else:
            missing.append(text)
    missing = list(dict.fromkeys(missing))
    ppe_status = "pass" if result.get("status") == "pass" else "fail" if person else "unknown"
    return {
        "vision_status": {
            "device_id": "board_2k1000la",
            "timestamp": now_text(),
            "mode": "local",
            "backend": "local_yolo_ncnn",
            "camera_online": True,
            "person_detected": person,
            "helmet_detected": helmet,
            "mask_detected": mask,
            "reflective_vest_detected": vest,
            "fire_detected": "fire" in labels or "flame" in labels,
            "ppe_status": ppe_status,
            "missing_ppe": missing,
            "summary": str(result.get("summary") or ("本地视觉检测正常" if ppe_status == "pass" else "本地视觉检测发现防护风险")),
            "confidence": max((float(item.get("prob", item.get("confidence", 0.0))) for item in detections if isinstance(item, dict)), default=0.0),
            "detections": detections,
            "latency_ms": int((time.time() - started) * 1000),
            "image_available": True,
            "image_path": str(image_path),
            "error": "",
        }
    }


def first_existing(paths: list[Path]) -> Path:
    for path in paths:
        if path.exists():
            return path
    raise RuntimeError("缺少本地 YOLO 文件: " + ", ".join(str(path) for path in paths))


def load_sensor_snapshot(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        status = data.get("final_status") if isinstance(data, dict) else None
        if isinstance(status, dict):
            return status.get("sensor_metrics") or status
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="2K1000LA USB camera vision bridge")
    parser.add_argument("--base-url", default="", help="Manual SafeCloud base URL. Empty enables cache/discovery.")
    parser.add_argument("--cache-file", default=default_cache_file())
    parser.add_argument("--discovery-port", type=int, default=int(os.environ.get("SAFECLOUD_DISCOVERY_PORT", "8011")))
    parser.add_argument("--discovery-timeout", type=float, default=3.0)
    parser.add_argument("--no-discovery", action="store_true")
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--test-image", default="", help="Use an image file instead of USB camera for smoke tests.")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=360)
    parser.add_argument("--jpeg-quality", type=int, default=72)
    parser.add_argument("--mode", default=os.environ.get("XYLT_VISION_MODE", "cloud"), choices=["cloud", "local", "off"])
    parser.add_argument("--mode-file", default=str(DEFAULT_MODE_FILE))
    parser.add_argument("--follow-cloud-mode", action="store_true")
    parser.add_argument("--local-vision-dir", default="")
    parser.add_argument("--sensor-snapshot-file", default=str(REPO_ROOT / "runtime" / "latest_evaluate_response.json"))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--include-debug", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_url, source = resolve_base_url(
        args.base_url or DEFAULT_BASE_URL,
        args.cache_file,
        args.discovery_port,
        args.discovery_timeout,
        args.no_discovery,
    )
    print(f"vision_safecloud_base_url={base_url} source={source}")
    loop = VisionLoop(args, base_url)
    while True:
        state = loop.run_once()
        status = state.get("vision_status", {})
        print(
            "vision_result "
            f"mode={status.get('mode')} "
            f"backend={status.get('backend')} "
            f"ppe={status.get('ppe_status')} "
            f"camera={status.get('camera_online')} "
            f"latency_ms={status.get('latency_ms')} "
            f"error={status.get('error', '')}"
        )
        if not args.loop:
            break
        time.sleep(max(1.0, args.interval))


if __name__ == "__main__":
    main()
