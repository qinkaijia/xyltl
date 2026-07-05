from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from app.schemas.evaluate import EvaluateRequest


REPO_ROOT = Path(__file__).resolve().parents[3]
ANALYZER_SRC = REPO_ROOT / "modules" / "analyzer" / "src"

if str(ANALYZER_SRC) not in sys.path:
    sys.path.insert(0, str(ANALYZER_SRC))

from main import run_demo  # noqa: E402


def evaluate(payload: EvaluateRequest) -> dict[str, Any]:
    previous_real_llm = os.environ.get("ANALYZER_USE_REAL_LLM")
    os.environ["ANALYZER_USE_REAL_LLM"] = "true" if payload.use_real_llm else "false"

    try:
        analyzer_input = _to_analyzer_input(payload)
        result = run_demo(analyzer_input, force_model=payload.force_model)
    finally:
        if previous_real_llm is None:
            os.environ.pop("ANALYZER_USE_REAL_LLM", None)
        else:
            os.environ["ANALYZER_USE_REAL_LLM"] = previous_real_llm

    debug = result.pop("_debug", None)
    response: dict[str, Any] = {"final_status": result}
    if payload.include_debug:
        response["debug"] = debug
    else:
        response["debug"] = None
    return response


def _to_analyzer_input(payload: EvaluateRequest) -> dict[str, Any]:
    metrics = payload.metrics
    state = payload.system_state
    return {
        "device_id": payload.device_id,
        "timestamp": payload.timestamp.isoformat(),
        "temperature": _number(metrics.get("temperature"), 0.0),
        "humidity": _number(metrics.get("humidity"), 0.0),
        "gas": _number(metrics.get("gas"), 0.0),
        "vibration": _number(metrics.get("vibration"), 0.0),
        "current": _number(metrics.get("current"), 0.0),
        "cloud_connected": bool(state.get("cloud_connected", True)),
        "voice_state": str(state.get("voice_state", "idle")),
        "sensor_online": bool(state.get("sensor_online", True)),
        "user_question": state.get("user_question"),
        "request_report": bool(state.get("request_report", False)),
    }


def _number(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
