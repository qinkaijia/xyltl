from __future__ import annotations

from models import LLMAnalysisResult, RuleResult, SensorData, SystemState, now_text
from judge_model import JudgeModel


def test_judge_model_fuses_multiple_results():
    sensor = SensorData("device", now_text(), 70.0, 50.0, 0.2, 1.7, 2.0)
    rule = RuleResult(1, "预警", "温度预警", "检查散热")
    model_results = [
        LLMAnalysisResult("m1", "r1", 1, "存在预警", ["温度偏高"], "检查散热", 0.8),
        LLMAnalysisResult("m2", "r2", 2, "存在报警趋势", ["振动异常"], "现场巡检", 0.85),
    ]
    judge = JudgeModel().judge(sensor, SystemState(), rule, model_results)
    assert judge.alarm_level == 2
    assert judge.suggestion

