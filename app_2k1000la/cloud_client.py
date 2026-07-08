from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app_2k1000la.sensor_source import (
    DEFAULT_SCENARIO_FILE,
    Mqtt2K0301Config,
    SensorSourceError,
    apply_runtime_options,
    create_sensor_source,
)

try:
    from voice.voice_text_player import VoiceTextPlayer, extract_voice_text
except ImportError:
    VoiceTextPlayer = None  # type: ignore
    extract_voice_text = None  # type: ignore


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DISCOVER_MESSAGE = b"SAFECLOUD_DISCOVER"


class SafeCloudClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def health(self, timeout: Optional[float] = None) -> bool:
        try:
            with urllib.request.urlopen(self.base_url + "/health", timeout=timeout or self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return payload.get("status") == "ok"
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            return False

    def evaluate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + "/api/evaluate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))


def evaluate_with_fallback(client: SafeCloudClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    started = time.time()
    try:
        response = client.evaluate(payload)
        response.setdefault("debug", {})
        response["debug"]["client"] = {
            "ok": True,
            "elapsed_ms": int((time.time() - started) * 1000),
            "base_url": client.base_url,
        }
        enrich_final_status_with_2k0301_fields(response, payload)
        return response
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {
            "final_status": local_fallback_status(payload, str(exc)),
            "debug": {
                "client": {
                    "ok": False,
                    "elapsed_ms": int((time.time() - started) * 1000),
                    "base_url": client.base_url,
                    "error": str(exc),
                }
            },
        }


def resolve_base_url(
    cli_base_url: str,
    cache_file: str,
    discovery_port: int,
    discovery_timeout: float,
    no_discovery: bool,
) -> Tuple[str, str]:
    candidates = [
        ("cli", cli_base_url.strip()),
        ("env", os.environ.get("SAFECLOUD_BASE_URL", "").strip()),
        ("cache", load_cached_base_url(cache_file)),
    ]
    for source, url in candidates:
        if url and SafeCloudClient(url, timeout=discovery_timeout).health(timeout=discovery_timeout):
            if source != "cache":
                save_cached_base_url(cache_file, url)
            return url, source

    if not no_discovery:
        discovered = discover_safecloud(discovery_port, discovery_timeout)
        if discovered and SafeCloudClient(discovered, timeout=discovery_timeout).health(timeout=discovery_timeout):
            save_cached_base_url(cache_file, discovered)
            return discovered, "discovery"

    fallback = cli_base_url.strip() or os.environ.get("SAFECLOUD_BASE_URL", "").strip() or DEFAULT_BASE_URL
    return fallback, "fallback"


def discover_safecloud(discovery_port: int = 8011, timeout: float = 3.0) -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)
    try:
        sock.sendto(DISCOVER_MESSAGE, ("255.255.255.255", discovery_port))
        started = time.time()
        while time.time() - started < timeout:
            data, _addr = sock.recvfrom(4096)
            try:
                payload = json.loads(data.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            if payload.get("service") == "SafeCloud" and payload.get("base_url"):
                return str(payload["base_url"]).rstrip("/")
    except (OSError, socket.timeout):
        return ""
    finally:
        sock.close()
    return ""


def default_cache_file() -> str:
    return str(Path.home() / ".xylt_safecloud.json")


def load_cached_base_url(cache_file: str) -> str:
    try:
        data = json.loads(Path(cache_file).read_text(encoding="utf-8"))
        return str(data.get("base_url", "")).strip()
    except (OSError, json.JSONDecodeError):
        return ""


def save_cached_base_url(cache_file: str, base_url: str) -> None:
    path = Path(cache_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"base_url": base_url, "updated_at": datetime.now().isoformat(timespec="seconds")}, indent=2)
        + "\n",
        encoding="utf-8",
    )


