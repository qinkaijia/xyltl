from __future__ import annotations

import base64
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from app.schemas.vision import VisionEvaluateRequest, VisionMode


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_VISION_API_URL = "https://ark.cn-beijing.volces.com/api/v3/responses"
DEFAULT_VISION_MODEL = "doubao-seed-2-0-lite-260428"
MAX_IMAGE_BYTES = 2_500_000

_LATEST_EVALUATION: dict[str, Any] | None = None
_LATEST_IMAGE_BYTES: bytes | None = None
_LATEST_IMAGE_MIME = "image/jpeg"
_VISION_MODE: VisionMode = "cloud"


def evaluate(payload: VisionEvaluateRequest) -> dict[str, Any]:
    global _LATEST_EVALUATION, _LATEST_IMAGE_BYTES, _LATEST_IMAGE_MIME

    started = time.time()
    mode = payload.mode or _VISION_MODE
    image_base64 = _strip_data_url(payload.image_base64)
    debug: dict[str, Any] = {
        "mode": mode,
        "backend": "doubao_vision" if mode == "cloud" else mode,
        "request_image_mime": payload.image_mime,
    }

    try:
        image_bytes = base64.b64decode(image_base64, validate=True)
    except (ValueError, TypeError) as exc:
        status = _error_status(payload, mode, "image_decode", f"图像 base64 解析失败: {exc}", started)
        return _store(payload, status, None, payload.image_mime, debug if payload.include_debug else None)

    if len(image_bytes) > MAX_IMAGE_BYTES:
        status = _error_status(
            payload,
            mode,
            "image_too_large",
            f"图像过大: {len(image_bytes)} bytes, 请降低分辨率或 JPEG 质量",
            started,
        )
        return _store(payload, status, image_bytes, payload.image_mime, debug if payload.include_debug else None)

    if mode == "off":
        status = _base_status(payload, mode, "off", started)
        status.update(
            {
                "camera_online": True,
                "ppe_status": "unknown",
                "summary": "视觉模块已关闭，未进行图像分析。",
                "image_available": True,
            }
        )
        return _store(payload, status, image_bytes, payload.image_mime, debug if payload.include_debug else None)

    if mode == "local":
        status = _error_status(
            payload,
            mode,
            "local_not_on_cloud",
            "local YOLO 模式在 2K1000LA 板端运行，SafeCloud 只接收云端视觉评估请求。",
            started,
        )
        return _store(payload, status, image_bytes, payload.image_mime, debug if payload.include_debug else None)

    client = DoubaoVisionClient()
    if not client.is_available:
        status = _error_status(payload, mode, "missing_config", client.missing_config_message, started)
        return _store(payload, status, image_bytes, payload.image_mime, debug if payload.include_debug else None)

    try:
        raw, client_debug = client.evaluate(image_base64, payload.image_mime, payload.sensor_snapshot)
        debug.update(client_debug)
        status = _normalize_model_result(raw, payload, started, backend="doubao_vision")
    except Exception as exc:  # noqa: BLE001 - API errors must not stop the safety service.
        status = _error_status(payload, mode, "doubao_call_failed", f"豆包视觉调用失败: {exc}", started)
        debug["error"] = str(exc)

    return _store(payload, status, image_bytes, payload.image_mime, debug if payload.include_debug else None)


def latest_evaluation() -> dict[str, Any] | None:
    return _LATEST_EVALUATION


def latest_image() -> tuple[bytes, str] | None:
    if _LATEST_IMAGE_BYTES is None:
        return None
    return _LATEST_IMAGE_BYTES, _LATEST_IMAGE_MIME


def get_mode() -> VisionMode:
    return _VISION_MODE


def set_mode(mode: VisionMode) -> VisionMode:
    global _VISION_MODE
    _VISION_MODE = mode
    return _VISION_MODE


