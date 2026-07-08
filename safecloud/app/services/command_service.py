from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.command import Command
from app.schemas.command import CommandCreate, CommandResult


def create_command(db: Session, payload: CommandCreate) -> Command:
    command = Command(**payload.model_dump())
    db.add(command)
    db.commit()
    db.refresh(command)
    return command


def pending_commands(db: Session, device_id: str) -> list[Command]:
    commands = (
        db.query(Command)
        .filter(Command.device_id == device_id, Command.status == "pending")
        .order_by(Command.created_at.asc())
        .all()
    )
    now = datetime.now(timezone.utc)
    for command in commands:
        command.status = "sent"
        command.sent_at = now
    db.commit()
    for command in commands:
        db.refresh(command)
    return commands


def update_command_result(db: Session, command: Command, payload: CommandResult) -> Command:
    command.status = payload.status
    command.result_message = payload.result_message
    command.executed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(command)
    return command


def apply_delivery_result(db: Session, command: Command, delivery: dict) -> Command:
    now = datetime.now(timezone.utc)
    command.sent_at = now
    command.executed_at = now
    command.status = "executed" if delivery.get("ok") else "failed"
    ack = delivery.get("ack") or {}
    command.result_message = (
        ack.get("message")
        or ack.get("error_code")
        or delivery.get("error")
        or delivery.get("status")
        or "command delivery finished"
    )
    db.commit()
    db.refresh(command)
    return command