def local_fallback_status(payload: Dict[str, Any], error: str = "") -> Dict[str, Any]:
    metrics = payload.get("metrics") or {}
    state = payload.get("system_state") or {}
    level, reason, hits = local_rule_evaluate(metrics, state)
    suggestion = (
        "云端请求失败，已启用端侧本地规则兜底；请保持现场巡检，关键动作按本地规则执行。"
        if level > 0
        else "云端请求失败，当前本地指标未触发预警；保持常规监测。"
    )
    status_text = {0: "正常", 1: "预警", 2: "报警"}.get(level, "未知")
    voice_text = f"当前设备处于{status_text}状态。{reason}。{suggestion}"
    status = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "device_id": payload.get("device_id", "2k1000la"),
        "alarm_level": level,
        "status_text": status_text,
        "temperature": number(metrics.get("temperature"), 0.0),
        "humidity": number(metrics.get("humidity"), 0.0),
        "gas": number(metrics.get("gas"), 0.0),
        "vibration": number(metrics.get("vibration"), 0.0),
        "current": number(metrics.get("current"), 0.0),
        "reason": reason,
        "suggestion": suggestion,
        "voice_text": voice_text,
        "cloud_connected": False,
        "need_cloud_upload": level > 0,
        "need_voice_alert": level > 0,
        "analysis_mode": "local_http_fallback",
        "source": {
            "rule_engine": True,
            "llm_analyzer": False,
            "judge_model": False,
            "safety_guard": True,
        },
        "client_error": error,
        "rule_hits": hits,
    }
    status.update(extract_2k0301_fields(payload))
    return status


def enrich_final_status_with_2k0301_fields(response: Dict[str, Any], payload: Dict[str, Any]) -> None:
    final_status = response.get("final_status")
    if isinstance(final_status, dict):
        final_status.update(extract_2k0301_fields(payload))


def extract_2k0301_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    metrics = payload.get("metrics") or {}
    state = payload.get("system_state") or {}
    fields = {
        "tvoc": number(metrics.get("tvoc", state.get("raw_tvoc")), 0.0),
        "eco2": number(metrics.get("eco2", state.get("raw_eco2")), 0.0),
        "mq3_value": number(metrics.get("mq3_value", state.get("raw_mq3_value")), 0.0),
        "flame_detected": bool(metrics.get("flame_detected", state.get("flame_detected", False))),
        "risk_score": number(metrics.get("risk_score", state.get("raw_risk_score")), 0.0),
        "sensor_online": bool(state.get("sensor_online", True)),
        "actuator_online": bool(state.get("actuator_online", True)),
        "sensor_source": state.get("source", ""),
    }
    fields["sensor_metrics"] = {
        "temperature": number(metrics.get("temperature"), 0.0),
        "humidity": number(metrics.get("humidity"), 0.0),
        "tvoc": fields["tvoc"],
        "eco2": fields["eco2"],
        "mq3_value": fields["mq3_value"],
        "flame_detected": fields["flame_detected"],
        "risk_score": fields["risk_score"],
    }
    return fields


def local_rule_evaluate(metrics: Dict[str, Any], state: Dict[str, Any]) -> Tuple[int, str, list[str]]:
    level = 0
    reasons = []
    hits = []
    sensor_online = state.get("sensor_online", True) is not False

    if not sensor_online:
        level = 2
        hits.append("SENSOR_OFFLINE")
        reasons.append("传感器离线，无法确认现场状态")

    if sensor_online:
        checks = [
            ("temperature", "温度", 60.0, 75.0),
            ("gas", "气体浓度", 0.3, 0.6),
        ]
        for key, label, warning, alarm in checks:
            value = number(metrics.get(key), 0.0)
            if value >= alarm:
                level = max(level, 2)
                hits.append(f"{key.upper()}_ALARM")
                reasons.append(f"{label}达到报警阈值：{value}")
            elif value >= warning:
                level = max(level, 1)
                hits.append(f"{key.upper()}_WARNING")
                reasons.append(f"{label}达到预警阈值：{value}")

        humidity = number(metrics.get("humidity"), 0.0)
        if humidity <= 10.0 or humidity >= 90.0:
            level = max(level, 2)
            hits.append("HUMIDITY_ALARM")
            reasons.append(f"湿度达到报警范围：{humidity}")
        elif humidity <= 20.0 or humidity >= 80.0:
            level = max(level, 1)
            hits.append("HUMIDITY_WARNING")
            reasons.append(f"湿度达到预警范围：{humidity}")

    if not reasons:
        reasons.append("所有关键指标处于正常范围")
    return level, "；".join(reasons), hits


