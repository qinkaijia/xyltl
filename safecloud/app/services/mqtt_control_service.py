from __future__ import annotations

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
    return bool(settings.mqtt_control_host) or settings.mqtt_control_enabled


def dispatch_to_2k0301(payload: CommandCreate, command_id: str) -> dict[str, Any] | None:
    if not direct_dispatch_enabled():
        return None

    settings = get_settings()
    config = MqttCommandConfig(
        host=settings.mqtt_control_host or "127.0.0.1",
        port=settings.mqtt_control_port,
        qos=settings.mqtt_control_qos,
    )
    client = Mqtt2K0301CommandClient(config)
    return client.send_command(
        payload.command_type,
        payload.command_payload,
        command_id=command_id,
        timeout=settings.mqtt_control_ack_timeout,
    )
