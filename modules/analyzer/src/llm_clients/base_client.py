from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List


_ENV_LOADED = False
_TRUE_VALUES = {"1", "true", "yes", "on"}


def load_local_env() -> None:
    """Load modules/analyzer/.env without requiring python-dotenv."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def real_llm_enabled() -> bool:
    load_local_env()
    return os.environ.get("ANALYZER_USE_REAL_LLM", "false").lower() in _TRUE_VALUES


class BaseLLMClient:
    def __init__(
        self,
        model_name: str,
        api_key_env: str = "",
        base_url_env: str = "",
        model_env: str = "",
    ) -> None:
        load_local_env()
        self.model_name = model_name
        self.api_key_env = api_key_env
        self.base_url_env = base_url_env
        self.model_env = model_env
        self.api_key = os.environ.get(api_key_env, "") if api_key_env else ""
        self.base_url = os.environ.get(base_url_env, "") if base_url_env else ""
        self.remote_model_name = os.environ.get(model_env, model_name) if model_env else model_name
        self.timeout = float(os.environ.get("ANALYZER_LLM_TIMEOUT", "30"))
        self.temperature = float(os.environ.get(f"{model_name.upper()}_TEMPERATURE", "0.2"))

    def analyze(self, input_data: Dict, role: str) -> Dict:
        if not self.is_available():
            raise RuntimeError(self.unavailable_reason())

        messages = self._build_messages(input_data, role)
        response = self._chat_completion(messages)
        content = self._extract_chat_content(response)
        parsed = self._parse_json_content(content)
        return self._normalize_result(parsed, input_data, role)

    def error_result(self, input_data: Dict, role: str, error: str) -> Dict:
        rule_result = input_data.get("rule_result", {}) or {}
        rule_level = self._safe_int(rule_result.get("alarm_level", 0), 0)
        rule_hits = rule_result.get("rule_hits", [])
        if isinstance(rule_hits, str):
            rule_hits = [rule_hits]
        if not isinstance(rule_hits, list):
            rule_hits = []
        suggestion = str(rule_result.get("suggestion") or "请检查大模型 API 配置与网络，关键动作按本地规则执行。")
        return {
            "model_name": self.model_name,
            "role": role,
            "alarm_level": rule_level,
            "risk_summary": "真实大模型未完成有效评估，当前仅保留规则引擎兜底结果。",
            "possible_causes": [str(item) for item in rule_hits if str(item).strip()] or ["真实大模型不可用"],
            "suggestion": suggestion,
            "confidence": 0.0,
            "error": error,
        }

    def is_available(self) -> bool:
        return (
            real_llm_enabled()
            and bool(self.api_key)
            and bool(self.base_url)
            and bool(self.remote_model_name)
        )

    def unavailable_reason(self) -> str:
        missing = []
        if not real_llm_enabled():
            missing.append("ANALYZER_USE_REAL_LLM 未开启")
        if self.api_key_env and not self.api_key:
            missing.append(f"缺少环境变量 {self.api_key_env}")
        if self.base_url_env and not self.base_url:
            missing.append(f"缺少环境变量 {self.base_url_env}")
        if self.model_env and not self.remote_model_name:
            missing.append(f"缺少环境变量 {self.model_env}")
        return "；".join(missing) or "客户端不可用"

    def _chat_completion(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        payload = {
            "model": self.remote_model_name,
            "messages": messages,
            "temperature": self.temperature,
            "stream": False,
        }
        return self._post_json(payload)

    def _post_json(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.base_url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                response_body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{self.model_name} HTTP {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"{self.model_name} 网络请求失败: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RuntimeError(f"{self.model_name} 请求超时") from exc

        try:
            return json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{self.model_name} 返回非 JSON 响应: {response_body[:300]}") from exc

    def _build_messages(self, input_data: Dict, role: str) -> List[Dict[str, str]]:
        rule_level = int(input_data.get("rule_result", {}).get("alarm_level", 0))
        schema = {
            "model_name": self.model_name,
            "role": role,
            "alarm_level": rule_level,
            "risk_summary": "一句话说明当前风险",
            "possible_causes": ["原因1", "原因2"],
            "suggestion": "面向现场人员的处置建议",
            "confidence": 0.85,
        }
        system_prompt = (
            "你是工业密闭空间智能安全监护仪的云端分析模型。"
            "本地 RuleEngine 的 alarm_level 是安全下限，你不能把它降级。"
            "只能输出一个 JSON 对象，不要输出 Markdown、代码块或额外解释。"
        )
        user_prompt = (
            f"你的分析角色: {role}\n"
            f"输出 JSON schema 示例: {json.dumps(schema, ensure_ascii=False)}\n"
            "请基于以下实时数据分析风险，alarm_level 只能是 0、1、2，"
            "confidence 为 0 到 1 的小数。\n"
            f"{json.dumps(input_data, ensure_ascii=False, indent=2)}"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _extract_chat_content(self, response: Dict[str, Any]) -> str:
        choices = response.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message", {})
            content = message.get("content", "")
            if isinstance(content, str) and content.strip():
                return content

        output_text = response.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        raise RuntimeError(f"{self.model_name} 响应中没有可解析文本")

    def _parse_json_content(self, content: str) -> Dict[str, Any]:
        text = content.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()

        if not text.startswith("{"):
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                text = text[start : end + 1]

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{self.model_name} 未返回合法 JSON: {content[:300]}") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError(f"{self.model_name} JSON 根节点不是对象")
        return parsed

    def _normalize_result(self, parsed: Dict[str, Any], input_data: Dict, role: str) -> Dict:
        rule_level = int(input_data.get("rule_result", {}).get("alarm_level", 0))
        alarm_level = self._safe_int(parsed.get("alarm_level", rule_level), rule_level)
        alarm_level = max(rule_level, max(0, min(2, alarm_level)))

        causes = parsed.get("possible_causes", [])
        if isinstance(causes, str):
            causes = [causes]
        if not isinstance(causes, list):
            causes = []
        causes = [str(item) for item in causes if str(item).strip()]
        if not causes:
            causes = list(input_data.get("rule_result", {}).get("rule_hits", [])) or ["未发现明确异常原因"]

        confidence = self._safe_float(parsed.get("confidence", 0.7), 0.7)
        if confidence > 1 and confidence <= 100:
            confidence = confidence / 100
        confidence = max(0.0, min(1.0, confidence))

        return {
            "model_name": str(parsed.get("model_name") or self.model_name),
            "role": str(parsed.get("role") or role),
            "alarm_level": alarm_level,
            "risk_summary": str(parsed.get("risk_summary") or input_data.get("rule_result", {}).get("reason", "")),
            "possible_causes": causes,
            "suggestion": str(parsed.get("suggestion") or input_data.get("rule_result", {}).get("suggestion", "")),
            "confidence": confidence,
        }

    @staticmethod
    def _safe_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
