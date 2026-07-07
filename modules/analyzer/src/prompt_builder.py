from __future__ import annotations

import json
from typing import Any, Dict


class PromptBuilder:
    def build_safety_prompt(self, payload: Dict[str, Any]) -> str:
        return self._build("安全分析", payload)

    def build_diagnosis_prompt(self, payload: Dict[str, Any]) -> str:
        return self._build("工程诊断", payload)

    def build_operation_prompt(self, payload: Dict[str, Any]) -> str:
        return self._build("运维建议", payload)

    def build_judge_prompt(self, payload: Dict[str, Any]) -> str:
        return self._build("多模型裁判", payload)

    def build_voice_answer_prompt(self, payload: Dict[str, Any]) -> str:
        return self._build("现场语音播报", payload)

    def build_report_prompt(self, payload: Dict[str, Any]) -> str:
        return self._build("云端报告", payload)

    @staticmethod
    def _build(role: str, payload: Dict[str, Any]) -> str:
        return (
            f"你是{role}模型。必须只输出 JSON，不得输出 JSON 以外内容。"
            "不得把 RuleEngine 的报警等级降级。建议必须简洁、可执行，语音文本适合现场播报。\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)
        )
