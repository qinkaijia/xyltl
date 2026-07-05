from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from voice.voice_text_player import VoiceTextPlayer, extract_voice_text
except ImportError:  # keep the board-side client usable when voice module is absent.
    VoiceTextPlayer = None  # type: ignore
    extract_voice_text = None  # type: ignore


DEFAULT_BASE_URL = "http://127.0.0.1:8000"


class SafeCloudClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

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


def evaluate_with_fallback(
    client: SafeCloudClient,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    started = time.time()
    try:
        response = client.evaluate(payload)
        response.setdefault("debug", {})
        response["debug"]["client"] = {
            "ok": True,
            "elapsed_ms": int((time.time() - started) * 1000),
            "base_url": client.base_url,
        }
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

    return {
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


def local_rule_evaluate(metrics: Dict[str, Any], state: Dict[str, Any]) -> tuple[int, str, list[str]]:
    level = 0
    reasons = []
    hits = []

    if state.get("sensor_online", True) is False:
        level = 2
        hits.append("SENSOR_OFFLINE")
        reasons.append("传感器离线，无法确认现场状态")

    checks = [
        ("temperature", "温度", 60.0, 75.0),
        ("gas", "气体浓度", 0.3, 0.6),
        ("vibration", "振动", 1.5, 2.5),
        ("current", "电流", 3.0, 5.0),
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="2K1000LA SafeCloud /api/evaluate client")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--scenario-file", required=True)
    parser.add_argument("--output-file", default="")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--use-real-llm", action="store_true")
    parser.add_argument("--force-model", default="")
    parser.add_argument("--include-debug", action="store_true")
    parser.add_argument("--speak", action="store_true", help="Speak final_status.voice_text after evaluate.")
    parser.add_argument("--tts-mode", default="", choices=["", "print", "none", "espeak", "spd-say"])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = load_scenario(args.scenario_file)
    payload["use_real_llm"] = bool(args.use_real_llm)
    payload["force_model"] = args.force_model
    payload["include_debug"] = bool(args.include_debug)

    response = evaluate_with_fallback(SafeCloudClient(args.base_url, args.timeout), payload)
    write_json(args.output_file, response)

    if args.speak:
        if VoiceTextPlayer is None or extract_voice_text is None:
            print("[voice] voice module unavailable, skip speaking")
        else:
            VoiceTextPlayer(args.tts_mode).speak(extract_voice_text(response))

    final_status = response["final_status"]
    print(
        "evaluate_result "
        f"level={final_status['alarm_level']} "
        f"mode={final_status['analysis_mode']} "
        f"voice_alert={final_status['need_voice_alert']}"
    )


if __name__ == "__main__":
    main()
