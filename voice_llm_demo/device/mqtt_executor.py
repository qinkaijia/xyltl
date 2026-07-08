from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Tuple


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from modules.control import Mqtt2K0301CommandClient, MqttCommandConfig, command_type_from_intent  # noqa: E402


class MqttCommandExecutor:
    def __init__(self, host: str, port: int = 1883, qos: int = 1, ack_timeout: float = 3.0) -> None:
        self.config = MqttCommandConfig(host=host, port=port, qos=qos)
        self.ack_timeout = ack_timeout

    def execute(self, intent: str, params: Dict) -> Tuple[bool, str]:
        try:
            command_type = command_type_from_intent(intent)
            result = Mqtt2K0301CommandClient(self.config).send_command(
                command_type,
                params,
                timeout=self.ack_timeout,
            )
        except Exception as exc:  # noqa: BLE001 - keep field voice loop stable.
            return False, f"MQTT 控制执行失败：{exc}"

        ack = result.get("ack") or {}
        message = ack.get("message") or result.get("error") or result.get("status")
        if result.get("ok"):
            return True, f"301 ACK 成功：{message}"
        return False, f"301 ACK 失败：{message}"
