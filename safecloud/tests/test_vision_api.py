import base64

from fastapi.testclient import TestClient

from app.main import app
from app.services import vision_service


client = TestClient(app)


class FakeDoubaoVisionClient:
    is_available = True
    missing_config_message = ""

    def evaluate(self, image_base64, image_mime, sensor_snapshot):
        return (
            {
                "person_detected": True,
                "helmet_detected": True,
                "mask_detected": False,
                "reflective_vest_detected": True,
                "fire_detected": False,
                "ppe_status": "fail",
                "missing_ppe": ["口罩"],
                "summary": "检测到人员未佩戴口罩。",
                "confidence": 0.86,
                "detections": [{"label": "person", "confidence": 0.9}],
            },
            {"model": "fake-vision", "elapsed_ms": 1},
        )


def test_vision_evaluate_stores_latest_and_image(monkeypatch):
    monkeypatch.setattr(vision_service, "DoubaoVisionClient", FakeDoubaoVisionClient)
    image_bytes = b"\xff\xd8fake-jpeg\xff\xd9"
    payload = {
        "device_id": "board_2k1000la",
        "image_base64": base64.b64encode(image_bytes).decode("ascii"),
        "image_mime": "image/jpeg",
        "mode": "cloud",
        "include_debug": True,
    }

    response = client.post("/api/vision/evaluate", json=payload)

    assert response.status_code == 200
    body = response.json()
    status = body["vision_status"]
    assert status["ppe_status"] == "fail"
    assert status["person_detected"] is True
    assert status["missing_ppe"] == ["口罩"]
    assert body["debug"]["model"] == "fake-vision"

    latest = client.get("/api/vision/latest")
    assert latest.status_code == 200
    assert latest.json()["response"]["vision_status"]["device_id"] == "board_2k1000la"

    image = client.get("/api/vision/latest-image")
    assert image.status_code == 200
    assert image.content == image_bytes
    assert image.headers["content-type"].startswith("image/jpeg")


def test_vision_mode_switch():
    response = client.post("/api/vision/mode", json={"mode": "local"})
    assert response.status_code == 200
    assert response.json()["mode"] == "local"

    response = client.get("/api/vision/mode")
    assert response.status_code == 200
    assert response.json()["mode"] == "local"

    client.post("/api/vision/mode", json={"mode": "cloud"})
