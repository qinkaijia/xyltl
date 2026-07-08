from __future__ import annotations

import os
import sys
import importlib.util
from pathlib import Path
from typing import Any

from app.schemas.evaluate import EvaluateRequest


REPO_ROOT = Path(__file__).resolve().parents[3]
ANALYZER_SRC = REPO_ROOT / "modules" / "analyzer" / "src"

if str(ANALYZER_SRC) not in sys.path:
    sys.path.insert(0, str(ANALYZER_SRC))

_ANALYZER_MAIN_SPEC = importlib.util.spec_from_file_location("xylt_analyzer_main", ANALYZER_SRC / "main.py")
if _ANALYZER_MAIN_SPEC is None or _ANALYZER_MAIN_SPEC.loader is None:
    raise RuntimeError(f"无法加载 analyzer main.py: {ANALYZER_SRC / 'main.py'}")
_ANALYZER_MAIN = importlib.util.module_from_spec(_ANALYZER_MAIN_SPEC)
_ANALYZER_MAIN_SPEC.loader.exec_module(_ANALYZER_MAIN)
run_demo = _ANALYZER_MAIN.run_demo


_LATEST_EVALUATION: dict[str, Any] | None = None


def evaluate(payload: EvaluateRequest) -> dict[str, Any]:
    global _LATEST_EVALUATION

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
    result.update(_extract_2k0301_fields(payload))
    _enforce_sensor_offline_status(result, payload)
    response: dict[str, Any] = {"final_status": result}
    if payload.include_debug:
        response["debug"] = debug
    else:
        response["debug"] = None
    _LATEST_EVALUATION = {
        "request": payload.model_dump(mode="json"),
        "response": response,
    }
    return response


def latest_evaluation() -> dict[str, Any] | None:
    return _LATEST_EVALUATION


def _to_analyzer_input(payload: EvaluateRequest) -> dict[str, Any]:
    metrics = payload.metrics
    state = payload.system_state
    gas_score = metrics.get("gas")
    if gas_score is None:
        gas_score = _normalize_2k0301_gas(metrics, state)
    return {
        "device_id": payload.device_id,
        "timestamp": payload.timestamp.isoformat(),
        "temperature": _number(metrics.get("temperature"), 0.0),
        "humidity": _number(metrics.get("humidity"), 0.0),
        "gas": _number(gas_score, 0.0),
        "vibration": _number(metrics.get("vibration"), 0.0),
        "current": _number(metrics.get("current"), 0.0),
        "cloud_connected": bool(state.get("cloud_connected", True)),
        "voice_state": str(state.get("voice_state", "idle")),
        "sensor_online": bool(state.get("sensor_online", True)),
        "user_question": state.get("user_question"),
        "request_report": bool(state.get("request_report", False)),
    }


def _extract_2k0301_fields(payload: EvaluateRequest) -> dict[str, Any]:
    metrics = payload.metrics
    state = payload.system_state
    tvoc = _number(metrics.get("tvoc", state.get("raw_tvoc")), 0.0)
    eco2 = _number(metrics.get("eco2", state.get("raw_eco2")), 0.0)
    mq3_value = _number(metrics.get("mq3_value", state.get("raw_mq3_value")), 0.0)
    risk_score = _number(metrics.get("risk_score", state.get("raw_risk_score")), 0.0)
    flame_detected = bool(metrics.get("flame_detected", state.get("flame_detected", False)))
    return {
        "tvoc": tvoc,
        "eco2": eco2,
        "mq3_value": mq3_value,
        "flame_detected": flame_detected,
        "risk_score": risk_score,
        "sensor_online": bool(state.get("sensor_online", True)),
        "actuator_online": bool(state.get("actuator_online", True)),
        "sensor_source": state.get("source", ""),
        "sensor_metrics": {
            "temperature": _number(metrics.get("temperature"), 0.0),
            "humidity": _number(metrics.get("humidity"), 0.0),
            "tvoc": tvoc,
            "eco2": eco2,
            "mq3_value": mq3_value,
            "flame_detected": flame_detected,
            "risk_score": risk_score,
        },
    }


def _enforce_sensor_offline_status(result: dict[str, Any], payload: EvaluateRequest) -> None:
    metrics = payload.metrics
    state = payload.system_state
    temperature = _number(metrics.get("temperature"), 0.0)
    humidity = _number(metrics.get("humidity"), 0.0)
    sensor_online = bool(state.get("sensor_online", True))
    has_invalid_sentinel = temperature <= -900.0 or humidity < 0.0
    if sensor_online and not has_invalid_sentinel:
        return

    reason = "2K0301 传感器离线，温湿度或空气质量数据无效，无法确认现场环境。"
    source_error = str(state.get("last_2k0301_error") or state.get("last_2k0301_reported_error") or "").strip()
    if source_error:
        reason = f"{reason}上报原因：{source_error}"
    suggestion = "请检查 2K0301 传感器供电、I2C 接线和 SHT/SGP30 初始化状态；现场保持本地报警、排风和人工巡检。"
    result["alarm_level"] = max(int(result.get("alarm_level") or 0), 2)
    result["status_text"] = "报警"
    result["reason"] = reason
    result["suggestion"] = suggestion
    result["voice_text"] = f"当前设备处于报警状态。{reason}。{suggestion}"
    result["need_cloud_upload"] = True
    result["need_voice_alert"] = True
    result["sensor_online"] = False
    result["offline_reason"] = source_error or "invalid_sensor_sentinel"
    rule_hits = result.setdefault("rule_hits", [])
    if isinstance(rule_hits, list) and "SENSOR_OFFLINE" not in rule_hits:
        rule_hits.append("SENSOR_OFFLINE")
    source = result.setdefault("source", {})
    if isinstance(source, dict):
        source["sensor_offline_guard"] = True


def _normalize_2k0301_gas(metrics: dict[str, Any], state: dict[str, Any]) -> float:
    flame_detected = bool(metrics.get("flame_detected", state.get("flame_detected", False)))
    if flame_detected:
        return 1.0
    tvoc = _number(metrics.get("tvoc", state.get("raw_tvoc")), 0.0)
    eco2 = _number(metrics.get("eco2", state.get("raw_eco2")), 400.0)
    mq3_value = _number(metrics.get("mq3_value", state.get("raw_mq3_value")), 0.0)
    risk_score = _number(metrics.get("risk_score", state.get("raw_risk_score")), 0.0)
    scores = [
        _clamp(tvoc / 60000.0),
        _clamp((eco2 - 400.0) / (60000.0 - 400.0)),
        _clamp(mq3_value / 999.0),
        _clamp(risk_score / 100.0),
    ]
    return round(max(scores), 4)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _number(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
