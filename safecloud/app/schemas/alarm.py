from datetime import datetime

from pydantic import BaseModel


class AlarmRead(BaseModel):
    alarm_id: str
    device_id: str
    alarm_type: str
    alarm_level: str
    alarm_message: str
    metric_name: str | None = None
    metric_value: float | None = None
    threshold_value: float | None = None
    status: str
    created_at: datetime
    handled_at: datetime | None = None

    model_config = {"from_attributes": True}


class AlarmHandle(BaseModel):
    result_message: str | None = None
