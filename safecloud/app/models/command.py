from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_command_id() -> str:
    return f"cmd-{uuid4().hex[:12]}"


class Command(Base):
    __tablename__ = "commands"

    command_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_command_id)
    device_id: Mapped[str] = mapped_column(String(64), ForeignKey("devices.device_id"), index=True)
    command_type: Mapped[str] = mapped_column(String(64), index=True)
    command_payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_message: Mapped[str | None] = mapped_column(Text, nullable=True)
