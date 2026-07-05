from __future__ import annotations

from typing import Dict

from llm_clients.base_client import BaseLLMClient
from llm_clients.mock_client import MockLLMClient


class KimiClient(BaseLLMClient):
    def __init__(self) -> None:
        super().__init__("kimi", "KIMI_API_KEY", "KIMI_API_URL", "KIMI_MODEL")
        self.fallback = MockLLMClient("kimi_mock")

    def analyze(self, input_data: Dict, role: str) -> Dict:
        return self.fallback.analyze(input_data, role)