class DoubaoVisionClient:
    def __init__(self) -> None:
        _load_env_files()
        self.api_key = (os.environ.get("DOUBAO_VISION_API_KEY") or os.environ.get("DOUBAO_API_KEY", "")).strip()
        self.api_url = (
            os.environ.get("DOUBAO_VISION_API_URL")
            or os.environ.get("DOUBAO_API_URL")
            or DEFAULT_VISION_API_URL
        ).strip()
        self.model = os.environ.get("DOUBAO_VISION_MODEL", DEFAULT_VISION_MODEL).strip()
        self.api_type = os.environ.get("DOUBAO_VISION_API_TYPE", "responses").strip().lower()
        self.timeout = float(os.environ.get("DOUBAO_VISION_TIMEOUT", "45"))

    @property
    def is_available(self) -> bool:
        return bool(self.api_key and self.api_url and self.model)

    @property
    def missing_config_message(self) -> str:
        missing = []
        if not self.api_key:
            missing.append("DOUBAO_VISION_API_KEY/DOUBAO_API_KEY")
        if not self.api_url:
            missing.append("DOUBAO_VISION_API_URL")
        if not self.model:
            missing.append("DOUBAO_VISION_MODEL")
        return "缺少豆包视觉配置: " + ", ".join(missing)

    def evaluate(self, image_base64: str, image_mime: str, sensor_snapshot: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        request_body = self._build_request_body(image_base64, image_mime, sensor_snapshot)
        started = time.time()
        response = requests.post(
            self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=request_body,
            timeout=self.timeout,
        )
        elapsed_ms = int((time.time() - started) * 1000)
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:600]}")
        payload = response.json()
        content = _extract_content(payload)
        return _parse_json_content(content), {
            "model": self.model,
            "api_url": self.api_url,
            "api_type": self.api_type,
            "elapsed_ms": elapsed_ms,
            "raw_content": content,
        }

    def _build_request_body(self, image_base64: str, image_mime: str, sensor_snapshot: dict[str, Any]) -> dict[str, Any]:
        if self.api_type in {"chat", "chat_completions", "chat-completions"}:
            return self._build_chat_completions_body(image_base64, image_mime, sensor_snapshot)
        return self._build_responses_body(image_base64, image_mime, sensor_snapshot)

    def _build_responses_body(self, image_base64: str, image_mime: str, sensor_snapshot: dict[str, Any]) -> dict[str, Any]:
        return {
            "model": self.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_image",
                            "image_url": f"data:{image_mime};base64,{image_base64}",
                        },
                        {
                            "type": "input_text",
                            "text": (
                                "你是工业密闭空间安全监护仪的视觉安全评估模块。"
                                "请只输出 JSON，不要输出 Markdown。"
                                + _vision_prompt(sensor_snapshot)
                            ),
                        },
                    ],
                }
            ],
        }

    def _build_chat_completions_body(self, image_base64: str, image_mime: str, sensor_snapshot: dict[str, Any]) -> dict[str, Any]:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是工业密闭空间安全监护仪的视觉安全评估模块。"
                    "请只输出 JSON，不要输出 Markdown。"
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": _vision_prompt(sensor_snapshot),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{image_mime};base64,{image_base64}",
                        },
                    },
                ],
            },
        ]
        return {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 700,
        }


def _vision_prompt(sensor_snapshot: dict[str, Any]) -> str:
    return (
        "请判断图像中的人员安全状态，重点识别：是否有人、是否佩戴安全帽、是否佩戴口罩、"
        "是否穿反光背心、是否存在明显火焰或危险姿态。"
        "必须返回严格 JSON，字段如下："
        "{"
        "\"person_detected\": true/false,"
        "\"helmet_detected\": true/false/null,"
        "\"mask_detected\": true/false/null,"
        "\"reflective_vest_detected\": true/false/null,"
        "\"fire_detected\": true/false,"
        "\"ppe_status\": \"pass|fail|unknown\","
        "\"missing_ppe\": [\"安全帽\",\"口罩\",\"反光背心\"],"
        "\"summary\": \"不超过80字的中文结论\","
        "\"confidence\": 0.0到1.0,"
        "\"detections\": [{\"label\":\"person|helmet|mask|vest|fire|other\",\"confidence\":0.0到1.0}]"
        "}。"
        f"当前传感器快照可作为辅助信息: {json.dumps(sensor_snapshot, ensure_ascii=False)}"
    )


def _normalize_model_result(raw: dict[str, Any], payload: VisionEvaluateRequest, started: float, backend: str) -> dict[str, Any]:
    status = _base_status(payload, payload.mode, backend, started)
    person = _optional_bool(raw.get("person_detected"))
    helmet = _optional_bool(raw.get("helmet_detected"))
    mask = _optional_bool(raw.get("mask_detected"))
    vest = _optional_bool(raw.get("reflective_vest_detected"))
    fire = bool(_optional_bool(raw.get("fire_detected")) or False)
    missing = _normalize_missing(raw.get("missing_ppe"))

    if person:
        if helmet is False and "安全帽" not in missing:
            missing.append("安全帽")
        if mask is False and "口罩" not in missing:
            missing.append("口罩")
        if vest is False and "反光背心" not in missing:
            missing.append("反光背心")

    ppe_status = str(raw.get("ppe_status") or "").strip().lower()
    if ppe_status not in {"pass", "fail", "unknown"}:
        if person is False:
            ppe_status = "unknown"
        else:
            ppe_status = "fail" if missing or fire else "pass"

    status.update(
        {
            "camera_online": True,
            "person_detected": bool(person) if person is not None else False,
            "helmet_detected": helmet,
            "mask_detected": mask,
            "reflective_vest_detected": vest,
            "fire_detected": fire,
            "ppe_status": ppe_status,
            "missing_ppe": missing,
            "summary": str(raw.get("summary") or _summary_from_status(person, ppe_status, missing, fire)),
            "confidence": _number(raw.get("confidence"), 0.0),
            "detections": raw.get("detections") if isinstance(raw.get("detections"), list) else [],
            "image_available": True,
        }
    )
    return status


