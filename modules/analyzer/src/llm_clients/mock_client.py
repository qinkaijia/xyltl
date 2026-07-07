from __future__ import annotations

from typing import Dict, List

from llm_clients.base_client import BaseLLMClient


class MockLLMClient(BaseLLMClient):
    def __init__(self, model_name: str = "mock") -> None:
        super().__init__(model_name=model_name)

    def analyze(self, input_data: Dict, role: str) -> Dict:
        rule_result = input_data["rule_result"]
        level = int(rule_result["alarm_level"])
        causes = self._causes(rule_result)
        return {
            "model_name": self.model_name,
            "role": role,
            "alarm_level": level,
            "risk_summary": self._summary(level),
            "possible_causes": causes,
            "suggestion": self._suggestion(role, level),
            "confidence": self._confidence(level),
        }

    @staticmethod
    def _summary(level: int) -> str:
        if level == 2:
            return "存在明确报警风险，需要保持本地安全联动。"
        if level == 1:
            return "存在预警风险，建议现场巡检并观察趋势。"
        return "未发现明显风险。"

    @staticmethod
    def _causes(rule_result: Dict) -> List[str]:
        hits = rule_result.get("rule_hits", [])
        if not hits:
            return ["关键指标处于正常范围"]
        return [f"规则命中：{hit}" for hit in hits]

    @staticmethod
    def _suggestion(role: str, level: int) -> str:
        if level == 2:
            return "立即检查设备负载、散热、振动和传感器状态，必要时停机排查。"
        if role in ("fast_voice_response", "demo"):
            return "请检查现场状态，重点关注异常指标。"
        return "建议检查散热风扇、设备固定结构、运行负载和传感器连接。"

    @staticmethod
    def _confidence(level: int) -> float:
        return 0.86 if level > 0 else 0.78
