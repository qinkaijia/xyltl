from __future__ import annotations

from pathlib import Path

from model_router import load_llm_config
from models import RuleResult, SensorData, SystemState, now_text
from multi_llm_analyzer import MultiLLMAnalyzer


CONFIG = Path(__file__).resolve().parents[1] / "config" / "llm_config.yaml"


def test_multi_llm_returns_results_for_selected_models():
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

