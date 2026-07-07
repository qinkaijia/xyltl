from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


STATUS_TEXT = {
    0: "正常",
    1: "预警",
    2: "报警",
}


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class SensorData:
    device_id: str
    timestamp: str
    temperature: float
    humidity: float
    gas: float
    vibration: float
    current: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SensorData":
        return cls(
            device_id=str(data.get("device_id", "device_001")),
            timestamp=str(data.get("timestamp", now_text())),
            temperature=float(data.get("temperature", 0.0)),
            humidity=float(data.get("humidity", 0.0)),
            gas=float(data.get("gas", 0.0)),
            vibration=float(data.get("vibration", 0.0)),
            current=float(data.get("current", 0.0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SystemState:
    cloud_connected: bool = True
    voice_state: str = "idle"
    sensor_online: bool = True
    user_question: Optional[str] = None
    request_report: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SystemState":
        return cls(
            cloud_connected=bool(data.get("cloud_connected", True)),
            voice_state=str(data.get("voice_state", "idle")),
            sensor_online=bool(data.get("sensor_online", True)),
            user_question=data.get("user_question"),
            request_report=bool(data.get("request_report", False)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RuleResult:
    alarm_level: int
    status: str
    reason: str
    suggestion: str
    rule_hits: List[str] = field(default_factory=list)
    need_cloud_upload: bool = False
    need_voice_alert: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RouterDecision:
    selected_models: List[str]
    judge_model: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LLMAnalysisResult:
    model_name: str
    role: str
    alarm_level: int
    risk_summary: str
    possible_causes: List[str]
    suggestion: str
    confidence: float
    error: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMAnalysisResult":
        return cls(
            model_name=str(data.get("model_name", "unknown")),
            role=str(data.get("role", "general")),
            alarm_level=int(data.get("alarm_level", 0)),
            risk_summary=str(data.get("risk_summary", "")),
            possible_causes=list(data.get("possible_causes", [])),
            suggestion=str(data.get("suggestion", "")),
            confidence=float(data.get("confidence", 0.0)),
            error=data.get("error"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class JudgeResult:
    alarm_level: int
    main_reason: str
    possible_causes: List[str]
    suggestion: str
    voice_text: str
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FinalStatus:
    timestamp: str
    device_id: str
    alarm_level: int
    status_text: str
    temperature: float
    humidity: float
    gas: float
    vibration: float
    current: float
    reason: str
    suggestion: str
    voice_text: str
    cloud_connected: bool
    need_cloud_upload: bool
    need_voice_alert: bool
    analysis_mode: str
    source: Dict[str, bool]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
