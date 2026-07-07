from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TelemetryCreate(BaseModel):
    device_id: str = Field(..., examples=["gateway_001"])
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metrics: dict[str, Any] = Field(
        ...,
        examples=[{"temperature": 26.5, "humidity": 58.2, "gas": 120}],
    )

    @field_validator("metrics")
    @classmethod
    def metrics_must_not_be_empty(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("metrics must not be empty")
        return value


class TelemetryRead(BaseModel):
    id: int
    device_id: str
    timestamp: datetime
    metrics: dict[str, Any]
    raw_payload: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class TelemetryIngestResult(BaseModel):
    telemetry: TelemetryRead
    generated_alarms: list["AlarmRead"] = []


from app.schemas.alarm import AlarmRead  # noqa: E402

TelemetryIngestResult.model_rebuild()
