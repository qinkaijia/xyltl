from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_alarm_id() -> str:
    return f"alm-{uuid4().hex[:12]}"


class Alarm(Base):
    __tablename__ = "alarms"

    alarm_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_alarm_id)
    device_id: Mapped[str] = mapped_column(String(64), ForeignKey("devices.device_id"), index=True)
    alarm_type: Mapped[str] = mapped_column(String(64), default="threshold")
    alarm_level: Mapped[str] = mapped_column(String(16), default="warning", index=True)
    alarm_message: Mapped[str] = mapped_column(Text)
    metric_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
