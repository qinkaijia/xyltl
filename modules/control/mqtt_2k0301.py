from __future__ import annotations

import json
import os
import threading
import time
import zlib
from dataclasses import dataclass
from typing import Any, Dict, Optional


DEFAULT_COMMAND_TOPIC = "device/board_2k0301/command"
DEFAULT_ACK_TOPIC = "device/board_2k0301/ack"
DEFAULT_ERROR_TOPIC = "device/board_2k0301/error"

ALLOWED_COMMANDS = {
    "fan_control",
    "buzzer_control",
    "alarm_light",
    "device_reset",
}

INTENT_TO_COMMAND = {
    "FAN_CONTROL": "fan_control",
    "BUZZER_CONTROL": "buzzer_control",
    "ALARM_LIGHT": "alarm_light",
    "DEVICE_RESET": "device_reset",
}


@dataclass
class MqttCommandConfig:
    host: str = "127.0.0.1"
    port: int = 1883
    command_topic: str = DEFAULT_COMMAND_TOPIC
    ack_topic: str = DEFAULT_ACK_TOPIC
    error_topic: str = DEFAULT_ERROR_TOPIC
    qos: int = 1
    client_id: str = ""

    @classmethod
    def from_env(cls, prefix: str = "XYLT_2K0301") -> "MqttCommandConfig":
        return cls(
            host=os.environ.get(f"{prefix}_MQTT_HOST", "127.0.0.1"),
            port=_int_env(f"{prefix}_MQTT_PORT", 1883),
            command_topic=os.environ.get(f"{prefix}_COMMAND_TOPIC", DEFAULT_COMMAND_TOPIC),
            ack_topic=os.environ.get(f"{prefix}_ACK_TOPIC", DEFAULT_ACK_TOPIC),
            error_topic=os.environ.get(f"{prefix}_ERROR_TOPIC", DEFAULT_ERROR_TOPIC),
            qos=_int_env(f"{prefix}_MQTT_QOS", 1),
            client_id=os.environ.get(f"{prefix}_MQTT_CLIENT_ID", ""),
        )


class MqttCommandError(RuntimeError):
    pass


class Mqtt2K0301CommandClient:
    def __init__(self, config: Optional[MqttCommandConfig] = None) -> None:
        self.config = config or MqttCommandConfig.from_env()
        self._ack_event = threading.Event()
        self._connect_event = threading.Event()
        self._lock = threading.Lock()
        self._target_seq: Optional[int] = None
        self._ack: Optional[Dict[str, Any]] = None
        self._last_error: Optional[Dict[str, Any]] = None
        self._client = self._create_client()

    def send_command(
        self,
        command_type: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        command_id: str = "",
        timeout: float = 3.0,
    ) -> Dict[str, Any]:
        message = build_command_message(command_type, params or {}, command_id=command_id)
        return self.publish_and_wait(message, timeout=timeout)

    def publish_and_wait(self, message: Dict[str, Any], timeout: float = 3.0) -> Dict[str, Any]:
        seq = int(message["seq"])
        payload = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        started = time.time()
        self._target_seq = seq

        try:
            self._client.connect(self.config.host, self.config.port, keepalive=30)
            self._client.loop_start()
            if not self._connect_event.wait(min(max(timeout, 0.5), 5.0)):
                raise MqttCommandError("MQTT connect timeout")

            info = self._client.publish(self.config.command_topic, payload, qos=self.config.qos)
            try:
                info.wait_for_publish(timeout=timeout)
            except TypeError:
                info.wait_for_publish()

            if not self._ack_event.wait(timeout):
                return {
                    "ok": False,
                    "status": "ack_timeout",
                    "seq": seq,
                    "command": message,
                    "ack": None,
                    "error": "ACK timeout",
                    "elapsed_ms": int((time.time() - started) * 1000),
                }

            with self._lock:
                ack = dict(self._ack or {})
                last_error = dict(self._last_error or {}) if self._last_error else None
            ok = bool(ack.get("ok", False))
            return {
                "ok": ok,
                "status": "ack_ok" if ok else "ack_failed",
                "seq": seq,
                "command": message,
                "ack": ack,
                "error": last_error,
                "elapsed_ms": int((time.time() - started) * 1000),
            }
        except Exception as exc:  # noqa: BLE001 - field diagnostics should return structured failures.
            return {
                "ok": False,
                "status": "mqtt_error",
                "seq": seq,
                "command": message,
                "ack": None,
                "error": str(exc),
                "elapsed_ms": int((time.time() - started) * 1000),
            }
        finally:
            self.close()

    def close(self) -> None:
        try:
            self._client.loop_stop()
        except Exception:
            pass
        try:
            self._client.disconnect()
        except Exception:
            pass

    def _create_client(self):
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:
            raise MqttCommandError("missing paho-mqtt dependency; install paho-mqtt") from exc

        client_id = self.config.client_id or "xylt-control-%d-%d" % (os.getpid(), int(time.time() * 1000))
        try:
            client = mqtt.Client(client_id=client_id)
        except TypeError:
            client = mqtt.Client(client_id)
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect
        return client

    def _on_connect(self, client, _userdata, _flags, rc, *_extra) -> None:
        if not _is_success_rc(rc):
            with self._lock:
                self._last_error = {
                    "type": "error",
                    "error_code": "MQTT_CONNECT_FAILED",
                    "message": "MQTT connect rc=%s" % rc,
                }
            self._connect_event.set()
            return
        client.subscribe(self.config.ack_topic, qos=self.config.qos)
        client.subscribe(self.config.error_topic, qos=self.config.qos)
        self._connect_event.set()

    def _on_disconnect(self, _client, _userdata, rc, *_extra) -> None:
        if not _is_success_rc(rc):
            with self._lock:
                self._last_error = {
                    "type": "error",
                    "error_code": "MQTT_DISCONNECTED",
                    "message": "MQTT disconnected rc=%s" % rc,
                }

    def _on_message(self, _client, _userdata, message) -> None:
        try:
            data = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            with self._lock:
                self._last_error = {
                    "type": "error",
                    "error_code": "BAD_JSON",
                    "message": str(exc),
                    "topic": message.topic,
                }
            return

        if message.topic == self.config.error_topic:
            with self._lock:
                self._last_error = data
            return

        if message.topic == self.config.ack_topic and int(data.get("seq", -1)) == self._target_seq:
            with self._lock:
                self._ack = data
            self._ack_event.set()


