from __future__ import annotations

import json

from models import FinalStatus
from output_writer import OutputWriter


def test_output_writer_writes_json(tmp_path):
    status = FinalStatus(
        timestamp="2026-07-05 15:30:00",
        device_id="device",
        alarm_level=1,
        status_text="预警",
        temperature=72.5,
        humidity=61.0,
        gas=0.25,
        vibration=1.82,
        current=2.3,
        reason="温度偏高",
        suggestion="检查散热",
        voice_text="当前设备处于预警状态。",
        cloud_connected=True,
        need_cloud_upload=True,
        need_voice_alert=True,
        analysis_mode="mock_multi_llm",
        source={"rule_engine": True, "llm_analyzer": True, "judge_model": True, "safety_guard": True},
    )
    output_path = tmp_path / "runtime" / "system_status.json"
    OutputWriter(output_path).write(status)
    loaded = json.loads(output_path.read_text(encoding="utf-8"))
    assert loaded["alarm_level"] == 1
    assert loaded["status_text"] == "预警"

