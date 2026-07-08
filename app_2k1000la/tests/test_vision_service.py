import time
from pathlib import Path

from app_2k1000la.vision_service import normalize_local_yolo_result, read_mode_file


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
