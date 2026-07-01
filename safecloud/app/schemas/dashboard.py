from typing import Any

from pydantic import BaseModel

from app.schemas.alarm import AlarmRead
from app.schemas.telemetry import TelemetryRead


class DashboardSummary(BaseModel):
    device_total: int
    online_device_total: int
    active_alarm_total: int
    latest_telemetry: list[TelemetryRead]
    recent_alarms: list[AlarmRead]
    device_status: dict[str, int]
    metric_names: list[str]
    extensions: dict[str, Any] = {}
