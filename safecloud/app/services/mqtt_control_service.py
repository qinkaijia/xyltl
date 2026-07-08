from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.schemas.command import CommandCreate


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from modules.control import Mqtt2K0301CommandClient, MqttCommandConfig  # noqa: E402


def direct_dispatch_enabled() -> bool:
    settings = get_settings()
    env_host = os.getenv("SAFECLOUD_2K0301_MQTT_HOST", "").strip() or os.getenv("XYLT_2K0301_MQTT_HOST", "").strip()
    return bool(env_host or settings.mqtt_control_host) or settings.mqtt_control_enabled


def dispatch_to_2k0301(payload: CommandCreate, command_id: str) -> dict[str, Any] | None:
    if not direct_dispatch_enabled():
        return None

    settings = get_settings()
    host = (
        os.getenv("SAFECLOUD_2K0301_MQTT_HOST", "").strip()
        or settings.mqtt_control_host
        or os.getenv("XYLT_2K0301_MQTT_HOST", "").strip()
        or "127.0.0.1"
    )
    port = int(os.getenv("SAFECLOUD_2K0301_MQTT_PORT", "") or settings.mqtt_control_port)
    config = MqttCommandConfig(
        host=host,
        port=port,
        qos=settings.mqtt_control_qos,
    )
    client = Mqtt2K0301CommandClient(config)
    delivery = client.send_command(
        payload.command_type,
        payload.command_payload,
        command_id=command_id,
        timeout=settings.mqtt_control_ack_timeout,
    )
    delivery["transport_target"] = f"{host}:{port}"
    return delivery