def build_command_message(
    command_type: str,
    params: Optional[Dict[str, Any]] = None,
    *,
    seq: Optional[int] = None,
    command_id: str = "",
) -> Dict[str, Any]:
    command = str(command_type or "").strip()
    if command not in ALLOWED_COMMANDS:
        raise ValueError("unsupported command_type: %s" % command)
    return {
        "type": "command",
        "seq": int(seq if seq is not None else _make_seq(command_id)),
        "command": command,
        "params": normalize_command_params(command, params or {}),
    }


def normalize_command_params(command_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if command_type == "fan_control":
        state = _choice(params.get("state", "on"), {"on", "off"}, "on")
        result: Dict[str, Any] = {"state": state}
        if state == "on":
            result["speed"] = _int_range(params.get("speed", 60), 0, 100)
            result["duration_ms"] = _int_range(params.get("duration_ms", 1000), 0, 600000)
        return result

    if command_type == "buzzer_control":
        state = _choice(params.get("state", "on"), {"on", "off"}, "on")
        result = {"state": state}
        if state == "on":
            result["pattern"] = _choice(params.get("pattern", "fast"), {"slow", "fast", "continuous"}, "fast")
            result["duration_ms"] = _int_range(params.get("duration_ms", 1000), 0, 600000)
        return result

    if command_type == "alarm_light":
        state = str(params.get("state", "")).lower()
        mode = _choice(params.get("mode", "blink"), {"on", "blink", "off"}, "blink")
        if state == "off":
            mode = "off"
        result = {"mode": mode}
        if mode == "off":
            result["color"] = "off"
        else:
            result["color"] = _choice(params.get("color", "red"), {"red", "yellow", "green"}, "red")
            result["duration_ms"] = _int_range(params.get("duration_ms", 1000), 0, 600000)
        return result

    if command_type == "device_reset":
        return {"target": _choice(params.get("target", "actuator_state"), {"actuator_state"}, "actuator_state")}

    raise ValueError("unsupported command_type: %s" % command_type)


def command_type_from_intent(intent: str) -> str:
    command_type = INTENT_TO_COMMAND.get(str(intent or "").strip().upper())
    if not command_type:
        raise ValueError("intent cannot be mapped to 2K0301 command: %s" % intent)
    return command_type


def _make_seq(command_id: str = "") -> int:
    if command_id:
        return zlib.crc32(command_id.encode("utf-8")) & 0x7FFFFFFF
    return int(time.time() * 1000) & 0x7FFFFFFF


def _choice(value: Any, allowed: set[str], default: str) -> str:
    text = str(value or default).strip().lower()
    return text if text in allowed else default


def _int_range(value: Any, minimum: int, maximum: int) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _is_success_rc(rc: Any) -> bool:
    try:
        return int(rc) == 0
    except (TypeError, ValueError):
        return str(rc).strip().lower() in {"0", "success", "normal disconnection"}
