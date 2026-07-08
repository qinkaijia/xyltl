from __future__ import annotations

from pathlib import Path

from models import SensorData, SystemState, now_text
from rule_engine import RuleEngine


THRESHOLDS = Path(__file__).resolve().parents[1] / "config" / "thresholds.json"


def make_sensor(**kwargs):
    data = {
        "device_id": "device_test",
        "timestamp": now_text(),
        "temperature": 30.0,
        "humidity": 50.0,
        "gas": 0.1,
        "vibration": 0.5,
        "current": 1.0,
    }
    data.update(kwargs)
    return SensorData.from_dict(data)


def test_rule_engine_normal_outputs_level_0():
    result = RuleEngine.from_file(THRESHOLDS).evaluate(make_sensor(), SystemState())
    assert result.alarm_level == 0


def test_rule_engine_temperature_warning_outputs_level_1():
    result = RuleEngine.from_file(THRESHOLDS).evaluate(make_sensor(temperature=65.0), SystemState())
    assert result.alarm_level == 1
    assert "TEMPERATURE_WARNING" in result.rule_hits


def test_rule_engine_temperature_alarm_outputs_level_2():
    result = RuleEngine.from_file(THRESHOLDS).evaluate(make_sensor(temperature=80.0), SystemState())
    assert result.alarm_level == 2
    assert "TEMPERATURE_ALARM" in result.rule_hits


def test_sensor_offline_forces_alarm():
    result = RuleEngine.from_file(THRESHOLDS).evaluate(make_sensor(), SystemState(sensor_online=False))
    assert result.alarm_level == 2


def test_sensor_offline_ignores_invalid_sentinel_values():
    result = RuleEngine.from_file(THRESHOLDS).evaluate(
        make_sensor(temperature=-999.0, humidity=-1.0),
        SystemState(sensor_online=False),
    )

    assert result.alarm_level == 2
    assert "SENSOR_OFFLINE" in result.rule_hits
    assert "HUMIDITY_ALARM" not in result.rule_hits
    assert "TEMPERATURE_ALARM" not in result.rule_hits
