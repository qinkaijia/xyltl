from __future__ import annotations

from datetime import datetime
import json
import os
import time
from pathlib import Path
from typing import Any

import config


VISION_QUERY_KEYWORDS = (
    "穿戴规范",
    "安全帽",
    "口罩",
    "反光背心",
    "摄像头",
    "现场画面",
    "安全隐患",
    "视觉巡检",
)

FORCE_CAPTURE_KEYWORDS = ("重新拍", "再看", "再拍", "重新看", "拍一下", "重新检查")


class VisionAssistantBridge:
    """Bridge voice questions to the 2K1000LA camera vision service."""

    def __init__(
        self,
        capture_request_file: str | None = None,
        vision_state_file: str | None = None,
        context_status_file: str | None = None,
        timeout_seconds: float | None = None,
        recent_seconds: float | None = None,
        enabled: bool | None = None,
    ) -> None:
        self.capture_request_file = Path(capture_request_file or config.VOICE_VISION_CAPTURE_REQUEST_FILE)
        self.vision_state_file = Path(vision_state_file or config.VOICE_VISION_STATE_FILE)
        self.context_status_file = Path(context_status_file or config.VOICE_CONTEXT_STATUS_FILE)
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else config.VOICE_VISION_TIMEOUT_SECONDS
        self.recent_seconds = recent_seconds if recent_seconds is not None else config.VOICE_VISION_RECENT_SECONDS
        self.enabled = config.VOICE_VISION_ENABLED if enabled is None else enabled

    def is_vision_query(self, text: str) -> bool:
        if not self.enabled:
            return False
        clean = str(text or "").strip()
        return any(keyword in clean for keyword in VISION_QUERY_KEYWORDS)

    def should_force_capture(self, text: str) -> bool:
        clean = str(text or "").strip()
        return any(keyword in clean for keyword in FORCE_CAPTURE_KEYWORDS)

    def answer(self, question: str) -> str:
        force = self.should_force_capture(question)
        state = None if force else self._read_recent_state()
        request_id = ""
        capture_note = ""

        if state is None:
            request_id = "voice-{}".format(int(time.time() * 1000))
            self._write_capture_request(request_id, question, force=force)
            state = self._wait_for_state(request_id)
            if state is None:
                state = self._read_latest_state()
                capture_note = "本次抓拍等待超时，以下为最近一次视觉结果。"
            else:
                capture_note = "已触发摄像头抓拍并完成云端视觉分析。"
        else:
            capture_note = "30 秒内已有视觉结果，本次复用最近一次分析。"

        sensor_snapshot = load_sensor_snapshot(self.context_status_file)
        if state is None:
            return "视觉服务暂时没有返回结果。" + format_sensor_summary(sensor_snapshot)

        status = extract_vision_status(state)
        return build_voice_reply(status, sensor_snapshot, capture_note, max_chars=config.VOICE_MAX_REPLY_CHARS)

    def _write_capture_request(self, request_id: str, question: str, force: bool) -> None:
        payload = {
            "type": "vision_capture_request",
            "request_id": request_id,
            "trigger": "voice",
            "question": question,
            "force": force,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.capture_request_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.capture_request_file.with_suffix(self.capture_request_file.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp_path, self.capture_request_file)

    def _wait_for_state(self, request_id: str) -> dict[str, Any] | None:
        deadline = time.monotonic() + max(1.0, self.timeout_seconds)
        while time.monotonic() < deadline:
            state = self._read_latest_state()
            status = extract_vision_status(state)
            if status.get("request_id") == request_id or status.get("reused_for_request_id") == request_id:
                return state
            time.sleep(0.5)
        return None

    def _read_recent_state(self) -> dict[str, Any] | None:
        state = self._read_latest_state()
        status = extract_vision_status(state)
        if not status:
            return None
        if state_age_seconds(status) <= self.recent_seconds:
            return state
        return None

    def _read_latest_state(self) -> dict[str, Any] | None:
        try:
            data = json.loads(self.vision_state_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError):
            return None


def extract_vision_status(state: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {}
    status = state.get("vision_status")
    return status if isinstance(status, dict) else {}


def state_age_seconds(status: dict[str, Any]) -> float:
    timestamp = str(status.get("timestamp") or "").strip()
    if not timestamp:
        return float("inf")
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return float("inf")
    if parsed.tzinfo is not None:
        now = datetime.now(parsed.tzinfo)
    else:
        now = datetime.now()
    return max(0.0, (now - parsed).total_seconds())


def load_sensor_snapshot(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}

    final_status = data.get("final_status")
    if isinstance(final_status, dict):
        metrics = final_status.get("sensor_metrics")
        if isinstance(metrics, dict):
            merged = dict(metrics)
            for key in ("status_text", "risk_level", "reason", "suggestion"):
                if key in final_status:
                    merged[key] = final_status[key]
            return merged
        return final_status

    payload = data.get("payload")
    if isinstance(payload, dict):
        return payload
    return data


def build_voice_reply(
    vision_status: dict[str, Any],
    sensor_snapshot: dict[str, Any],
    capture_note: str,
    max_chars: int = 180,
) -> str:
    ppe_summary = format_ppe_summary(vision_status)
    sensor_summary = format_sensor_summary(sensor_snapshot)
    conclusion = format_combined_conclusion(vision_status, sensor_snapshot)
    reply = "{}{}{}{}".format(capture_note, ppe_summary, sensor_summary, conclusion)
    return trim_reply(reply, max_chars)


def format_ppe_summary(status: dict[str, Any]) -> str:
    if not status:
        return " 视觉侧暂无有效结果。"
    error = str(status.get("error") or "").strip()
    if error:
        return " 视觉侧异常：{}。".format(error)

    person_text = "检测到人员" if status.get("person_detected") else "未明确检测到人员"
    ppe_status = str(status.get("ppe_status") or "unknown")
    ppe_text = {
        "pass": "穿戴基本规范",
        "fail": "穿戴不规范",
        "unknown": "穿戴状态无法确认",
        "error": "视觉识别异常",
    }.get(ppe_status, "穿戴状态无法确认")
    missing = status.get("missing_ppe") if isinstance(status.get("missing_ppe"), list) else []
    missing_text = "，缺少{}".format("、".join(str(item) for item in missing)) if missing else ""
    summary = str(status.get("summary") or "").strip()
    if summary and len(summary) <= 36:
        return " 视觉侧：{}，{}{}；{}。".format(person_text, ppe_text, missing_text, summary)
    return " 视觉侧：{}，{}{}。".format(person_text, ppe_text, missing_text)


def format_sensor_summary(sensor: dict[str, Any]) -> str:
    if not sensor:
        return " 301 环境数据暂未收到。"
    fields = [
        ("温度", sensor.get("temperature"), "℃"),
        ("湿度", sensor.get("humidity"), "%RH"),
        ("TVOC", sensor.get("tvoc"), "ppb"),
        ("eCO2", sensor.get("eco2"), "ppm"),
        ("MQ-3", sensor.get("mq3_value"), "mg/L"),
        ("风险值", sensor.get("risk_score"), ""),
    ]
    parts = []
    for name, value, unit in fields:
        if value is None:
            continue
        parts.append("{}{}{}".format(name, value, unit))
    flame = sensor.get("flame_detected")
    if flame is not None:
        parts.append("火焰{}".format("有" if bool(flame) else "无"))
    if not parts:
        return " 301 环境数据字段不完整。"
    return " 301 环境侧：" + "，".join(parts) + "。"


def format_combined_conclusion(vision_status: dict[str, Any], sensor: dict[str, Any]) -> str:
    risks: list[str] = []
    if vision_status.get("ppe_status") == "fail":
        risks.append("人员防护不完整")
    if vision_status.get("fire_detected"):
        risks.append("画面疑似火焰")
    if bool(sensor.get("flame_detected")):
        risks.append("火焰传感器报警")
    risk_score = number_or_none(sensor.get("risk_score"))
    if risk_score is not None and risk_score >= 60:
        risks.append("综合风险值偏高")
    tvoc = number_or_none(sensor.get("tvoc"))
    if tvoc is not None and tvoc >= 1000:
        risks.append("TVOC 偏高")
    eco2 = number_or_none(sensor.get("eco2"))
    if eco2 is not None and eco2 >= 1500:
        risks.append("eCO2 偏高")
    mq3 = number_or_none(sensor.get("mq3_value"))
    if mq3 is not None and mq3 >= 0.5:
        risks.append("MQ-3 酒精/可燃气体指标偏高")

    if risks:
        shown = risks[:3]
        suffix = "等" if len(risks) > len(shown) else ""
        return " 综合判断：存在安全隐患，重点关注{}{}。".format("、".join(shown), suffix)
    return " 综合判断：暂未发现明显安全隐患。"


def number_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def trim_reply(text: str, max_chars: int) -> str:
    text = " ".join(str(text or "").split())
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    limit = max(1, max_chars - 1)
    punctuation_positions = [text.rfind(mark, 0, limit) for mark in ("。", "；", "，")]
    cut = max(punctuation_positions)
    if cut > limit * 0.65:
        return text[: cut + 1]
    return text[:limit].rstrip("，。；、 ") + "。"
