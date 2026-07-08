from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from vision_bridge import VisionAssistantBridge, build_voice_reply


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_vision_query_detection_and_capture_request(tmp_path: Path):
    bridge = VisionAssistantBridge(
        capture_request_file=str(tmp_path / "capture_request.json"),
        vision_state_file=str(tmp_path / "vision_state.json"),
        context_status_file=str(tmp_path / "latest_evaluate_response.json"),
        timeout_seconds=1,
        enabled=True,
    )

    assert bridge.is_vision_query("现在穿戴规范吗")
    assert bridge.should_force_capture("重新拍一下看看安全帽")

    bridge._write_capture_request("req-1", "现在穿戴规范吗", force=True)
    data = json.loads((tmp_path / "capture_request.json").read_text(encoding="utf-8"))
    assert data["request_id"] == "req-1"
    assert data["trigger"] == "voice"
    assert data["force"] is True


def test_build_voice_reply_contains_chinese_sensor_fields():
    reply = build_voice_reply(
        {
            "person_detected": True,
            "ppe_status": "fail",
            "missing_ppe": ["安全帽"],
            "summary": "人员未佩戴安全帽",
            "fire_detected": False,
        },
        {
            "temperature": 25.0,
            "humidity": 55.0,
            "tvoc": 120,
            "eco2": 450,
            "mq3_value": 0.123,
            "flame_detected": False,
            "risk_score": 0,
        },
        "已触发摄像头抓拍并完成云端视觉分析。",
        max_chars=500,
    )

    assert "缺少安全帽" in reply
    assert "温度25.0℃" in reply
    assert "TVOC120ppb" in reply
    assert "存在安全隐患" in reply


def test_answer_reuses_recent_vision_result(tmp_path: Path):
    state_file = tmp_path / "vision_state.json"
    context_file = tmp_path / "latest_evaluate_response.json"
    write_json(
        state_file,
        {
            "vision_status": {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "person_detected": True,
                "ppe_status": "pass",
                "missing_ppe": [],
                "summary": "穿戴正常",
            }
        },
    )
    write_json(
        context_file,
        {
            "final_status": {
                "sensor_metrics": {
                    "temperature": 25.0,
                    "humidity": 55.0,
                    "tvoc": 120,
                    "eco2": 450,
                    "mq3_value": 0.123,
                    "flame_detected": False,
                    "risk_score": 0,
                }
            }
        },
    )
    bridge = VisionAssistantBridge(
        capture_request_file=str(tmp_path / "capture_request.json"),
        vision_state_file=str(state_file),
        context_status_file=str(context_file),
        recent_seconds=30,
        enabled=True,
    )

    reply = bridge.answer("现在穿戴规范吗")

    assert "复用最近一次分析" in reply
    assert "穿戴基本规范" in reply
    assert "温度25.0℃" in reply
    assert not (tmp_path / "capture_request.json").exists()
