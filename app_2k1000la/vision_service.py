from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import os
import shutil
import sys
import threading
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
DEFAULT_CAPTURE_REQUEST_FILE = DEFAULT_OUTPUT_DIR / "capture_request.json"
DEFAULT_LIVE_IMAGE_FILE = DEFAULT_OUTPUT_DIR / "live.jpg"
DEFAULT_ARCHIVE_DIR = Path("/media/xylt/0403-0201/xylt_vision_archive")
DEFAULT_PERIODIC_UPLOAD_SECONDS = 300.0
DEFAULT_TRIGGER_MIN_INTERVAL_SECONDS = 30.0
DEFAULT_PREVIEW_INTERVAL_SECONDS = 0.8
DEFAULT_ARCHIVE_MAX_AGE_DAYS = 7.0
DEFAULT_ARCHIVE_MAX_BYTES = 1_073_741_824
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


def read_capture_request(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    request_id = str(data.get("request_id") or data.get("id") or "").strip()
    if not request_id:
        request_id = str(data.get("created_at") or path.stat().st_mtime_ns)
    trigger = str(data.get("trigger") or "manual").strip() or "manual"
    return {
        "request_id": request_id,
        "trigger": trigger,
        "question": str(data.get("question") or ""),
        "force": bool(data.get("force")),
        "created_at": str(data.get("created_at") or ""),
    }


def initial_capture_request_id(path: Path) -> str:
    request = read_capture_request(path)
    return str(request["request_id"]) if request else ""


def sanitize_name_part(value: str, default: str = "capture") -> str:
    text = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(value or ""))
    text = text.strip("_")
    return (text or default)[:48]


def prune_archive(archive_dir: Path, max_age_days: float, max_bytes: int) -> dict[str, int]:
    if not archive_dir.exists() or max_age_days <= 0 and max_bytes <= 0:
        return {"archive_pruned_files": 0, "archive_pruned_bytes": 0}

    now = time.time()
    max_age_seconds = max_age_days * 86400.0
    files: list[tuple[float, int, Path]] = []
    pruned_files = 0
    pruned_bytes = 0

    for path in archive_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        if max_age_days > 0 and now - stat.st_mtime > max_age_seconds:
            try:
                size = stat.st_size
                path.unlink()
                pruned_files += 1
                pruned_bytes += size
            except OSError:
                pass
            continue
        files.append((stat.st_mtime, stat.st_size, path))

    if max_bytes > 0:
        total_bytes = sum(size for _, size, _ in files)
        for _, size, path in sorted(files, key=lambda item: item[0]):
            if total_bytes <= max_bytes:
                break
            try:
                path.unlink()
                total_bytes -= size
                pruned_files += 1
                pruned_bytes += size
            except OSError:
                pass

    return {"archive_pruned_files": pruned_files, "archive_pruned_bytes": pruned_bytes}


