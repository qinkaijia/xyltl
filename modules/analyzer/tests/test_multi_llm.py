from __future__ import annotations

from pathlib import Path

from model_router import load_llm_config
from models import RuleResult, SensorData, SystemState, now_text
from multi_llm_analyzer import MultiLLMAnalyzer


CONFIG = Path(__file__).resolve().parents[1] / "config" / "llm_config.yaml"


def test_multi_llm_returns_results_for_selected_models(monkeypatch):
    monkeypatch.setenv("ANALYZER_USE_REAL_LLM", "false")
    sensor = SensorData("device", now_text(), 72.0, 50.0, 0.2, 1.8, 2.0)
    rule = RuleResult(1, "预警", "温度偏高", "检查散热", ["TEMPERATURE_WARNING"])
    results = MultiLLMAnalyzer(load_llm_config(CONFIG)).analyze(sensor, SystemState(), rule, ["qwen", "mock"])
    assert len(results) == 2
    assert all(item.alarm_level >= 1 for item in results)


def test_multi_llm_returns_rule_fallback_when_no_models():
    sensor = SensorData("device", now_text(), 30.0, 50.0, 0.1, 0.5, 1.0)
    rule = RuleResult(0, "正常", "正常", "继续监测")
    results = MultiLLMAnalyzer(load_llm_config(CONFIG)).analyze(sensor, SystemState(), rule, [])
    assert results[0].model_name == "rule_fallback"


def test_real_llm_failure_does_not_create_mock_result(monkeypatch):
    monkeypatch.setenv("ANALYZER_USE_REAL_LLM", "true")
    monkeypatch.setenv("QWEN_API_KEY", "")
    monkeypatch.setenv("QWEN_API_URL", "")
    monkeypatch.setenv("QWEN_MODEL", "")
    sensor = SensorData("device", now_text(), 30.0, 50.0, 0.1, 0.5, 1.0)
    rule = RuleResult(0, "正常", "正常", "继续监测")

    results = MultiLLMAnalyzer(load_llm_config(CONFIG)).analyze(sensor, SystemState(), rule, ["qwen"])

    assert results[0].model_name == "qwen"
    assert results[0].error
    assert not results[0].model_name.endswith("_mock")
