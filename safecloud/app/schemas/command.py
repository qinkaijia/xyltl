from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CommandCreate(BaseModel):
    device_id: str = Field(..., examples=["gateway_001"])
    command_type: str = Field(..., examples=["fan_control"])
    command_payload: dict[str, Any] = Field(default_factory=dict, examples=[{"state": "on"}])


class CommandResult(BaseModel):
    status: str = Field(..., examples=["executed"])
    result_message: str | None = Field(default=None, examples=["fan_control executed"])


class CommandRead(BaseModel):
    command_id: str
    device_id: str
    command_type: str
    command_payload: dict[str, Any]
    status: str
    created_at: datetime
    sent_at: datetime | None = None
    executed_at: datetime | None = None
    result_message: str | None = None

    model_config = {"from_attributes": True}
