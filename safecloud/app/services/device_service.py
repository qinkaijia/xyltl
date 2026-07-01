from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.device import Device
from app.schemas.device import DeviceCreate, DeviceUpdate


def create_device(db: Session, payload: DeviceCreate) -> Device:
    device = Device(**payload.model_dump())
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def list_devices(db: Session) -> list[Device]:
    return db.query(Device).order_by(Device.created_at.desc()).all()


def get_device(db: Session, device_id: str) -> Device | None:
    return db.get(Device, device_id)


def update_device(db: Session, device: Device, payload: DeviceUpdate) -> Device:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(device, field, value)
    db.commit()
    db.refresh(device)
    return device


def ensure_device(db: Session, device_id: str) -> Device:
    device = get_device(db, device_id)
    if device:
        return device
    device = Device(
        device_id=device_id,
        device_name=device_id,
        device_type="gateway",
        status="online",
        description="Auto-created by telemetry ingestion.",
    )
    db.add(device)
    db.flush()
    return device


def mark_seen(db: Session, device: Device) -> Device:
    device.status = "online"
    device.last_seen = datetime.now(timezone.utc)
    db.flush()
    return device
