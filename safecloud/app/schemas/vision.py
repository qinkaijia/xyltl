from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


VisionMode = Literal["cloud", "local", "off"]


class VisionEvaluateRequest(BaseModel):
    device_id: str = Field(default="board_2k1000la")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    image_base64: str
    image_mime: str = Field(default="image/jpeg")
    mode: VisionMode = Field(default="cloud")
    sensor_snapshot: dict[str, Any] = Field(default_factory=dict)
    include_debug: bool = Field(default=False)

    @field_validator("image_base64")
    @classmethod
    def image_base64_must_not_be_empty(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("image_base64 must not be empty")
        return text


class VisionEvaluateResponse(BaseModel):
    vision_status: dict[str, Any]
    debug: dict[str, Any] | None = None


class VisionModeRequest(BaseModel):
    mode: VisionMode


class VisionModeResponse(BaseModel):
    mode: VisionMode
