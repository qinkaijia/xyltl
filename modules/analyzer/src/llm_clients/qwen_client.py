from __future__ import annotations

from typing import Dict

from llm_clients.base_client import BaseLLMClient
from llm_clients.mock_client import MockLLMClient


class QwenClient(BaseLLMClient):
    def __init__(self) -> None:
        super().__init__("qwen", "QWEN_API_KEY", "QWEN_API_URL", "QWEN_MODEL")
        self.fallback = MockLLMClient("qwen_mock")

    def analyze(self, input_data: Dict, role: str) -> Dict:
        return self.fallback.analyze(input_data, role)
