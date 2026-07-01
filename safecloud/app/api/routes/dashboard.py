from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.alarm import Alarm
from app.models.device import Device
from app.models.telemetry import TelemetryData
from app.schemas.dashboard import DashboardSummary
from app.services.telemetry_service import latest_for_device


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)):
    devices = db.query(Device).order_by(Device.created_at.desc()).all()
    device_total = len(devices)
    online_device_total = sum(1 for device in devices if device.status == "online")
    active_alarm_total = db.query(func.count(Alarm.alarm_id)).filter(Alarm.status == "active").scalar() or 0

    latest_telemetry = []
    metric_names: set[str] = set()
    for device in devices:
        telemetry = latest_for_device(db, device.device_id)
        if telemetry:
            latest_telemetry.append(telemetry)
            metric_names.update(telemetry.metrics.keys())

    recent_alarms = db.query(Alarm).order_by(Alarm.created_at.desc()).limit(10).all()
    device_status = Counter(device.status for device in devices)

    return {
        "device_total": device_total,
        "online_device_total": online_device_total,
        "active_alarm_total": active_alarm_total,
        "latest_telemetry": latest_telemetry,
        "recent_alarms": recent_alarms,
        "device_status": dict(device_status),
        "metric_names": sorted(metric_names),
        "extensions": {
            "frontend_hint": "Ready for ECharts/Vue/React dashboards",
            "latest_telemetry_count": len(latest_telemetry),
        },
    }
