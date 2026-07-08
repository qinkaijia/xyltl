from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_evaluate_mock_warning():
    response = client.post(
        "/api/evaluate",
        json={
            "device_id": "device_api_test",
            "metrics": {
                "temperature": 72.5,
                "humidity": 61.0,
                "gas": 0.25,
                "vibration": 1.82,
                "current": 2.3,
            },
            "include_debug": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["final_status"]["alarm_level"] == 1
    assert body["final_status"]["analysis_mode"] == "mock_multi_llm"
    assert body["debug"]["router"]["selected_models"]


def test_evaluate_force_mock_alarm():
    response = client.post(
        "/api/evaluate",
        json={
            "device_id": "device_api_alarm",
            "metrics": {
                "temperature": 86.0,
                "humidity": 60.0,
                "gas": 0.32,
                "vibration": 2.8,
                "current": 4.2,
            },
            "force_model": "mock",
            "include_debug": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["final_status"]["alarm_level"] == 2
    assert body["final_status"]["need_voice_alert"] is True
    assert body["debug"]["router"]["selected_models"] == ["mock"]


def test_evaluate_preserves_2k0301_metrics_and_latest_result():
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
        },
        "system_state": {"cloud_connected": True, "sensor_online": True, "actuator_online": True, "source": "2k0301"},
        "include_debug": True,
    }

    response = client.post("/api/evaluate", json=payload)

    assert response.status_code == 200
    body = response.json()
    final_status = body["final_status"]
    assert final_status["tvoc"] == 120
    assert final_status["eco2"] == 450
    assert final_status["mq3_value"] == 0.123
    assert final_status["flame_detected"] is False
    assert final_status["sensor_metrics"]["risk_score"] == 0

    latest = client.get("/api/evaluate/latest")
    assert latest.status_code == 200
    assert latest.json()["response"]["final_status"]["device_id"] == "board_2k0301"


def test_evaluate_sensor_offline_guard_has_clear_reason():
    response = client.post(
        "/api/evaluate",
        json={
            "device_id": "board_2k0301",
            "metrics": {
                "temperature": -999.0,
                "humidity": -1.0,
                "tvoc": 0,
                "eco2": 0,
                "mq3_value": 0.002,
                "flame_detected": False,
                "risk_score": 0,
            },
            "system_state": {
                "cloud_connected": True,
                "sensor_online": False,
                "actuator_online": True,
                "source": "2k0301_mqtt",
                "last_2k0301_error": "2K0301 sensor_packet contains invalid sentinel values",
            },
            "include_debug": True,
        },
    )

    assert response.status_code == 200
    final_status = response.json()["final_status"]
    assert final_status["alarm_level"] == 2
    assert final_status["sensor_online"] is False
    assert "2K0301 传感器离线" in final_status["reason"]
    assert "2K0301 传感器离线" in final_status["voice_text"]
    assert final_status["need_voice_alert"] is True
