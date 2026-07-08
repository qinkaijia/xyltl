import argparse

import app_2k1000la.cloud_client as cloud_client_module
from app_2k1000la.cloud_client import (
    VoiceAlertManager,
    build_mqtt_config,
    extract_2k0301_fields,
    local_fallback_status,
    local_rule_evaluate,
)


def test_local_rule_normal():
    level, reason, hits = local_rule_evaluate(
        {"temperature": 30, "humidity": 50, "gas": 0.1, "tvoc": 120, "eco2": 450, "mq3_value": 0.123, "risk_score": 0},
        {"sensor_online": True},
    )
    assert level == 0
    assert hits == []
    assert "正常范围" in reason


def test_local_rule_alarm():
    level, reason, hits = local_rule_evaluate(
        {"temperature": 86, "humidity": 60, "gas": 0.65, "tvoc": 2600, "eco2": 2400, "mq3_value": 0.86, "risk_score": 78},
        {"sensor_online": True},
    )
    assert level == 2
    assert "TEMPERATURE_ALARM" in hits
    assert "GAS_ALARM" in hits


def test_local_rule_sensor_offline_ignores_sentinel_values():
    level, reason, hits = local_rule_evaluate(
        {"temperature": -999.0, "humidity": -1.0, "gas": 0.0},
        {"sensor_online": False},
    )

    assert level == 2
    assert "SENSOR_OFFLINE" in hits
    assert "HUMIDITY_ALARM" not in hits
    assert "TEMPERATURE_ALARM" not in hits
    assert "离线" in reason


def test_fallback_status_contains_voice_text():
    payload = {
        "device_id": "board_test",
        "metrics": {
            "temperature": 86,
            "humidity": 60,
            "gas": 0.65,
            "tvoc": 2600,
            "eco2": 2400,
            "mq3_value": 0.86,
            "flame_detected": False,
            "risk_score": 78,
        },
        "system_state": {"sensor_online": True},
    }
    status = local_fallback_status(payload, "timeout")
    assert status["alarm_level"] == 2
    assert status["analysis_mode"] == "local_http_fallback"
    assert status["voice_text"]


def test_extract_2k0301_fields_keeps_raw_sensor_values():
    payload = {
        "device_id": "board_2k0301",
        "metrics": {
            "temperature": 25.0,
            "humidity": 55.0,
            "tvoc": 120,
            "eco2": 450,
            "mq3_value": 0.123,
            "flame_detected": False,
            "risk_score": 0,
            "gas": 0.002,
        },
        "system_state": {"source": "2k0301_mqtt", "sensor_online": True},
    }

    fields = extract_2k0301_fields(payload)

    assert fields["tvoc"] == 120
    assert fields["eco2"] == 450
    assert fields["mq3_value"] == 0.123
    assert fields["flame_detected"] is False
    assert fields["sensor_metrics"]["risk_score"] == 0


def test_build_mqtt_config_from_cli_args():
    args = argparse.Namespace(
        sensor_source="2k0301",
        mqtt_host="192.168.43.40",
        mqtt_port=1883,
        mqtt_qos=1,
        mqtt_sensor_topic="device/board_2k0301/sensor",
        mqtt_heartbeat_topic="device/board_2k0301/heartbeat",
        mqtt_ack_topic="device/board_2k0301/ack",
        mqtt_error_topic="device/board_2k0301/error",
        mqtt_command_topic="device/board_2k0301/command",
        mqtt_first_timeout=3.0,
        mqtt_stale_after=6.0,
    )

    config = build_mqtt_config(args)

    assert config is not None
    assert config.host == "192.168.43.40"
    assert config.port == 1883
    assert config.sensor_topic == "device/board_2k0301/sensor"
    assert config.first_message_timeout == 3.0
    assert config.stale_after_seconds == 6.0


def test_build_mqtt_config_returns_none_for_mock_source():
    args = argparse.Namespace(sensor_source="mock")

    assert build_mqtt_config(args) is None


def test_voice_alert_manager_speaks_alerts_with_cooldown(monkeypatch):
    spoken = []

    def fake_speak(response, tts_mode=""):
        spoken.append((response["final_status"]["voice_text"], tts_mode))
        return True

    monkeypatch.setattr(cloud_client_module, "speak_response", fake_speak)
    manager = VoiceAlertManager(enabled=True, tts_mode="print", cooldown_seconds=30)

    normal = {
        "final_status": {
            "alarm_level": 0,
            "need_voice_alert": False,
            "voice_text": "当前设备处于正常状态。",
            "status_text": "正常",
            "reason": "所有关键指标处于正常范围",
        }
    }
    first_alarm = {
        "final_status": {
            "alarm_level": 2,
            "need_voice_alert": True,
            "voice_text": "当前设备处于报警状态。温度过高。",
            "status_text": "报警",
            "reason": "温度过高",
            "suggestion": "立即排查现场。",
        }
    }
    changed_alarm = {
        "final_status": {
            "alarm_level": 2,
            "need_voice_alert": True,
            "voice_text": "当前设备处于报警状态。检测到火焰。",
            "status_text": "报警",
            "reason": "检测到火焰",
            "suggestion": "立即撤离并处理火源。",
        }
    }

    assert manager.maybe_speak(normal, now=100) is False
    assert manager.maybe_speak(first_alarm, now=101) is True
    assert manager.maybe_speak(first_alarm, now=110) is False
    assert manager.maybe_speak(changed_alarm, now=111) is True
    assert manager.maybe_speak(normal, now=112) is False
    assert manager.maybe_speak(changed_alarm, now=113) is False
    assert manager.maybe_speak(changed_alarm, now=142) is True
    assert spoken == [
        ("当前设备处于报警状态。温度过高。", "print"),
        ("当前设备处于报警状态。检测到火焰。", "print"),
        ("当前设备处于报警状态。检测到火焰。", "print"),
    ]
