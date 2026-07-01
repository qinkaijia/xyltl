from datetime import datetime

from pydantic import BaseModel, Field


class DeviceBase(BaseModel):
    device_name: str = Field(..., examples=["一号边缘网关"])
    device_type: str = Field(default="gateway", examples=["gateway"])
    location: str | None = Field(default=None, examples=["实验室演示舱"])
    status: str = Field(default="offline", examples=["online"])
    firmware_version: str | None = Field(default=None, examples=["v0.1.0"])
    description: str | None = None


class DeviceCreate(DeviceBase):
    device_id: str = Field(..., examples=["gateway_001"])


class DeviceUpdate(BaseModel):
    device_name: str | None = None
    device_type: str | None = None
    location: str | None = None
    status: str | None = None
    firmware_version: str | None = None
    description: str | None = None


class DeviceRead(DeviceBase):
    device_id: str
    last_seen: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
