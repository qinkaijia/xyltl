from __future__ import annotations

from llm_clients.base_client import BaseLLMClient
from llm_clients.deepseek_client import DeepSeekClient


def test_base_client_extracts_json_from_markdown_block():
    client = BaseLLMClient("unit")
    parsed = client._parse_json_content(
        '```json\n{"alarm_level": 1, "risk_summary": "预警", "possible_causes": "温度偏高"}\n```'
    )
    result = client._normalize_result(
        parsed,
        {"rule_result": {"alarm_level": 1, "rule_hits": ["TEMPERATURE_WARNING"], "suggestion": "检查散热"}},
        "unit_role",
    )
    assert result["alarm_level"] == 1
    assert result["possible_causes"] == ["温度偏高"]


def test_provider_falls_back_to_mock_when_real_llm_disabled(monkeypatch):
    monkeypatch.setenv("ANALYZER_USE_REAL_LLM", "false")
    payload = {
        "rule_result": {
            "alarm_level": 1,
            "rule_hits": ["TEMPERATURE_WARNING"],
            "reason": "温度偏高",
            "suggestion": "检查散热",
        }
    }
    result = DeepSeekClient().analyze(payload, "engineering_diagnosis")
    assert result["model_name"] == "deepseek_mock"
    assert "error" not in result


def test_provider_records_error_when_real_llm_enabled_but_missing_config(monkeypatch):
    monkeypatch.setenv("ANALYZER_USE_REAL_LLM", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_URL", "")
    monkeypatch.setenv("DEEPSEEK_MODEL", "")
    payload = {
        "rule_result": {
            "alarm_level": 1,
            "rule_hits": ["TEMPERATURE_WARNING"],
            "reason": "温度偏高",
            "suggestion": "检查散热",
        }
    }
    result = DeepSeekClient().analyze(payload, "engineering_diagnosis")
    assert result["model_name"] == "deepseek_mock"
    assert "已回退 mock" in result["error"]
