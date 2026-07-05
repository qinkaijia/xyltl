from __future__ import annotations

from models import RuleResult, SystemState


class TaskClassifier:
    def classify(self, rule_result: RuleResult, system_state: SystemState) -> str:
        if system_state.user_question:
            return "voice_question"
        if system_state.request_report:
            return "cloud_report"
        if rule_result.alarm_level == 2:
            return "alarm"
        if rule_result.alarm_level == 1:
            return "warning"
        return "normal"
