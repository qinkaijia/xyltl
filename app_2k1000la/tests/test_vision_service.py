import time
from pathlib import Path

from app_2k1000la.vision_service import (
    archive_capture,
    initial_capture_request_id,
    normalize_local_yolo_result,
    read_capture_request,
    read_mode_file,
    VisionLoop,
)


def test_normalize_local_yolo_result_maps_ppe_fields(tmp_path: Path):
    image_path = tmp_path / "latest.jpg"
    result = {
        "status": "fail",
        "missing": ["mask"],
        "summary": "missing mask",
        "detections": [
            {"name": "person", "prob": 0.92},
            {"name": "helmet", "prob": 0.88},
            {"name": "vest", "prob": 0.81},
        ],
    }

    state = normalize_local_yolo_result(result, image_path, time.time())
    status = state["vision_status"]

    assert status["mode"] == "local"
    assert status["backend"] == "local_yolo_ncnn"
    assert status["person_detected"] is True
    assert status["helmet_detected"] is True
    assert status["mask_detected"] is False
    assert status["reflective_vest_detected"] is True
    assert status["missing_ppe"] == ["口罩"]


def test_normalize_local_yolo_result_keeps_fail_without_person(tmp_path: Path):
    image_path = tmp_path / "latest.jpg"
    result = {
        "status": "fail",
        "missing": ["安全帽", "口罩"],
        "summary": "不合格：缺安全帽、口罩",
        "detections": [],
    }

    state = normalize_local_yolo_result(result, image_path, time.time())
    status = state["vision_status"]

    assert status["person_detected"] is False
    assert status["ppe_status"] == "fail"
    assert status["missing_ppe"] == ["安全帽", "口罩"]


def test_read_mode_file_uses_valid_mode_only(tmp_path: Path):
    mode_file = tmp_path / "mode_request.json"
    mode_file.write_text('{"mode":"off"}', encoding="utf-8")
    assert read_mode_file(mode_file, "cloud") == "off"

    mode_file.write_text('{"mode":"bad"}', encoding="utf-8")
    assert read_mode_file(mode_file, "cloud") == "cloud"


def test_current_mode_prefers_board_local_request(tmp_path: Path, monkeypatch):
    mode_file = tmp_path / "mode_request.json"
    mode_file.write_text('{"mode":"local"}', encoding="utf-8")
    args = type(
        "Args",
        (),
        {
            "output_dir": str(tmp_path),
            "live_image_file": str(tmp_path / "live.jpg"),
            "mode_file": str(mode_file),
            "capture_request_file": str(tmp_path / "capture_request.json"),
            "archive_dir": str(tmp_path / "archive"),
            "camera_index": 0,
            "width": 320,
            "height": 180,
            "test_image": "",
            "local_vision_dir": "",
            "mode": "cloud",
            "follow_cloud_mode": True,
            "timeout": 1.0,
            "periodic_upload_seconds": 300.0,
        },
    )()
    monkeypatch.setattr("app_2k1000la.vision_service.fetch_cloud_mode", lambda *args: "cloud")

    loop = VisionLoop(args, "http://safecloud.local")

    assert loop.current_mode() == "local"


def test_read_capture_request_normalizes_request(tmp_path: Path):
    request_file = tmp_path / "capture_request.json"
    request_file.write_text(
        '{"request_id":"req-1","trigger":"voice","question":"现在穿戴规范吗","force":true}',
        encoding="utf-8",
    )

    request = read_capture_request(request_file)

    assert request is not None
    assert request["request_id"] == "req-1"
    assert request["trigger"] == "voice"
    assert request["force"] is True


def test_initial_capture_request_id_skips_stale_request_on_restart(tmp_path: Path):
    request_file = tmp_path / "capture_request.json"
    request_file.write_text('{"request_id":"old-req","trigger":"qt_manual"}', encoding="utf-8")

    assert initial_capture_request_id(request_file) == "old-req"


def test_archive_capture_writes_files_and_prunes_old(tmp_path: Path):
    image_path = tmp_path / "latest.jpg"
    image_path.write_bytes(b"fake-jpeg")
    archive_dir = tmp_path / "archive"
    old_file = archive_dir / "old.json"
    old_file.parent.mkdir(parents=True)
    old_file.write_text("{}", encoding="utf-8")
    old_time = time.time() - 9 * 86400
    old_file.touch()
    import os

    os.utime(old_file, (old_time, old_time))
    state = {
        "vision_status": {
            "timestamp": "2026-07-08T12:00:00",
            "trigger": "voice",
            "request_id": "req-1",
        }
    }

    result = archive_capture(state, image_path, archive_dir, max_age_days=7, max_bytes=1_000_000)

    assert Path(result["archive_image_path"]).exists()
    assert Path(result["archive_state_path"]).exists()
    assert result["archive_pruned_files"] == 1
    assert not old_file.exists()
