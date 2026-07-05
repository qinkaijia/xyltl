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
