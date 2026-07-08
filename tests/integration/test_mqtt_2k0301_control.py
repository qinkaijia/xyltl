import pytest

from modules.control import build_command_message, command_type_from_intent, normalize_command_params


def test_build_fan_command_message_from_command_id():
    message = build_command_message(
        "fan_control",
        {"state": "on", "speed": 120, "duration_ms": 1000},
        command_id="cmd-demo",
    )

    assert message["type"] == "command"
    assert message["seq"] > 0
    assert message["command"] == "fan_control"
    assert message["params"] == {"state": "on", "speed": 100, "duration_ms": 1000}


def test_alarm_light_off_normalizes_to_safe_payload():
    assert normalize_command_params("alarm_light", {"state": "off", "color": "red"}) == {
        "mode": "off",
        "color": "off",
    }


def test_unsupported_command_is_rejected():
    with pytest.raises(ValueError):
        build_command_message("open_everything", {})


def test_voice_intent_maps_to_2k0301_command():
    assert command_type_from_intent("FAN_CONTROL") == "fan_control"
    assert command_type_from_intent("BUZZER_CONTROL") == "buzzer_control"
    assert command_type_from_intent("ALARM_LIGHT") == "alarm_light"
