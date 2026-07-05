from __future__ import annotations

import os
from typing import Dict


class BaseLLMClient:
    def __init__(
        self,
        model_name: str,
        api_key_env: str = "",
        base_url_env: str = "",
        model_env: str = "",
    ) -> None:
        self.model_name = model_name
        self.api_key_env = api_key_env
        self.base_url_env = base_url_env
        self.model_env = model_env
        self.api_key = os.environ.get(api_key_env, "") if api_key_env else ""
        self.base_url = os.environ.get(base_url_env, "") if base_url_env else ""
        self.remote_model_name = os.environ.get(model_env, model_name) if model_env else model_name

    def analyze(self, input_data: Dict, role: str) -> Dict:
        raise NotImplementedError

    def is_available(self) -> bool:
        return True