def error_status(
    mode: str,
    backend: str,
    message: str,
    image_path: Path | None = None,
    elapsed_ms: int = 0,
    trigger: str = "manual",
    request_id: str = "",
    camera_online: bool = False,
) -> dict[str, Any]:
    return {
        "vision_status": {
            "device_id": "board_2k1000la",
            "timestamp": now_text(),
            "mode": mode,
            "trigger": trigger,
            "request_id": request_id,
            "backend": backend,
            "camera_online": camera_online,
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
        self._lock = threading.RLock()

    def open(self) -> None:
        with self._lock:
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
        with self._lock:
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
        with self._lock:
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
        self.live_image_path = Path(args.live_image_file)
        self.state_path = self.output_dir / "vision_state.json"
        self.mode_file = Path(args.mode_file)
        self.capture_request_file = Path(args.capture_request_file)
        self.archive_dir = Path(args.archive_dir)
        self.camera = CameraSource(args.camera_index, args.width, args.height, args.test_image)
        self.local_runner = LocalYoloRunner(args.local_vision_dir)
        self.last_request_id = initial_capture_request_id(self.capture_request_file)
        self.last_capture_monotonic = 0.0
        self.next_periodic_at = time.monotonic() + max(0.0, float(args.periodic_upload_seconds))
        self.last_state: dict[str, Any] | None = None
        self.last_preview_monotonic = 0.0
        self.analysis_thread: threading.Thread | None = None

    def run_once(self, trigger: str = "manual", request_id: str = "", question: str = "") -> dict[str, Any]:
        started = time.time()
        mode = self.current_mode()
        if mode == "off":
            self.camera.release()
            state = error_status("off", "off", "视觉模块已关闭。", trigger=trigger, request_id=request_id)
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
            state["vision_status"].update({"trigger": trigger, "request_id": request_id})
            self.write_state(state)
            return state

        if mode == "local":
            state = self.local_runner.evaluate(frame, self.image_path, started, trigger=trigger, request_id=request_id)
            if question:
                state.setdefault("vision_status", {})["capture_question"] = question
            self.write_state(state)
            return state

        state = self.evaluate_cloud(image_bytes, started, trigger=trigger, request_id=request_id, question=question)
        self.write_state(state)
        return state

    def run_forever(self) -> None:
        print(
            "vision_loop "
            f"periodic_upload_seconds={self.args.periodic_upload_seconds} "
            f"capture_request_file={self.capture_request_file} "
            f"live_image_file={self.live_image_path} "
            f"archive_dir={self.archive_dir if not self.args.no_archive else 'disabled'}"
        )
        while True:
            self.update_live_preview()
            state = self.maybe_run_due_capture()
            if state is not None:
                print_state(state)
            time.sleep(max(0.2, self.args.interval))

    def update_live_preview(self) -> None:
        if self.args.preview_interval <= 0:
            return
        now = time.monotonic()
        if now - self.last_preview_monotonic < self.args.preview_interval:
            return
        self.last_preview_monotonic = now

        mode = self.current_mode()
        if mode == "off":
            self.camera.release()
            return
        try:
            self.camera.open()
            frame = self.camera.read()
            encode_jpeg(frame, self.live_image_path, self.args.preview_jpeg_quality)
        except Exception as exc:  # noqa: BLE001 - live preview must not kill the resident service.
            if self.last_state is None:
                state = error_status(mode, "camera", f"实时预览失败: {exc}")
                self.write_state(state)

    def maybe_run_due_capture(self) -> dict[str, Any] | None:
        now = time.monotonic()
        request = read_capture_request(self.capture_request_file)
        if request and request["request_id"] != self.last_request_id:
            if self.analysis_thread is not None and self.analysis_thread.is_alive():
                return None
            force = bool(request.get("force"))
            can_capture = force or now - self.last_capture_monotonic >= self.args.trigger_min_interval_seconds
            self.last_request_id = str(request["request_id"])
            if can_capture:
                if not self.start_analysis(
                    trigger=str(request.get("trigger") or "manual"),
                    request_id=str(request.get("request_id") or ""),
                    question=str(request.get("question") or ""),
                ):
                    return None
                self._mark_capture_done(now)
                return None
            if self.last_state is not None:
                status = self.last_state.setdefault("vision_status", {})
                status["reused_from_request_id"] = status.get("request_id", "")
                status["request_id"] = request["request_id"]
                status["trigger"] = request.get("trigger") or status.get("trigger") or "manual"
                if request.get("question"):
                    status["capture_question"] = request["question"]
                status["reused_reason"] = "30 秒内已有视觉结果，复用最近一次抓拍。"
                self.write_state(self.last_state)
                return self.last_state

        if self.args.periodic_upload_seconds > 0 and now >= self.next_periodic_at:
            if self.analysis_thread is not None and self.analysis_thread.is_alive():
                return None
            request_id = f"periodic-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            if not self.start_analysis(trigger="periodic", request_id=request_id):
                return None
            self._mark_capture_done(now)
            return None
        return None

    def start_analysis(self, trigger: str, request_id: str, question: str = "") -> bool:
        if self.analysis_thread is not None and self.analysis_thread.is_alive():
            return False
        self.write_processing_state(trigger=trigger, request_id=request_id, question=question)
        self.analysis_thread = threading.Thread(
            target=self._analysis_worker,
            args=(trigger, request_id, question),
            daemon=True,
        )
        self.analysis_thread.start()
        return True

    def write_processing_state(self, trigger: str, request_id: str, question: str = "") -> None:
        state = {
            "vision_status": {
                "device_id": "board_2k1000la",
                "timestamp": now_text(),
                "mode": self.current_mode(),
                "trigger": trigger,
                "request_id": request_id,
                "backend": "pending",
                "camera_online": True,
                "person_detected": None,
                "helmet_detected": None,
                "mask_detected": None,
                "reflective_vest_detected": None,
                "fire_detected": None,
                "ppe_status": "processing",
                "missing_ppe": [],
                "summary": "已收到拍照检测请求，正在抓拍并调用视觉模型。",
                "confidence": 0.0,
                "detections": [],
                "latency_ms": 0,
                "image_available": False,
                "image_path": "",
                "live_image_path": str(self.live_image_path if self.live_image_path.exists() else ""),
                "error": "",
            }
        }
        if question:
            state["vision_status"]["capture_question"] = question
        write_json_atomic(self.state_path, state)
        self.last_state = state

    def _analysis_worker(self, trigger: str, request_id: str, question: str) -> None:
        state = self.run_once(trigger=trigger, request_id=request_id, question=question)
        print_state(state)

    def _mark_capture_done(self, now: float) -> None:
        self.last_capture_monotonic = now
        if self.args.periodic_upload_seconds > 0:
            self.next_periodic_at = now + self.args.periodic_upload_seconds

    def current_mode(self) -> str:
        mode = self.args.mode
        if self.args.follow_cloud_mode:
            mode = fetch_cloud_mode(self.base_url, self.args.timeout, mode)
        # Board-local mode requests come from Qt and must win over the cloud
        # default; otherwise the Qt "local" button can be silently overridden.
        mode = read_mode_file(self.mode_file, mode)
        return mode if mode in {"cloud", "local", "off"} else "cloud"

    def evaluate_cloud(self, image_bytes: bytes, started: float, trigger: str, request_id: str, question: str = "") -> dict[str, Any]:
        payload = {
            "device_id": "board_2k1000la",
            "timestamp": now_text(),
            "image_base64": base64.b64encode(image_bytes).decode("ascii"),
            "image_mime": "image/jpeg",
            "mode": "cloud",
            "trigger": trigger,
            "request_id": request_id,
            "sensor_snapshot": load_sensor_snapshot(Path(self.args.sensor_snapshot_file)),
            "include_debug": self.args.include_debug,
        }
        try:
            state = request_json(self.base_url, "/api/vision/evaluate", payload, timeout=self.args.timeout)
            status = state.setdefault("vision_status", {})
            status.setdefault("image_path", str(self.image_path))
            status.setdefault("latency_ms", int((time.time() - started) * 1000))
            status.setdefault("trigger", trigger)
            status.setdefault("request_id", request_id)
            if question:
                status["capture_question"] = question
            status["image_available"] = True
            return state
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            return error_status(
                "cloud",
                "safecloud",
                f"SafeCloud 视觉请求失败: {exc}",
                image_path=self.image_path,
                elapsed_ms=int((time.time() - started) * 1000),
                trigger=trigger,
                request_id=request_id,
                camera_online=True,
            )

    def write_state(self, state: dict[str, Any]) -> None:
        status = state.setdefault("vision_status", {})
        status.setdefault("image_path", str(self.image_path if self.image_path.exists() else ""))
        status["live_image_path"] = str(self.live_image_path if self.live_image_path.exists() else "")
        if not self.args.no_archive:
            status.update(
                archive_capture(
                    state,
                    self.image_path,
                    self.archive_dir,
                    self.args.archive_max_age_days,
                    self.args.archive_max_bytes,
                )
            )
        write_json_atomic(self.state_path, state)
        self.last_state = state


def archive_capture(
    state: dict[str, Any],
    image_path: Path,
    archive_dir: Path,
    max_age_days: float,
    max_bytes: int,
) -> dict[str, Any]:
    status = state.setdefault("vision_status", {})
    result: dict[str, Any] = {
        "archive_dir": str(archive_dir),
        "archive_image_path": "",
        "archive_state_path": "",
        "archive_pruned_files": 0,
        "archive_pruned_bytes": 0,
    }
    try:
        archive_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now()
        day_dir = archive_dir / timestamp.strftime("%Y%m%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        trigger = sanitize_name_part(str(status.get("trigger") or "capture"))
        request_id = sanitize_name_part(str(status.get("request_id") or timestamp.strftime("%H%M%S")))
        stem = f"{timestamp.strftime('%H%M%S')}_{trigger}_{request_id}"

        if image_path.exists():
            archived_image = day_dir / f"{stem}.jpg"
            shutil.copy2(image_path, archived_image)
            result["archive_image_path"] = str(archived_image)

        archived_state = day_dir / f"{stem}.json"
        write_json_atomic(archived_state, state)
        result["archive_state_path"] = str(archived_state)
        result.update(prune_archive(archive_dir, max_age_days, max_bytes))
    except OSError as exc:
        result["archive_error"] = str(exc)
    return result


def print_state(state: dict[str, Any]) -> None:
    status = state.get("vision_status", {})
    print(
        "vision_result "
        f"mode={status.get('mode')} "
        f"trigger={status.get('trigger')} "
        f"request_id={status.get('request_id')} "
        f"backend={status.get('backend')} "
        f"ppe={status.get('ppe_status')} "
        f"camera={status.get('camera_online')} "
        f"latency_ms={status.get('latency_ms')} "
        f"error={status.get('error', '')}"
    )


class LocalYoloRunner:
    def __init__(self, local_vision_dir: str) -> None:
        self.local_vision_dir = local_vision_dir
        self._module = None

    def evaluate(self, frame: Any, image_path: Path, started: float, trigger: str = "manual", request_id: str = "") -> dict[str, Any]:
        try:
            module = self._load_module()
            result = module.check_frame(frame)
            return normalize_local_yolo_result(result, image_path, started, trigger=trigger, request_id=request_id)
        except Exception as exc:  # noqa: BLE001
            return error_status(
                "local",
                "local_yolo",
                f"本地 YOLO 推理失败: {exc}",
                image_path=image_path,
                elapsed_ms=int((time.time() - started) * 1000),
                trigger=trigger,
                request_id=request_id,
                camera_online=True,
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


def normalize_local_yolo_result(
    result: dict[str, Any],
    image_path: Path,
    started: float,
    trigger: str = "manual",
    request_id: str = "",
) -> dict[str, Any]:
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
    raw_status = str(result.get("status") or "").lower()
    if raw_status == "pass":
        ppe_status = "pass"
    elif raw_status == "fail" or missing:
        ppe_status = "fail"
    else:
        ppe_status = "unknown"
    return {
        "vision_status": {
            "device_id": "board_2k1000la",
            "timestamp": now_text(),
            "mode": "local",
            "trigger": trigger,
            "request_id": request_id,
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
    parser.add_argument("--width", type=int, default=480)
    parser.add_argument("--height", type=int, default=270)
    parser.add_argument("--jpeg-quality", type=int, default=58)
    parser.add_argument("--mode", default=os.environ.get("XYLT_VISION_MODE", "cloud"), choices=["cloud", "local", "off"])
    parser.add_argument("--mode-file", default=str(DEFAULT_MODE_FILE))
    parser.add_argument("--follow-cloud-mode", action="store_true")
    parser.add_argument("--local-vision-dir", default="")
    parser.add_argument("--sensor-snapshot-file", default=str(REPO_ROOT / "runtime" / "latest_evaluate_response.json"))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--live-image-file", default=str(DEFAULT_LIVE_IMAGE_FILE))
    parser.add_argument("--capture-request-file", default=str(DEFAULT_CAPTURE_REQUEST_FILE))
    parser.add_argument("--archive-dir", default=str(DEFAULT_ARCHIVE_DIR))
    parser.add_argument("--archive-max-age-days", type=float, default=DEFAULT_ARCHIVE_MAX_AGE_DAYS)
    parser.add_argument("--archive-max-bytes", type=int, default=DEFAULT_ARCHIVE_MAX_BYTES)
    parser.add_argument("--no-archive", action="store_true")
    parser.add_argument("--periodic-upload-seconds", type=float, default=DEFAULT_PERIODIC_UPLOAD_SECONDS)
    parser.add_argument("--trigger-min-interval-seconds", type=float, default=DEFAULT_TRIGGER_MIN_INTERVAL_SECONDS)
    parser.add_argument("--preview-interval", type=float, default=DEFAULT_PREVIEW_INTERVAL_SECONDS)
    parser.add_argument("--preview-jpeg-quality", type=int, default=45)
    parser.add_argument("--interval", type=float, default=0.2, help="Loop polling interval in seconds.")
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
    if args.loop:
        loop.run_forever()
        return
    while True:
        state = loop.run_once()
        print_state(state)
        if not args.loop:
            break
        time.sleep(max(1.0, args.interval))


if __name__ == "__main__":
    main()
