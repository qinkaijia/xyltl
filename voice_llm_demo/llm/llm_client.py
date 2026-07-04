from __future__ import annotations

import json
import urllib.error
import urllib.request

import config
from .mock_llm import MockLLM


class LLMClient:
    def __init__(self) -> None:
        self.mock_llm = MockLLM()

    def analyze(self, user_text: str, device_context: dict) -> dict:
        if not config.USE_REAL_LLM:
            return self.mock_llm.analyze(user_text, device_context)
        return self._analyze_http(user_text, device_context)

    def _analyze_http(self, user_text: str, device_context: dict) -> dict:
        payload = json.dumps(
            {"user_text": user_text, "device_context": device_context},
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            config.LLM_API_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            print(f"真实 LLM 暂不可用，改用 MockLLM。错误：{exc}")
            return self.mock_llm.analyze(user_text, device_context)