def _store(
    payload: VisionEvaluateRequest,
    status: dict[str, Any],
    image_bytes: bytes | None,
    image_mime: str,
    debug: dict[str, Any] | None,
) -> dict[str, Any]:
    global _LATEST_EVALUATION, _LATEST_IMAGE_BYTES, _LATEST_IMAGE_MIME
    if image_bytes is not None:
        _LATEST_IMAGE_BYTES = image_bytes
        _LATEST_IMAGE_MIME = image_mime or "image/jpeg"
    response = {"vision_status": status, "debug": debug}
    _LATEST_EVALUATION = {
        "request": payload.model_dump(mode="json", exclude={"image_base64"}),
        "response": response,
    }
    return response


def _base_status(payload: VisionEvaluateRequest, mode: VisionMode, backend: str, started: float) -> dict[str, Any]:
    return {
        "device_id": payload.device_id,
        "timestamp": payload.timestamp.isoformat(),
        "mode": mode,
        "trigger": payload.trigger,
        "request_id": payload.request_id,
        "backend": backend,
        "camera_online": False,
        "person_detected": False,
        "helmet_detected": None,
        "mask_detected": None,
        "reflective_vest_detected": None,
        "fire_detected": False,
        "ppe_status": "unknown",
        "missing_ppe": [],
        "summary": "",
        "confidence": 0.0,
        "detections": [],
        "latency_ms": int((time.time() - started) * 1000),
        "image_available": False,
        "error": "",
    }


def _error_status(payload: VisionEvaluateRequest, mode: VisionMode, backend: str, error: str, started: float) -> dict[str, Any]:
    status = _base_status(payload, mode, backend, started)
    status.update(
        {
            "camera_online": False if backend == "image_decode" else True,
            "ppe_status": "error",
            "summary": error,
            "error": error,
            "image_available": backend != "image_decode",
        }
    )
    return status


def _strip_data_url(value: str) -> str:
    text = value.strip()
    if text.startswith("data:"):
        return text.split(",", 1)[1] if "," in text else text
    return text


def _extract_content(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    output = payload.get("output")
    if isinstance(output, list):
        parts: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, str):
                parts.append(content)
                continue
            if not isinstance(content, list):
                continue
            for part in content:
                if isinstance(part, str):
                    parts.append(part)
                elif isinstance(part, dict):
                    text = part.get("text") or part.get("output_text")
                    if isinstance(text, str):
                        parts.append(text)
        content_text = "".join(parts).strip()
        if content_text:
            return content_text

    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError("豆包视觉响应缺少 output_text/output/choices")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        return "".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
    return str(content or "")


def _parse_json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if not text:
        raise RuntimeError("豆包视觉响应为空")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise RuntimeError("豆包视觉响应不是 JSON 对象")
    return data


def _load_env_files() -> None:
    for path in (REPO_ROOT / "modules" / "analyzer" / ".env", REPO_ROOT / "safecloud" / ".env"):
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return None


def _normalize_missing(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    alias = {
        "helmet": "安全帽",
        "hardhat": "安全帽",
        "mask": "口罩",
        "vest": "反光背心",
        "reflective_vest": "反光背心",
    }
    for item in value:
        text = str(item).strip()
        if not text:
            continue
        names.append(alias.get(text.lower(), text))
    return list(dict.fromkeys(names))


def _summary_from_status(person: bool | None, ppe_status: str, missing: list[str], fire: bool) -> str:
    if fire:
        return "画面中疑似存在火焰，请立即复核现场。"
    if person is False:
        return "画面中未检测到人员。"
    if ppe_status == "fail":
        return "人员防护不完整，缺少：" + "、".join(missing or ["必要防护装备"])
    if ppe_status == "pass":
        return "人员防护装备状态正常。"
    return "画面质量或目标不明确，建议人工复核。"


def _number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
