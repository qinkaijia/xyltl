from datetime import datetime

from sqlalchemy.orm import Session

from app.models.telemetry import TelemetryData
from app.schemas.telemetry import TelemetryCreate
from app.services import alarm_service, device_service


def ingest_telemetry(db: Session, payload: TelemetryCreate) -> tuple[TelemetryData, list]:
    device = device_service.ensure_device(db, payload.device_id)
    device_service.mark_seen(db, device)

    telemetry = TelemetryData(
        device_id=payload.device_id,
        timestamp=payload.timestamp,
        metrics=payload.metrics,
        raw_payload=payload.model_dump(mode="json"),
    )
    db.add(telemetry)
    db.flush()

    alarms = alarm_service.evaluate_telemetry(db, payload.device_id, payload.metrics)
    db.commit()
    db.refresh(telemetry)
    for alarm in alarms:
        db.refresh(alarm)
    return telemetry, alarms


def latest_for_device(db: Session, device_id: str) -> TelemetryData | None:
    return (
        db.query(TelemetryData)
        .filter(TelemetryData.device_id == device_id)
        .order_by(TelemetryData.timestamp.desc(), TelemetryData.id.desc())
        .first()
    )


def history_for_device(
    db: Session,
    device_id: str,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 200,
) -> list[TelemetryData]:
    query = db.query(TelemetryData).filter(TelemetryData.device_id == device_id)
    if start_time:
        query = query.filter(TelemetryData.timestamp >= start_time)
    if end_time:
        query = query.filter(TelemetryData.timestamp <= end_time)
    return query.order_by(TelemetryData.timestamp.desc()).limit(limit).all()
