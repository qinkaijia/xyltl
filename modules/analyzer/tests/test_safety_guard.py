from __future__ import annotations

from models import JudgeResult, RuleResult, SensorData, SystemState, now_text
from safety_guard import SafetyGuard


def test_safety_guard_does_not_downgrade_alarm():
    sensor = SensorData("device", now_text(), 80.0, 50.0, 0.2, 1.0, 2.0)
    rule = RuleResult(2, "报警", "温度报警", "立即检查")
    judge = JudgeResult(0, "模型误判正常", [], "继续观察", "正常", 0.5)
    final = SafetyGuard().enforce(judge, rule, sensor, SystemState())
    assert final.alarm_level == 2
    assert final.status_text == "报警"


def test_safety_guard_fills_voice_and_suggestion():
    sensor = SensorData("device", now_text(), 60.0, 50.0, 0.2, 1.0, 2.0)
    rule = RuleResult(1, "预警", "温度预警", "检查散热")
    judge = JudgeResult(1, "温度预警", [], "", "", 0.8)
    final = SafetyGuard().enforce(judge, rule, sensor, SystemState())
    assert final.suggestion
    assert final.voice_text