def number(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_scenario(path: str) -> Dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("request", data)


def write_json(path: Optional[str], payload: Dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if not path:
        print(text)
        return
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text + "\n", encoding="utf-8")


def env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def status_needs_voice_alert(status: Dict[str, Any]) -> bool:
    return bool(status.get("need_voice_alert")) or number(status.get("alarm_level"), 0.0) > 0


def alert_signature(status: Dict[str, Any]) -> str:
    sensor_metrics = status.get("sensor_metrics") if isinstance(status.get("sensor_metrics"), dict) else {}
    payload = {
        "alarm_level": status.get("alarm_level"),
        "status_text": status.get("status_text"),
        "reason": status.get("reason"),
        "suggestion": status.get("suggestion"),
        "temperature": sensor_metrics.get("temperature", status.get("temperature")),
        "humidity": sensor_metrics.get("humidity", status.get("humidity")),
        "tvoc": sensor_metrics.get("tvoc", status.get("tvoc")),
        "eco2": sensor_metrics.get("eco2", status.get("eco2")),
        "mq3_value": sensor_metrics.get("mq3_value", status.get("mq3_value")),
        "flame_detected": sensor_metrics.get("flame_detected", status.get("flame_detected")),
        "risk_score": sensor_metrics.get("risk_score", status.get("risk_score")),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


class VoiceAlertManager:
    def __init__(self, enabled: bool, tts_mode: str = "", cooldown_seconds: float = 30.0) -> None:
        self.enabled = enabled
        self.tts_mode = tts_mode
        self.cooldown_seconds = max(0.0, cooldown_seconds)
        self.last_signature = ""
        self.last_spoken_at = 0.0

    def maybe_speak(self, response: Dict[str, Any], now: Optional[float] = None) -> bool:
        if not self.enabled:
            return False
        status = response.get("final_status")
        if not isinstance(status, dict):
            return False
        if not status_needs_voice_alert(status):
            return False

        current_time = time.time() if now is None else now
        signature = alert_signature(status)
        should_speak = (
            signature != self.last_signature
            or self.last_spoken_at <= 0
            or current_time - self.last_spoken_at >= self.cooldown_seconds
        )
        if not should_speak:
            return False

        spoken = speak_response(response, self.tts_mode)
        self.last_signature = signature
        self.last_spoken_at = current_time
        return spoken


def run_once(
    args: argparse.Namespace,
    client: SafeCloudClient,
    payload: Dict[str, Any],
    alert_manager: Optional[VoiceAlertManager] = None,
) -> Dict[str, Any]:
    response = evaluate_with_fallback(client, payload)
    if args.output_file:
        write_json(args.output_file, response)
    spoken = False
    if getattr(args, "speak", False):
        spoken = speak_response(response, args.tts_mode)
    elif alert_manager is not None:
        spoken = alert_manager.maybe_speak(response)

    final_status = response["final_status"]
    debug_client = (response.get("debug") or {}).get("client") or {}
    print(
        "evaluate_result "
        f"level={final_status['alarm_level']} "
        f"mode={final_status['analysis_mode']} "
        f"voice_alert={final_status['need_voice_alert']} "
        f"alert_spoken={spoken} "
        f"base_url={client.base_url} "
        f"elapsed_ms={debug_client.get('elapsed_ms')}"
    )
    return response


def speak_response(response: Dict[str, Any], tts_mode: str = "") -> bool:
    if VoiceTextPlayer is None or extract_voice_text is None:
        print("[voice] voice module unavailable, skip speaking")
        return False
    return VoiceTextPlayer(tts_mode).speak(extract_voice_text(response))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="2K1000LA SafeCloud /api/evaluate client")
    parser.add_argument("--base-url", default="", help="Manual SafeCloud base URL. Overrides discovery.")
    parser.add_argument(
        "--sensor-source",
        default="scenario",
        choices=["scenario", "mock", "2k0301"],
        help="Sensor input source: one scenario file, cycling mock scenarios, or MQTT 2K0301 bridge.",
    )
    parser.add_argument("--scenario-file", default=DEFAULT_SCENARIO_FILE)
    parser.add_argument("--output-file", default="")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--use-real-llm", action="store_true")
    parser.add_argument("--force-model", default="")
    parser.add_argument("--include-debug", action="store_true")
    parser.add_argument("--speak", action="store_true", help="Speak final_status.voice_text after evaluate.")
    parser.add_argument(
        "--speak-on-alert",
        action="store_true",
        help="Only speak when final_status.need_voice_alert is true or alarm_level is greater than zero.",
    )
    parser.add_argument(
        "--alert-cooldown-seconds",
        type=float,
        default=env_float("XYLT_ALERT_COOLDOWN_SECONDS", 30.0),
        help="Minimum interval before repeating the same voice alert.",
    )
    parser.add_argument("--tts-mode", default="", choices=["", "print", "none", "espeak", "spd-say", "audio", "baidu"])
    parser.add_argument("--cache-file", default=default_cache_file())
    parser.add_argument("--discovery-port", type=int, default=int(os.environ.get("SAFECLOUD_DISCOVERY_PORT", "8011")))
    parser.add_argument("--discovery-timeout", type=float, default=3.0)
    parser.add_argument("--no-discovery", action="store_true")
    parser.add_argument("--loop", action="store_true", help="Run as a simple resident polling process.")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--mqtt-host", default="", help="2K0301 MQTT broker host. Defaults to env or 127.0.0.1.")
    parser.add_argument("--mqtt-port", type=int, default=0, help="2K0301 MQTT broker port. Defaults to env or 1883.")
    parser.add_argument("--mqtt-qos", type=int, default=-1, choices=[-1, 0, 1, 2])
    parser.add_argument("--mqtt-sensor-topic", default="")
    parser.add_argument("--mqtt-heartbeat-topic", default="")
    parser.add_argument("--mqtt-ack-topic", default="")
    parser.add_argument("--mqtt-error-topic", default="")
    parser.add_argument("--mqtt-command-topic", default="")
    parser.add_argument("--mqtt-first-timeout", type=float, default=0.0)
    parser.add_argument("--mqtt-stale-after", type=float, default=0.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        sensor_source = create_sensor_source(args.sensor_source, args.scenario_file, build_mqtt_config(args))
    except SensorSourceError as exc:
        raise SystemExit(f"数据源初始化失败：{exc}") from exc

    base_url, source = resolve_base_url(
        args.base_url,
        args.cache_file,
        args.discovery_port,
        args.discovery_timeout,
        args.no_discovery,
    )
    print(f"safecloud_base_url={base_url} source={source}")
    client = SafeCloudClient(base_url, args.timeout)
    alert_manager = VoiceAlertManager(args.speak_on_alert, args.tts_mode, args.alert_cooldown_seconds)

    while True:
        try:
            payload = apply_runtime_options(
                sensor_source.next_payload(),
                args.use_real_llm,
                args.force_model,
                args.include_debug,
            )
        except SensorSourceError as exc:
            raise SystemExit(f"数据源读取失败：{exc}") from exc
        run_once(args, client, payload, alert_manager)
        if not args.loop:
            break
        time.sleep(args.interval)


def build_mqtt_config(args: argparse.Namespace) -> Optional[Mqtt2K0301Config]:
    if args.sensor_source != "2k0301":
        return None
    config = Mqtt2K0301Config.from_env()
    if args.mqtt_host:
        config.host = args.mqtt_host
    if args.mqtt_port > 0:
        config.port = args.mqtt_port
    if args.mqtt_qos >= 0:
        config.qos = args.mqtt_qos
    if args.mqtt_sensor_topic:
        config.sensor_topic = args.mqtt_sensor_topic
    if args.mqtt_heartbeat_topic:
        config.heartbeat_topic = args.mqtt_heartbeat_topic
    if args.mqtt_ack_topic:
        config.ack_topic = args.mqtt_ack_topic
    if args.mqtt_error_topic:
        config.error_topic = args.mqtt_error_topic
    if args.mqtt_command_topic:
        config.command_topic = args.mqtt_command_topic
    if args.mqtt_first_timeout > 0:
        config.first_message_timeout = args.mqtt_first_timeout
    if args.mqtt_stale_after > 0:
        config.stale_after_seconds = args.mqtt_stale_after
    return config


if __name__ == "__main__":
    main()
