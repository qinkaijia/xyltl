import time
from pathlib import Path

from app_2k1000la.vision_service import archive_capture, normalize_local_yolo_result, read_capture_request, read_mode_file


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


def test_read_mode_file_uses_valid_mode_only(tmp_path: Path):
    mode_file = tmp_path / "mode_request.json"
    mode_file.write_text('{"mode":"off"}', encoding="utf-8")
    assert read_mode_file(mode_file, "cloud") == "off"

    mode_file.write_text('{"mode":"bad"}', encoding="utf-8")
    assert read_mode_file(mode_file, "cloud") == "cloud"


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
