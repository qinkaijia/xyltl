from __future__ import annotations

from typing import Dict

from llm_clients.base_client import BaseLLMClient, real_llm_enabled
from llm_clients.mock_client import MockLLMClient


class DoubaoClient(BaseLLMClient):
    def __init__(self) -> None:
        super().__init__("doubao", "DOUBAO_API_KEY", "DOUBAO_API_URL", "DOUBAO_MODEL")
        self.fallback = MockLLMClient("doubao_mock")

    def analyze(self, input_data: Dict, role: str) -> Dict:
        if not real_llm_enabled():
            return self.fallback.analyze(input_data, role)
        try:
            if self.is_available():
                return super().analyze(input_data, role)
            raise RuntimeError(self.unavailable_reason())
        except Exception as exc:
            result = self.fallback.analyze(input_data, role)
            result["error"] = f"豆包真实 API 调用失败，已回退 mock: {exc}"
            return result
