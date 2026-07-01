from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.alarm import Alarm
from app.schemas.alarm import AlarmHandle, AlarmRead
from app.services import alarm_service


router = APIRouter(prefix="/alarms", tags=["alarms"])


@router.get("", response_model=list[AlarmRead])
def list_alarms(status: str | None = None, db: Session = Depends(get_db)):
    return alarm_service.list_alarms(db, status=status)


@router.get("/{device_id}", response_model=list[AlarmRead])
def list_device_alarms(device_id: str, status: str | None = None, db: Session = Depends(get_db)):
    return alarm_service.list_alarms(db, device_id=device_id, status=status)


@router.put("/{alarm_id}/handle", response_model=AlarmRead)
def handle_alarm(alarm_id: str, payload: AlarmHandle, db: Session = Depends(get_db)):
    alarm = db.get(Alarm, alarm_id)
    if not alarm:
        raise HTTPException(status_code=404, detail="alarm not found")
    return alarm_service.handle_alarm(db, alarm)
