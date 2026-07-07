from __future__ import annotations

from models import FinalStatus, JudgeResult, RuleResult, SensorData, STATUS_TEXT, SystemState, now_text


class SafetyGuard:
    """Final deterministic guard; LLM/judge cannot downgrade local rules."""

    def enforce(
        self,
        judge_result: JudgeResult,
        rule_result: RuleResult,
        sensor_data: SensorData,
        system_state: SystemState,
        llm_available: bool = True,
        analysis_mode: str = "mock_multi_llm",
    ) -> FinalStatus:
        try:
            level = int(judge_result.alarm_level)
            reason = judge_result.main_reason or rule_result.reason
            suggestion = judge_result.suggestion or rule_result.suggestion
            voice_text = judge_result.voice_text or f"{STATUS_TEXT[rule_result.alarm_level]}：{reason}"
        except Exception:
            level = rule_result.alarm_level
            reason = rule_result.reason
            suggestion = rule_result.suggestion
            voice_text = f"{rule_result.status}：{reason}。{suggestion}"

        level = max(level, rule_result.alarm_level)
        level = max(0, min(2, level))
        if not suggestion:
            suggestion = rule_result.suggestion or "请检查现场设备状态。"
        if not voice_text:
            voice_text = f"{STATUS_TEXT[level]}：{reason}。{suggestion}"

        return FinalStatus(
            timestamp=now_text(),
            device_id=sensor_data.device_id,
            alarm_level=level,
            status_text=STATUS_TEXT[level],
            temperature=sensor_data.temperature,
            humidity=sensor_data.humidity,
            gas=sensor_data.gas,
            vibration=sensor_data.vibration,
            current=sensor_data.current,
            reason=reason,
            suggestion=suggestion,
            voice_text=voice_text,
            cloud_connected=system_state.cloud_connected,
            need_cloud_upload=rule_result.need_cloud_upload or level > 0,
            need_voice_alert=rule_result.need_voice_alert or level > 0,
            analysis_mode=analysis_mode if llm_available else "rule_fallback",
            source={
                "rule_engine": True,
                "llm_analyzer": llm_available,
                "judge_model": llm_available,
                "safety_guard": True,
            },
        )
