from __future__ import annotations

from pathlib import Path

from model_router import ModelRouter, load_llm_config
from models import RuleResult


CONFIG = Path(__file__).resolve().parents[1] / "config" / "llm_config.yaml"


def rule(level):
    return RuleResult(level, "x", "reason", "suggestion")


def test_router_normal_selects_no_models():
    decision = ModelRouter(load_llm_config(CONFIG)).route("normal", rule(0))
    assert decision.selected_models == []


def test_router_alarm_selects_at_most_three_models():
    decision = ModelRouter(load_llm_config(CONFIG)).route("alarm", rule(2))
    assert 1 <= len(decision.selected_models) <= 3


def test_router_network_failure_uses_mock():
    decision = ModelRouter(load_llm_config(CONFIG)).route("alarm", rule(2), network_state=False)
    assert decision.selected_models == ["mock"]

