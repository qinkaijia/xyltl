from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class EvaluateRequest(BaseModel):
    device_id: str = Field(..., examples=["device_001"])
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metrics: dict[str, Any] = Field(
        ...,
        examples=[
            {
                "temperature": 72.5,
                "humidity": 61.0,
                "gas": 0.25,
                "vibration": 1.82,
                "current": 2.3,
            }
        ],
    )
    system_state: dict[str, Any] = Field(
        default_factory=dict,
        examples=[{"cloud_connected": True, "voice_state": "idle", "sensor_online": True}],
    )
    use_real_llm: bool = Field(default=False)
    force_model: Literal["", "deepseek", "kimi", "zhipu", "doubao", "qwen", "mock"] = ""
    include_debug: bool = Field(default=False)

    @field_validator("metrics")
    @classmethod
    def metrics_must_not_be_empty(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("metrics must not be empty")
        return value


class EvaluateResponse(BaseModel):
    final_status: dict[str, Any]
    debug: dict[str, Any] | None = None
