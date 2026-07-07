import argparse

from app_2k1000la.cloud_client import build_mqtt_config, local_fallback_status, local_rule_evaluate


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


def test_build_mqtt_config_from_cli_args():
    args = argparse.Namespace(
        sensor_source="2k0301",
        mqtt_host="192.168.43.40",
        mqtt_port=1883,
        mqtt_qos=1,
        mqtt_sensor_topic="device/2k0301/sensor",
        mqtt_heartbeat_topic="device/2k0301/heartbeat",
        mqtt_ack_topic="device/2k0301/ack",
        mqtt_error_topic="device/2k0301/error",
        mqtt_command_topic="device/2k0301/command",
        mqtt_first_timeout=3.0,
        mqtt_stale_after=6.0,
    )

    config = build_mqtt_config(args)

    assert config is not None
    assert config.host == "192.168.43.40"
    assert config.port == 1883
    assert config.sensor_topic == "device/2k0301/sensor"
    assert config.first_message_timeout == 3.0
    assert config.stale_after_seconds == 6.0


def test_build_mqtt_config_returns_none_for_mock_source():
    args = argparse.Namespace(sensor_source="mock")

    assert build_mqtt_config(args) is None
