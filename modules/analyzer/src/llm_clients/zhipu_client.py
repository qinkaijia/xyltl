from __future__ import annotations

from typing import Dict

from llm_clients.base_client import BaseLLMClient
from llm_clients.mock_client import MockLLMClient


class ZhipuClient(BaseLLMClient):
    def __init__(self) -> None:
        super().__init__("zhipu", "ZHIPU_API_KEY", "ZHIPU_API_URL", "ZHIPU_MODEL")
        self.fallback = MockLLMClient("zhipu_mock")

    def analyze(self, input_data: Dict, role: str) -> Dict:
        return self.fallback.analyze(input_data, role)
