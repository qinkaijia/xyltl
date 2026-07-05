import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = REPO_ROOT / "tests" / "scenarios" / "evaluate"

client = TestClient(app)


@pytest.mark.parametrize("scenario_path", sorted(SCENARIO_DIR.glob("*.json")))
def test_evaluate_scenarios(scenario_path):
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    response = client.post("/api/evaluate", json=scenario["request"])

    assert response.status_code == 200
    body = response.json()
    assert body["final_status"]["alarm_level"] == scenario["expected"]["alarm_level"]
    assert "voice_text" in body["final_status"]
