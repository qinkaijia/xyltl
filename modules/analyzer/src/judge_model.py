from __future__ import annotations

from collections import Counter
from typing import List

from models import JudgeResult, LLMAnalysisResult, RuleResult, SensorData, SystemState


class JudgeModel:
    """Fuse multiple model outputs while respecting local rule severity."""

    def judge(
        self,
        sensor_data: SensorData,
        system_state: SystemState,
        rule_result: RuleResult,
        model_results: List[LLMAnalysisResult],
    ) -> JudgeResult:
        levels = [max(0, min(2, item.alarm_level)) for item in model_results]
        model_max = max(levels) if levels else rule_result.alarm_level
        final_level = max(rule_result.alarm_level, model_max)

        risky_votes = sum(1 for level in levels if level > 0)
        if risky_votes >= max(1, len(levels) // 2 + 1):
            final_level = max(final_level, 1)
        if rule_result.alarm_level >= 1 and any(level == 2 for level in levels):
            final_level = 2

        causes = self._merge_causes(rule_result, model_results)
        suggestion = self._merge_suggestion(rule_result, model_results)
        confidence = self._confidence(rule_result, model_results)
        main_reason = self._main_reason(rule_result, model_results, final_level)

        return JudgeResult(
            alarm_level=final_level,
            main_reason=main_reason,
            possible_causes=causes,
            suggestion=suggestion,
            voice_text=self._voice_text(final_level, main_reason, suggestion),
            confidence=confidence,
        )

    @staticmethod
    def _merge_causes(rule_result: RuleResult, model_results: List[LLMAnalysisResult]) -> List[str]:
        causes = list(rule_result.rule_hits)
        for result in model_results:
            causes.extend(result.possible_causes)
        unique = []
        for cause in causes:
            if cause and cause not in unique:
                unique.append(cause)
        return unique or ["未发现明确异常原因"]

    @staticmethod
    def _merge_suggestion(rule_result: RuleResult, model_results: List[LLMAnalysisResult]) -> str:
        for result in model_results:
            if result.suggestion:
                return result.suggestion
        return rule_result.suggestion

    @staticmethod
    def _confidence(rule_result: RuleResult, model_results: List[LLMAnalysisResult]) -> float:
        if not model_results:
            return 0.72
        average = sum(result.confidence for result in model_results) / len(model_results)
        return round(max(average, 0.8 if rule_result.alarm_level > 0 else 0.7), 2)

    @staticmethod
    def _main_reason(
        rule_result: RuleResult,
        model_results: List[LLMAnalysisResult],
        final_level: int,
    ) -> str:
        if model_results:
            summaries = [result.risk_summary for result in model_results if result.risk_summary]
            if summaries:
                return Counter(summaries).most_common(1)[0][0]
        if final_level == 0:
            return "本地规则和模型分析均未发现明显风险。"
        return rule_result.reason

    @staticmethod
    def _voice_text(level: int, reason: str, suggestion: str) -> str:
        if level == 2:
            prefix = "当前设备处于报警状态。"
        elif level == 1:
            prefix = "当前设备处于预警状态。"
        else:
            prefix = "当前设备运行正常。"
        clean_reason = reason.rstrip("。；; ")
        clean_suggestion = suggestion.rstrip("。；; ")
        return f"{prefix}{clean_reason}。{clean_suggestion}。"
