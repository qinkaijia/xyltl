from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.command import Command
from app.schemas.command import CommandCreate, CommandRead, CommandResult
from app.services import command_service, device_service, mqtt_control_service


router = APIRouter(prefix="/commands", tags=["commands"])


@router.post("", response_model=CommandRead, status_code=status.HTTP_201_CREATED)
def create_command(payload: CommandCreate, db: Session = Depends(get_db)):
    if not device_service.get_device(db, payload.device_id):
        device_service.ensure_device(db, payload.device_id)
        db.commit()
    command = command_service.create_command(db, payload)
    delivery = mqtt_control_service.dispatch_to_2k0301(payload, command.command_id)
    if delivery is None:
        return command

    command = command_service.apply_delivery_result(db, command, delivery)
    return {
        **CommandRead.model_validate(command).model_dump(),
        "delivery_status": delivery.get("status"),
        "delivery_elapsed_ms": delivery.get("elapsed_ms"),
        "ack": delivery.get("ack"),
        "transport_error": delivery.get("error"),
    }


@router.get("/pending/{device_id}", response_model=list[CommandRead])
def pending_commands(device_id: str, db: Session = Depends(get_db)):
    return command_service.pending_commands(db, device_id)


@router.put("/{command_id}/result", response_model=CommandRead)
def command_result(command_id: str, payload: CommandResult, db: Session = Depends(get_db)):
    command = db.get(Command, command_id)
    if not command:
        raise HTTPException(status_code=404, detail="command not found")
    return command_service.update_command_result(db, command, payload)
