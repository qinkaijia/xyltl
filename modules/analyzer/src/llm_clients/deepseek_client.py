from __future__ import annotations

from typing import Dict

from llm_clients.base_client import BaseLLMClient
from llm_clients.mock_client import MockLLMClient


class DeepSeekClient(BaseLLMClient):
    def __init__(self) -> None:
        super().__init__("deepseek", "DEEPSEEK_API_KEY", "DEEPSEEK_API_URL", "DEEPSEEK_MODEL")
        self.fallback = MockLLMClient("deepseek_mock")

    def analyze(self, input_data: Dict, role: str) -> Dict:
        return self.fallback.analyze(input_data, role)
