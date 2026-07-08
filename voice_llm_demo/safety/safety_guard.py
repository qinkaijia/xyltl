from __future__ import annotations

from typing import Dict, Tuple


class SafetyGuard:
    ALLOWED_INTENTS = {
        "START_DETECTION",
        "STOP_DETECTION",
        "QUERY_STATUS",
        "QUERY_SENSOR_DATA",
        "QUERY_ALARM",
        "EXPLAIN_ALARM",
        "GENERAL_QA",
        "LLM_UNAVAILABLE",
        "UPLOAD_DATA",
        "GENERATE_REPORT",
        "RETURN_HOME",
        "FAN_CONTROL",
        "BUZZER_CONTROL",
        "ALARM_LIGHT",
        "DEVICE_RESET",
        "UNSUPPORTED",
    }
    DANGEROUS_INTENTS = {
        "STOP_DETECTION",
        "CLEAR_ALARM",
        "RESET_DEVICE",
        "SHUTDOWN_SYSTEM",
        "DELETE_HISTORY",
        "DEVICE_RESET",
    }
    REQUIRED_FIELDS = {"type", "intent", "need_execute", "need_confirm", "params", "reply"}

    def check(self, llm_result: Dict) -> Tuple[bool, str]:
        if not isinstance(llm_result, dict):
            return False, "LLM 输出不是 dict，拒绝执行。"

        missing_fields = self.REQUIRED_FIELDS - set(llm_result.keys())
        if missing_fields:
            return False, f"LLM 输出缺少字段：{', '.join(sorted(missing_fields))}"

        intent = llm_result.get("intent")
        if intent not in self.ALLOWED_INTENTS:
            return False, f"intent 不在白名单中：{intent}"

        if intent == "UNSUPPORTED":
            return False, "该语音命令暂不支持。"

        if intent in self.DANGEROUS_INTENTS and not llm_result.get("need_confirm"):
            return False, f"{intent} 是危险命令，必须二次确认。"

        params = llm_result.get("params") or {}
        if intent in {"FAN_CONTROL", "BUZZER_CONTROL", "ALARM_LIGHT"}:
            state = str(params.get("state") or "").lower()
            mode = str(params.get("mode") or "").lower()
            if (state == "off" or mode == "off") and not llm_result.get("need_confirm"):
                return False, f"{intent} 关闭动作需要二次确认。"

        return True, "安全校验通过。"

    def need_confirm(self, llm_result: dict) -> bool:
        intent = llm_result.get("intent") if isinstance(llm_result, dict) else None
        return bool(llm_result.get("need_confirm")) or intent in self.DANGEROUS_INTENTS
