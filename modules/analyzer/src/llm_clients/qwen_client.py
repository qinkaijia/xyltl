from __future__ import annotations

from typing import Dict

from llm_clients.base_client import BaseLLMClient, real_llm_enabled
from llm_clients.mock_client import MockLLMClient


class QwenClient(BaseLLMClient):
    def __init__(self) -> None:
        super().__init__("qwen", "QWEN_API_KEY", "QWEN_API_URL", "QWEN_MODEL")
        self.fallback = MockLLMClient("qwen_mock")

    def analyze(self, input_data: Dict, role: str) -> Dict:
        if not real_llm_enabled():
            return self.fallback.analyze(input_data, role)
        try:
            if self.is_available():
                return super().analyze(input_data, role)
            raise RuntimeError(self.unavailable_reason())
        except Exception as exc:
            return self.error_result(input_data, role, f"通义千问真实 API 调用失败: {exc}")
