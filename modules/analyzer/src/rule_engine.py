from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Union

from models import RuleResult, SensorData, STATUS_TEXT, SystemState


class RuleEngine:
    """Local deterministic safety rules. This is the final fallback."""

    def __init__(self, thresholds: Dict) -> None:
        self.thresholds = thresholds

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "RuleEngine":
        with open(path, "r", encoding="utf-8") as file:
            return cls(json.load(file))

    def evaluate(self, sensor_data: SensorData, system_state: SystemState) -> RuleResult:
        level = 0
        hits: List[str] = []
        reasons: List[str] = []

        if not system_state.sensor_online:
            level = 2
            hits.append("SENSOR_OFFLINE")
            reasons.append("传感器离线，无法确认现场状态")

        level = max(level, self._check_high("temperature", sensor_data.temperature, hits, reasons, "温度"))
        level = max(level, self._check_range("humidity", sensor_data.humidity, hits, reasons, "湿度"))
        level = max(level, self._check_high("gas", sensor_data.gas, hits, reasons, "气体浓度"))
        level = max(level, self._check_high("vibration", sensor_data.vibration, hits, reasons, "振动"))
        level = max(level, self._check_high("current", sensor_data.current, hits, reasons, "电流"))

        if not system_state.cloud_connected:
            hits.append("CLOUD_DISCONNECTED")
            reasons.append("云端连接中断，智能分析能力降级")

        if not reasons:
            reasons.append("所有关键指标处于正常范围")

        suggestion = self._suggestion_for_level(level)
        return RuleResult(
            alarm_level=level,
            status=STATUS_TEXT[level],
            reason="；".join(reasons),
            suggestion=suggestion,
            rule_hits=hits,
            need_cloud_upload=level > 0,
            need_voice_alert=level > 0,
        )

    def _check_high(self, name: str, value: float, hits: List[str], reasons: List[str], label: str) -> int:
        threshold = self.thresholds[name]
        if value >= float(threshold["alarm"]):
            hits.append(f"{name.upper()}_ALARM")
            reasons.append(f"{label}达到报警阈值：{value}")
            return 2
        if value >= float(threshold["warning"]):
            hits.append(f"{name.upper()}_WARNING")
            reasons.append(f"{label}达到预警阈值：{value}")
            return 1
        return 0

    def _check_range(self, name: str, value: float, hits: List[str], reasons: List[str], label: str) -> int:
        threshold = self.thresholds[name]
        if value <= float(threshold["alarm_low"]) or value >= float(threshold["alarm_high"]):
            hits.append(f"{name.upper()}_ALARM")
            reasons.append(f"{label}达到报警范围：{value}")
            return 2
        if value <= float(threshold["warning_low"]) or value >= float(threshold["warning_high"]):
            hits.append(f"{name.upper()}_WARNING")
            reasons.append(f"{label}达到预警范围：{value}")
            return 1
        return 0

    @staticmethod
    def _suggestion_for_level(level: int) -> str:
        if level == 2:
            return "立即检查现场设备，保持本地报警与安全联动，不要依赖云端单独决策。"
        if level == 1:
            return "建议巡检散热、振动、负载和传感器状态，并持续观察趋势。"
        return "系统运行正常，保持常规监测。"
