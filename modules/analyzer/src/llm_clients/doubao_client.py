from __future__ import annotations

from typing import Dict

from llm_clients.base_client import BaseLLMClient
from llm_clients.mock_client import MockLLMClient


class DoubaoClient(BaseLLMClient):
    def __init__(self) -> None:
        super().__init__("doubao", "DOUBAO_API_KEY", "DOUBAO_API_URL", "DOUBAO_MODEL")
        self.api_type = "responses"
        self.fallback = MockLLMClient("doubao_mock")

    def analyze(self, input_data: Dict, role: str) -> Dict:
        return self.fallback.analyze(input_data, role)
