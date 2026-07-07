from __future__ import annotations

import copy
import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]


DEFAULT_SCENARIO_FILE = "tests/scenarios/evaluate/normal.json"
DEFAULT_MOCK_SCENARIOS = [
    "tests/scenarios/evaluate/normal.json",
    "tests/scenarios/evaluate/temperature_warning.json",
    "tests/scenarios/evaluate/gas_alarm.json",
    "tests/scenarios/evaluate/vibration_alarm.json",
    "tests/scenarios/evaluate/sensor_offline.json",
]

DEFAULT_2K0301_SENSOR_TOPIC = "device/2k0301/sensor"
DEFAULT_2K0301_HEARTBEAT_TOPIC = "device/2k0301/heartbeat"
DEFAULT_2K0301_ACK_TOPIC = "device/2k0301/ack"
DEFAULT_2K0301_ERROR_TOPIC = "device/2k0301/error"
DEFAULT_2K0301_COMMAND_TOPIC = "device/2k0301/command"


class SensorSourceError(RuntimeError):
    pass


@dataclass
class Mqtt2K0301Config:
    host: str = "127.0.0.1"
    port: int = 1883
    sensor_topic: str = DEFAULT_2K0301_SENSOR_TOPIC
    heartbeat_topic: str = DEFAULT_2K0301_HEARTBEAT_TOPIC
    ack_topic: str = DEFAULT_2K0301_ACK_TOPIC
    error_topic: str = DEFAULT_2K0301_ERROR_TOPIC
    command_topic: str = DEFAULT_2K0301_COMMAND_TOPIC
    qos: int = 1
    first_message_timeout: float = 8.0
    stale_after_seconds: float = 5.0
    client_id: str = ""

    @classmethod
    def from_env(cls) -> "Mqtt2K0301Config":
        return cls(
            host=os.environ.get("XYLT_2K0301_MQTT_HOST", "127.0.0.1"),
            port=_int_env("XYLT_2K0301_MQTT_PORT", 1883),
            sensor_topic=os.environ.get("XYLT_2K0301_SENSOR_TOPIC", DEFAULT_2K0301_SENSOR_TOPIC),
            heartbeat_topic=os.environ.get("XYLT_2K0301_HEARTBEAT_TOPIC", DEFAULT_2K0301_HEARTBEAT_TOPIC),
            ack_topic=os.environ.get("XYLT_2K0301_ACK_TOPIC", DEFAULT_2K0301_ACK_TOPIC),
            error_topic=os.environ.get("XYLT_2K0301_ERROR_TOPIC", DEFAULT_2K0301_ERROR_TOPIC),
            command_topic=os.environ.get("XYLT_2K0301_COMMAND_TOPIC", DEFAULT_2K0301_COMMAND_TOPIC),
            qos=_int_env("XYLT_2K0301_MQTT_QOS", 1),
            first_message_timeout=_float_env("XYLT_2K0301_FIRST_TIMEOUT", 8.0),
            stale_after_seconds=_float_env("XYLT_2K0301_STALE_AFTER", 5.0),
            client_id=os.environ.get("XYLT_2K0301_MQTT_CLIENT_ID", ""),
        )


class SensorSource:
    def next_payload(self) -> Dict[str, Any]:
        raise NotImplementedError


class ScenarioFileSource(SensorSource):
    def __init__(self, scenario_file: str) -> None:
        self.scenario_file = scenario_file

    def next_payload(self) -> Dict[str, Any]:
        return load_payload_file(self.scenario_file)


class MockSensorSource(SensorSource):
    def __init__(self, scenario_files: Optional[Iterable[str]] = None) -> None:
        self._scenario_files: List[str] = list(scenario_files or DEFAULT_MOCK_SCENARIOS)
        if not self._scenario_files:
            raise SensorSourceError("mock scenario list must not be empty")
        self._index = 0

    def next_payload(self) -> Dict[str, Any]:
        scenario_file = self._scenario_files[self._index % len(self._scenario_files)]
        self._index += 1
        payload = load_payload_file(scenario_file)
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()
        return payload


