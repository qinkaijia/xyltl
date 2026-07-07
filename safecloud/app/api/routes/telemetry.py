from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.telemetry import TelemetryCreate, TelemetryIngestResult, TelemetryRead
from app.services import telemetry_service


router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.post("", response_model=TelemetryIngestResult, status_code=status.HTTP_201_CREATED)
def ingest_telemetry(payload: TelemetryCreate, db: Session = Depends(get_db)):
    telemetry, alarms = telemetry_service.ingest_telemetry(db, payload)
    return {"telemetry": telemetry, "generated_alarms": alarms}


@router.get("/latest/{device_id}", response_model=TelemetryRead)
def latest_telemetry(device_id: str, db: Session = Depends(get_db)):
    telemetry = telemetry_service.latest_for_device(db, device_id)
    if not telemetry:
        raise HTTPException(status_code=404, detail="telemetry not found")
    return telemetry


@router.get("/history/{device_id}", response_model=list[TelemetryRead])
def telemetry_history(
    device_id: str,
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return telemetry_service.history_for_device(db, device_id, start_time, end_time, limit)
