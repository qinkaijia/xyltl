from app_2k1000la.cloud_client import local_fallback_status, local_rule_evaluate


def test_local_rule_normal():
    level, reason, hits = local_rule_evaluate(
        {"temperature": 30, "humidity": 50, "gas": 0.1, "vibration": 0.5, "current": 1.0},
        {"sensor_online": True},
    )
    assert level == 0
    assert hits == []
    assert "正常范围" in reason


def test_local_rule_alarm():
    level, reason, hits = local_rule_evaluate(
        {"temperature": 86, "humidity": 60, "gas": 0.32, "vibration": 2.8, "current": 4.2},
        {"sensor_online": True},
    )
    assert level == 2
    assert "TEMPERATURE_ALARM" in hits
    assert "VIBRATION_ALARM" in hits


def test_fallback_status_contains_voice_text():
    payload = {
        "device_id": "board_test",
        "metrics": {"temperature": 86, "humidity": 60, "gas": 0.32, "vibration": 2.8, "current": 4.2},
        "system_state": {"sensor_online": True},
    }
    status = local_fallback_status(payload, "timeout")
    assert status["alarm_level"] == 2
    assert status["analysis_mode"] == "local_http_fallback"
    assert status["voice_text"]
