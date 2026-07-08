from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.alarm import Alarm
from app.models.device import Device
from app.models.telemetry import TelemetryData
from app.schemas.dashboard import DashboardSummary
from app.services import analyzer_service
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

    extensions = {
        "frontend_hint": "Ready for ECharts/Vue/React dashboards",
        "latest_telemetry_count": len(latest_telemetry),
    }
    latest = analyzer_service.latest_evaluation()
    final_status = ((latest or {}).get("response") or {}).get("final_status") if latest else None
    if isinstance(final_status, dict):
        gateway_online = final_status.get("cloud_connected") is not False
        sensor_online = final_status.get("sensor_online") is not False
        device_total = 2
        online_device_total = int(gateway_online) + int(sensor_online)
        active_alarm_total = 1 if int(final_status.get("alarm_level") or 0) > 0 else 0
        device_status = {
            "online": online_device_total,
            "offline": device_total - online_device_total,
        }
        metric_names = [
            "temperature",
            "humidity",
            "tvoc",
            "eco2",
            "mq3_value",
            "flame_detected",
            "risk_score",
        ]
        extensions["latest_evaluate_status"] = {
            key: final_status.get(key)
            for key in (
                "device_id",
                "timestamp",
                "alarm_level",
                "status_text",
                "sensor_online",
                "actuator_online",
                "reason",
            )
        }

    return {
        "device_total": device_total,
        "online_device_total": online_device_total,
        "active_alarm_total": active_alarm_total,
        "latest_telemetry": latest_telemetry,
        "recent_alarms": recent_alarms,
        "device_status": dict(device_status),
        "metric_names": sorted(metric_names),
        "extensions": extensions,
    }