class Future2K0301Source(SensorSource):
    def __init__(self, config: Optional[Mqtt2K0301Config] = None) -> None:
        self.config = config or Mqtt2K0301Config.from_env()
        self._lock = threading.Lock()
        self._latest_sensor: Optional[Dict[str, Any]] = None
        self._latest_sensor_monotonic = 0.0
        self._latest_heartbeat: Optional[Dict[str, Any]] = None
        self._latest_heartbeat_monotonic = 0.0
        self._last_ack: Optional[Dict[str, Any]] = None
        self._last_error: Optional[Dict[str, Any]] = None
        self._message_event = threading.Event()
        self._client = self._create_client()
        self._connect()

    def next_payload(self) -> Dict[str, Any]:
        if self._latest_sensor is None:
            self._message_event.wait(self.config.first_message_timeout)

        with self._lock:
            latest_sensor = copy.deepcopy(self._latest_sensor)
            latest_heartbeat = copy.deepcopy(self._latest_heartbeat)
            last_error = copy.deepcopy(self._last_error)
            sensor_age = time.monotonic() - self._latest_sensor_monotonic if self._latest_sensor else None
            heartbeat_age = time.monotonic() - self._latest_heartbeat_monotonic if self._latest_heartbeat else None

        if latest_sensor is None:
            return build_2k0301_offline_payload("尚未收到 2K0301 sensor_packet", latest_heartbeat, last_error)
        if sensor_age is not None and sensor_age > self.config.stale_after_seconds:
            return build_2k0301_offline_payload("2K0301 sensor_packet 超时", latest_heartbeat, last_error)
        state = latest_sensor.setdefault("system_state", {})
        if latest_heartbeat:
            state["actuator_online"] = bool(latest_heartbeat.get("actuator_online", True))
            state["heartbeat_seq"] = latest_heartbeat.get("seq")
            state["heartbeat_error_flags"] = latest_heartbeat.get("error_flags", [])
            if latest_heartbeat.get("sensor_online") is False:
                state["sensor_online"] = False
                state["last_2k0301_error"] = "2K0301 heartbeat reported sensor_online=false"
        if heartbeat_age is not None and heartbeat_age > self.config.stale_after_seconds:
            state["sensor_online"] = False
            state["last_2k0301_error"] = "2K0301 heartbeat 超时"
        if last_error:
            state["last_2k0301_reported_error"] = last_error
        return latest_sensor

    def close(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    def publish_command(self, command: Dict[str, Any]) -> None:
        payload = json.dumps(command, ensure_ascii=False)
        self._client.publish(self.config.command_topic, payload, qos=self.config.qos)

    def _create_client(self):
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:
            raise SensorSourceError("缺少 paho-mqtt 依赖，请安装：pip3 install paho-mqtt") from exc

        client_id = self.config.client_id or "xylt-2k1000la-%d" % os.getpid()
        try:
            client = mqtt.Client(client_id=client_id)
        except TypeError:
            client = mqtt.Client(client_id)
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect
        return client

    def _connect(self) -> None:
        try:
            self._client.connect(self.config.host, self.config.port, keepalive=30)
            self._client.loop_start()
        except OSError as exc:
            raise SensorSourceError(
                "连接 2K0301 MQTT Broker 失败：%s:%s" % (self.config.host, self.config.port)
            ) from exc

    def _on_connect(self, client, _userdata, _flags, rc, *_extra) -> None:
        if rc != 0:
            with self._lock:
                self._last_error = {
                    "type": "error",
                    "error_code": "MQTT_CONNECT_FAILED",
                    "message": "MQTT connect rc=%s" % rc,
                }
            return
        for topic in (
            self.config.sensor_topic,
            self.config.heartbeat_topic,
            self.config.ack_topic,
            self.config.error_topic,
        ):
            client.subscribe(topic, qos=self.config.qos)

    def _on_disconnect(self, _client, _userdata, rc, *_extra) -> None:
        if rc != 0:
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

        now = time.monotonic()
        with self._lock:
            if message.topic == self.config.sensor_topic:
                try:
                    self._latest_sensor = transform_2k0301_sensor_message(data)
                    self._latest_sensor_monotonic = now
                    self._message_event.set()
                except SensorSourceError as exc:
                    self._last_error = {
                        "type": "error",
                        "error_code": "BAD_SENSOR_PACKET",
                        "message": str(exc),
                        "raw": data,
                    }
            elif message.topic == self.config.heartbeat_topic:
                self._latest_heartbeat = data
                self._latest_heartbeat_monotonic = now
                self._message_event.set()
            elif message.topic == self.config.ack_topic:
                self._last_ack = data
            elif message.topic == self.config.error_topic:
                self._last_error = data


def create_sensor_source(
    source_type: str,
    scenario_file: str = DEFAULT_SCENARIO_FILE,
    mqtt_config: Optional[Mqtt2K0301Config] = None,
) -> SensorSource:
    if source_type == "scenario":
        return ScenarioFileSource(scenario_file)
    if source_type == "mock":
        return MockSensorSource()
    if source_type == "2k0301":
        return Future2K0301Source(mqtt_config)
    raise SensorSourceError("未知 sensor source: %s" % source_type)


def transform_2k0301_sensor_message(message: Dict[str, Any]) -> Dict[str, Any]:
    if message.get("type") != "sensor_packet":
        raise SensorSourceError("期望 sensor_packet，实际收到：%s" % message.get("type"))
    payload = message.get("payload")
    if not isinstance(payload, dict):
        raise SensorSourceError("sensor_packet 缺少 payload")

    device_id = str(payload.get("device_id") or "board_2k0301")
    temperature = number(payload.get("temperature"), 0.0)
    humidity = number(payload.get("humidity"), 0.0)
    tvoc = number(payload.get("tvoc"), 0.0)
    eco2 = number(payload.get("eco2"), 400.0)
    mq3_value = number(payload.get("mq3_value"), 0.0)
    risk_score = number(payload.get("risk_score"), 0.0)
    flame_detected = bool(payload.get("flame_detected", False))
    gas = normalize_2k0301_gas(tvoc, eco2, mq3_value, risk_score, flame_detected)

    return {
        "device_id": device_id,
        "timestamp": _normalize_timestamp(payload.get("timestamp")),
        "metrics": {
            "temperature": temperature,
            "humidity": humidity,
            "gas": gas,
            "vibration": 0.0,
            "current": 0.0,
        },
        "system_state": {
            "cloud_connected": True,
            "voice_state": "idle",
            "sensor_online": True,
            "actuator_online": True,
            "flame_detected": flame_detected,
            "source": "2k0301_mqtt",
            "source_seq": message.get("seq"),
            "raw_tvoc": tvoc,
            "raw_eco2": eco2,
            "raw_mq3_value": mq3_value,
            "raw_risk_score": risk_score,
        },
    }


def normalize_2k0301_gas(
    tvoc: float,
    eco2: float,
    mq3_value: float,
    risk_score: float,
    flame_detected: bool = False,
) -> float:
    if flame_detected:
        return 1.0
    tvoc_score = _clamp(tvoc / 60000.0)
    eco2_score = _clamp((eco2 - 400.0) / (60000.0 - 400.0))
    mq3_score = _clamp(mq3_value / 999.0)
    risk_score_value = _clamp(risk_score / 100.0)
    return round(max(tvoc_score, eco2_score, mq3_score, risk_score_value), 4)


def build_2k0301_offline_payload(
    reason: str,
    latest_heartbeat: Optional[Dict[str, Any]] = None,
    last_error: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    device_id = "board_2k0301"
    if latest_heartbeat and latest_heartbeat.get("device_id"):
        device_id = str(latest_heartbeat["device_id"])
    return {
        "device_id": device_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "temperature": 0.0,
            "humidity": 0.0,
            "gas": 0.0,
            "vibration": 0.0,
            "current": 0.0,
        },
        "system_state": {
            "cloud_connected": True,
            "voice_state": "idle",
            "sensor_online": False,
            "actuator_online": bool(latest_heartbeat and latest_heartbeat.get("actuator_online", False)),
            "source": "2k0301_mqtt",
            "last_2k0301_error": reason,
            "last_2k0301_reported_error": last_error,
        },
    }


def load_payload_file(path: str) -> Dict[str, Any]:
    payload_path = Path(path)
    if not payload_path.is_absolute():
        payload_path = REPO_ROOT / payload_path
    try:
        data = json.loads(payload_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SensorSourceError("读取数据源失败：%s" % payload_path) from exc
    except json.JSONDecodeError as exc:
        raise SensorSourceError("数据源 JSON 格式错误：%s" % payload_path) from exc
    return copy.deepcopy(data.get("request", data))


def apply_runtime_options(
    payload: Dict[str, Any],
    use_real_llm: bool,
    force_model: str,
    include_debug: bool,
) -> Dict[str, Any]:
    prepared = copy.deepcopy(payload)
    prepared["use_real_llm"] = bool(use_real_llm)
    prepared["force_model"] = force_model
    prepared["include_debug"] = bool(include_debug)
    return prepared


def _normalize_timestamp(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return datetime.now(timezone.utc).isoformat()
    return text


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def number(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
