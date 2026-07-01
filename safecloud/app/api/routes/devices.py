from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.device import DeviceCreate, DeviceRead, DeviceUpdate
from app.services import device_service


router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
def create_device(payload: DeviceCreate, db: Session = Depends(get_db)):
    if device_service.get_device(db, payload.device_id):
        raise HTTPException(status_code=409, detail="device_id already exists")
    return device_service.create_device(db, payload)


@router.get("", response_model=list[DeviceRead])
def list_devices(db: Session = Depends(get_db)):
    return device_service.list_devices(db)


@router.get("/{device_id}", response_model=DeviceRead)
def get_device(device_id: str, db: Session = Depends(get_db)):
    device = device_service.get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    return device


@router.put("/{device_id}", response_model=DeviceRead)
def update_device(device_id: str, payload: DeviceUpdate, db: Session = Depends(get_db)):
    device = device_service.get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    return device_service.update_device(db, device, payload)
