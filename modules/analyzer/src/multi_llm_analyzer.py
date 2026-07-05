from __future__ import annotations

from typing import Dict, List

from llm_clients import DeepSeekClient, DoubaoClient, KimiClient, MockLLMClient, QwenClient, ZhipuClient
from models import LLMAnalysisResult, RuleResult, SensorData, SystemState


class MultiLLMAnalyzer:
    """Call routed LLM clients in order. Real clients fall back to mock."""

    def __init__(self, llm_config: Dict) -> None:
        self.llm_config = llm_config
        self.clients = {
            "deepseek": DeepSeekClient(),
            "kimi": KimiClient(),
            "zhipu": ZhipuClient(),
            "doubao": DoubaoClient(),
            "qwen": QwenClient(),
            "mock": MockLLMClient("mock"),
        }

    def analyze(
        self,
        sensor_data: SensorData,
        system_state: SystemState,
        rule_result: RuleResult,
        selected_models: List[str],
    ) -> List[LLMAnalysisResult]:
        payload = {
            "sensor_data": sensor_data.to_dict(),
            "system_state": system_state.to_dict(),
            "rule_result": rule_result.to_dict(),
        }
        results: List[LLMAnalysisResult] = []

        for model_name in selected_models:
            client = self.clients.get(model_name, self.clients["mock"])
            role = self.llm_config.get("models", {}).get(model_name, {}).get("role", "general")
            try:
                result = client.analyze(payload, role)
                results.append(LLMAnalysisResult.from_dict(result))
            except Exception as exc:
                results.append(
                    LLMAnalysisResult(
                        model_name=model_name,
                        role=role,
                        alarm_level=rule_result.alarm_level,
                        risk_summary="模型调用失败，使用规则引擎结果兜底。",
                        possible_causes=list(rule_result.rule_hits),
                        suggestion=rule_result.suggestion,
                        confidence=0.5,
                        error=str(exc),
                    )
                )

        if not results:
            results.append(self._fallback_result(rule_result))
        return results

    @staticmethod
    def _fallback_result(rule_result: RuleResult) -> LLMAnalysisResult:
        return LLMAnalysisResult(
            model_name="rule_fallback",
            role="local_rule_fallback",
            alarm_level=rule_result.alarm_level,
            risk_summary=rule_result.reason,
            possible_causes=list(rule_result.rule_hits) or ["无模型调用，采用本地规则结果"],
            suggestion=rule_result.suggestion,
            confidence=0.72,
        )
