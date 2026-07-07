from app_2k1000la.sensor_source import (
    MockSensorSource,
    ScenarioFileSource,
    apply_runtime_options,
    build_2k0301_offline_payload,
    normalize_2k0301_gas,
    transform_2k0301_sensor_message,
)


def test_scenario_file_source_loads_request():
    payload = ScenarioFileSource("tests/scenarios/evaluate/normal.json").next_payload()

    assert payload["device_id"] == "scenario_normal"
    assert payload["metrics"]["temperature"] == 30.0


def test_mock_source_cycles_scenarios():
    source = MockSensorSource(
        [
            "tests/scenarios/evaluate/normal.json",
            "tests/scenarios/evaluate/temperature_warning.json",
        ]
    )

    first = source.next_payload()
    second = source.next_payload()
    third = source.next_payload()

    assert first["device_id"] == "scenario_normal"
    assert second["device_id"] == "scenario_temperature_warning"
    assert third["device_id"] == "scenario_normal"
    assert "timestamp" in first


def test_transform_2k0301_sensor_message():
    payload = transform_2k0301_sensor_message(
        {
            "type": "sensor_packet",
            "seq": 0,
            "payload": {
                "device_id": "board_2k0301",
                "timestamp": "2026-07-06T13:25:30",
                "temperature": 28.0,
                "humidity": 37.5,
                "tvoc": 5,
                "eco2": 400,
                "mq3_value": 0.004,
                "flame_detected": False,
                "risk_score": 5,
            },
        }
    )

    assert payload["device_id"] == "board_2k0301"
    assert payload["metrics"]["temperature"] == 28.0
    assert payload["metrics"]["humidity"] == 37.5
    assert payload["metrics"]["gas"] == 0.05
    assert payload["metrics"]["vibration"] == 0.0
    assert payload["system_state"]["source"] == "2k0301_mqtt"
    assert payload["system_state"]["source_seq"] == 0
    assert payload["system_state"]["raw_mq3_value"] == 0.004


def test_transform_2k0301_flame_forces_high_gas_score():
    assert normalize_2k0301_gas(0, 400, 0, 0, flame_detected=True) == 1.0


def test_build_2k0301_offline_payload_uses_heartbeat_device_id():
    payload = build_2k0301_offline_payload(
        "heartbeat timeout",
        latest_heartbeat={"device_id": "board_2k0301", "actuator_online": True},
        last_error={"error_code": "MQTT_DISCONNECTED"},
    )

    assert payload["device_id"] == "board_2k0301"
    assert payload["system_state"]["sensor_online"] is False
    assert payload["system_state"]["actuator_online"] is True
    assert payload["system_state"]["last_2k0301_error"] == "heartbeat timeout"


def test_apply_runtime_options_does_not_mutate_input():
    payload = {"device_id": "board_test", "metrics": {"temperature": 30.0}, "include_debug": False}

    prepared = apply_runtime_options(payload, use_real_llm=True, force_model="deepseek", include_debug=True)

    assert prepared["use_real_llm"] is True
    assert prepared["force_model"] == "deepseek"
    assert prepared["include_debug"] is True
    assert payload == {"device_id": "board_test", "metrics": {"temperature": 30.0}, "include_debug": False}
