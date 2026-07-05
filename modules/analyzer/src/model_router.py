from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Union

from models import RouterDecision, RuleResult


def load_llm_config(path: Union[str, Path]) -> Dict[str, Any]:
    """Load the small project YAML without requiring PyYAML on embedded boards."""
    try:
        import yaml  # type: ignore

        with open(path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)
    except ImportError:
        return _load_simple_yaml(path)


def _load_simple_yaml(path: Union[str, Path]) -> Dict[str, Any]:
    config: Dict[str, Any] = {}
    section = ""
    current = ""
    list_key = ""
    with open(path, "r", encoding="utf-8") as file:
        for raw in file:
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            indent = len(raw) - len(raw.lstrip(" "))
            line = raw.strip()
            if indent == 0 and line.endswith(":"):
                section = line[:-1]
                config[section] = {}
                current = ""
                continue
            if indent == 2 and line.endswith(":"):
                current = line[:-1]
                if section in ("models", "router"):
                    config[section][current] = {}
                continue
            if indent == 2 and ":" in line and section == "judge":
                key, value = [part.strip() for part in line.split(":", 1)]
                config[section][key] = [] if value == "" else _parse_value(value)
                list_key = key
                continue
            if indent == 4 and ":" in line and section in ("models", "router"):
                key, value = [part.strip() for part in line.split(":", 1)]
                config[section][current][key] = [] if value == "" else _parse_value(value)
                list_key = key
                continue
            if line.startswith("- "):
                value = line[2:].strip()
                if section == "judge":
                    config[section][list_key].append(value)
                else:
                    config[section][current][list_key].append(value)
    return config


def _parse_value(value: str) -> Any:
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "[]":
        return []
    try:
        return int(value)
    except ValueError:
        return value


class ModelRouter:
    """Deterministically choose models according to task and config."""

    def __init__(self, llm_config: Dict[str, Any]) -> None:
        self.config = llm_config

    def route(
        self,
        task_type: str,
        rule_result: RuleResult,
        network_state: bool = True,
    ) -> RouterDecision:
        router_config = self.config["router"].get(task_type, self.config["router"]["normal"])
        if not router_config.get("call_llm", False):
            return RouterDecision([], self._judge_model(), "当前为正常状态，无需调用大模型。")

        if not network_state:
            return RouterDecision(["mock"], "mock", "网络不可用，降级使用 mock 模型。")

        max_models = int(router_config.get("max_models", 0))
        selected: List[str] = []
        for name in router_config.get("preferred_models", []):
            model_config = self.config["models"].get(name, {})
            if model_config.get("enabled", False):
                selected.append(name)
            if len(selected) >= max_models:
                break

        if not selected and self.config["models"].get("mock", {}).get("enabled", True):
            selected = ["mock"]

        return RouterDecision(
            selected_models=selected,
            judge_model=self._judge_model(),
            reason=f"任务类型 {task_type}，规则等级 {rule_result.alarm_level}，选择 {selected}",
        )

    def _judge_model(self) -> str:
        for name in self.config.get("judge", {}).get("preferred_models", []):
            if self.config["models"].get(name, {}).get("enabled", False):
                return name
        return "mock"
