from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import random
from typing import List


@dataclass
class DeviceState:
    detecting: bool = False
    temperature: float = 36.5
    humidity: float = 52.0
    pressure: float = 101.3
    vibration: str = "normal"
    alarms: List[str] = field(default_factory=list)
    uploaded: bool = False
    last_report: str = ""

    def get_context(self) -> dict:
        return {
            "detecting": self.detecting,
            "temperature": round(self.temperature, 1),
            "humidity": round(self.humidity, 1),
            "pressure": round(self.pressure, 1),
            "vibration": self.vibration,
            "alarms": list(self.alarms),
            "uploaded": self.uploaded,
            "last_report": self.last_report,
        }

    def update_simulated_data(self) -> None:
        if self.detecting:
            self.temperature = max(20.0, self.temperature + random.uniform(-0.8, 1.8))
            self.humidity = min(95.0, max(20.0, self.humidity + random.uniform(-2.0, 2.0)))
            self.pressure = max(80.0, self.pressure + random.uniform(-0.5, 0.5))
            if random.random() < 0.15:
                self.vibration = "abnormal"
            elif random.random() < 0.35:
                self.vibration = "normal"

        alarms = set(self.alarms)
        if self.temperature > 60:
            alarms.add("temperature_high")
        else:
            alarms.discard("temperature_high")

        if self.vibration == "abnormal":
            alarms.add("vibration_abnormal")
        else:
            alarms.discard("vibration_abnormal")

        self.alarms = sorted(alarms)

    def generate_report(self) -> str:
        context = self.get_context()
        alarm_text = "、".join(context["alarms"]) if context["alarms"] else "无报警"
        self.last_report = (
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 检测报告："
            f"检测状态={context['detecting']}，温度={context['temperature']}℃，"
            f"湿度={context['humidity']}%，压力={context['pressure']}kPa，"
            f"振动={context['vibration']}，报警={alarm_text}。"
        )
        return self.last_report
