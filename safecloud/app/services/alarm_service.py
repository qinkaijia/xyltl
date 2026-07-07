from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.alarm import Alarm


def _to_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def evaluate_telemetry(db: Session, device_id: str, metrics: dict[str, Any]) -> list[Alarm]:
    settings = get_settings()
    generated: list[Alarm] = []

    for metric_name, threshold_value in settings.metric_thresholds.items():
        if metric_name not in metrics:
            continue
        metric_value = _to_number(metrics[metric_name])
        if metric_value is None or metric_value <= threshold_value:
            continue

        alarm = Alarm(
            device_id=device_id,
            alarm_type="threshold",
            alarm_level="critical" if metric_value >= threshold_value * 1.5 else "warning",
            alarm_message=f"{metric_name}={metric_value} exceeds threshold {threshold_value}",
            metric_name=metric_name,
            metric_value=metric_value,
            threshold_value=threshold_value,
        )
        db.add(alarm)
        generated.append(alarm)

    db.flush()
    return generated


def list_alarms(db: Session, device_id: str | None = None, status: str | None = None) -> list[Alarm]:
    query = db.query(Alarm)
    if device_id:
        query = query.filter(Alarm.device_id == device_id)
    if status:
        query = query.filter(Alarm.status == status)
    return query.order_by(Alarm.created_at.desc()).all()


def handle_alarm(db: Session, alarm: Alarm) -> Alarm:
    alarm.status = "handled"
    alarm.handled_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alarm)
    return alarm
