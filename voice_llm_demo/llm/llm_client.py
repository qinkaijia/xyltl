from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import config
from .mock_llm import MockLLM


class LLMClient:
    _PROVIDERS = {
        "deepseek": ("DEEPSEEK_API_KEY", "DEEPSEEK_API_URL", "DEEPSEEK_MODEL", "https://api.deepseek.com/chat/completions", "deepseek-chat"),
        "kimi": ("KIMI_API_KEY", "KIMI_API_URL", "KIMI_MODEL", "https://api.moonshot.cn/v1/chat/completions", "kimi-k2"),
        "zhipu": ("ZHIPU_API_KEY", "ZHIPU_API_URL", "ZHIPU_MODEL", "https://open.bigmodel.cn/api/paas/v4/chat/completions", "glm-4-flash"),
        "doubao": ("DOUBAO_API_KEY", "DOUBAO_API_URL", "DOUBAO_MODEL", "https://ark.cn-beijing.volces.com/api/v3/chat/completions", "doubao-seed-1-6-flash"),
        "qwen": ("QWEN_API_KEY", "QWEN_API_URL", "QWEN_MODEL", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions", "qwen-plus"),
    }

    def __init__(
        self,
        *,
        use_real: bool | None = None,
        provider: str | None = None,
        context_status_file: str | None = None,
        max_history_turns: int | None = None,
        max_reply_chars: int | None = None,
        max_question_chars: int | None = None,
        max_context_chars: int | None = None,
    ) -> None:
        self.mock_llm = MockLLM()
        self.use_real = config.USE_REAL_LLM if use_real is None else use_real
        self.provider = (provider or config.VOICE_LLM_PROVIDER or "mock").lower()
        self.context_status_file = context_status_file or config.VOICE_CONTEXT_STATUS_FILE
        self.max_history_turns = max_history_turns or config.VOICE_MAX_HISTORY_TURNS
        self.max_reply_chars = max_reply_chars or config.VOICE_MAX_REPLY_CHARS
        self.max_question_chars = max_question_chars or config.VOICE_MAX_QUESTION_CHARS
        self.max_context_chars = max_context_chars or config.VOICE_MAX_CONTEXT_CHARS
        self.history: list[dict[str, str]] = []

    def analyze(self, user_text: str, device_context: dict) -> dict:
        text = self._clip_text(user_text or "", self.max_question_chars)
        local_result = self.mock_llm.analyze(text, device_context)

        # Hardware and safety-related commands remain deterministic. The model
        # may explain, but it must not be the authority that executes actuators.
        if local_result.get("need_execute") or local_result.get("intent") not in {"UNSUPPORTED", "QUERY_STATUS", "EXPLAIN_ALARM"}:
            self._remember(text, str(local_result.get("reply", "")))
            return local_result

        if not self.use_real or self.provider == "mock":
            self._remember(text, str(local_result.get("reply", "")))
            return local_result

        try:
            reply = self._answer_with_llm(text, device_context)
        except Exception as exc:  # noqa: BLE001 - keep voice loop alive.
            message = f"真实大模型调用失败：{exc}。请检查 API Key、模型名和网络。"
            print(message)
            return self._llm_unavailable_result(text, message)

        reply = self._clip_text(str(reply), self.max_reply_chars)
        self._remember(text, reply)
        return {
            "type": "qa",
            "intent": "GENERAL_QA",
            "need_execute": False,
            "need_confirm": False,
            "params": {},
            "reply": reply,
            "provider": self.provider,
        }

    def _llm_unavailable_result(self, user_text: str, message: str) -> dict:
        reply = self._clip_text(message, self.max_reply_chars)
        self._remember(user_text, reply)
        return {
            "type": "error",
            "intent": "LLM_UNAVAILABLE",
            "need_execute": False,
            "need_confirm": False,
            "params": {},
            "reply": reply,
            "provider": self.provider,
        }

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
            message = f"真实大模型 HTTP 调用失败：{exc}。请检查 API Key、模型名和网络。"
            print(message)
            return self._llm_unavailable_result(user_text, message)

    def _answer_with_llm(self, user_text: str, device_context: dict) -> str:
        messages = self._build_messages(user_text, device_context)
        return self._call_chat_completion(messages)

    def _build_messages(self, user_text: str, device_context: dict) -> list[dict[str, str]]:
        context = {
            "device_context": device_context,
            "latest_system_status": self._load_status_context(),
        }
        context_text = self._clip_text(json.dumps(context, ensure_ascii=False), self.max_context_chars)
        system_prompt = (
            "你是密闭空间智能安全监护仪的中文语音助手。"
            "只根据给定设备状态和已有对话回答，不编造传感器读数。"
            "涉及报警、排风、蜂鸣器、灯光等执行动作时，只说明需要走本地安全命令，"
            "不要声称自己已经执行。回答要适合语音播报，简洁、明确、专业。"
            f"回复不超过 {self.max_reply_chars} 个中文字符。"
        )
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for item in self.history[-self.max_history_turns :]:
            messages.append({"role": "user", "content": item.get("user", "")})
            messages.append({"role": "assistant", "content": item.get("assistant", "")})
        messages.append(
            {
                "role": "user",
                "content": f"设备上下文 JSON：{context_text}\n用户问题：{user_text}",
            }
        )
        return messages

    def _call_chat_completion(self, messages: list[dict[str, str]]) -> str:
        provider = self.provider
        if provider not in self._PROVIDERS:
            raise RuntimeError(f"未知 VOICE_LLM_PROVIDER: {provider}")
        key_env, url_env, model_env, default_url, default_model = self._PROVIDERS[provider]
        api_key = os.environ.get("VOICE_LLM_API_KEY") or os.environ.get(key_env)
        if not api_key:
            raise RuntimeError(f"缺少大模型密钥环境变量：{key_env}")
        api_url = os.environ.get("VOICE_LLM_API_URL") or os.environ.get(url_env) or default_url
        model = os.environ.get("VOICE_LLM_MODEL") or os.environ.get(model_env) or default_model
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max(128, min(512, self.max_reply_chars * 2)),
        }
        request = urllib.request.Request(
            api_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=25) as response:
            body = json.loads(response.read().decode("utf-8"))
        return self._extract_reply(body)

    @staticmethod
    def _extract_reply(body: dict) -> str:
        choices = body.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict) and message.get("content"):
                    return str(message["content"]).strip()
                if first.get("text"):
                    return str(first["text"]).strip()
        if body.get("output_text"):
            return str(body["output_text"]).strip()
        output = body.get("output")
        if isinstance(output, list):
            chunks: list[str] = []
            for item in output:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("text"):
                            chunks.append(str(part["text"]))
                elif isinstance(content, str):
                    chunks.append(content)
            if chunks:
                return "".join(chunks).strip()
        raise RuntimeError("大模型响应中未找到可播报文本")

    def _load_status_context(self) -> dict:
        if not self.context_status_file or not os.path.exists(self.context_status_file):
            return {}
        try:
            with open(self.context_status_file, "r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError):
            return {}
        status = payload.get("final_status", payload)
        debug = payload.get("debug", {}) if isinstance(payload, dict) else {}
        return {
            "device_id": status.get("device_id"),
            "alarm_level": status.get("alarm_level"),
            "status_text": status.get("status_text"),
            "reason": status.get("reason"),
            "suggestion": status.get("suggestion"),
            "cloud_connected": status.get("cloud_connected"),
            "analysis_mode": status.get("analysis_mode"),
            "sensor_metrics": status.get("sensor_metrics"),
            "tvoc": status.get("tvoc"),
            "eco2": status.get("eco2"),
            "mq3_value": status.get("mq3_value"),
            "flame_detected": status.get("flame_detected"),
            "risk_score": status.get("risk_score"),
            "client": debug.get("client", {}),
        }

    def _local_qa_reply(self, user_text: str, device_context: dict, local_result: dict) -> str:
        if any(keyword in user_text for keyword in ["介绍", "系统", "项目", "作用", "功能"]):
            return (
                "这是基于龙芯 2K0301 和 2K1000LA 的密闭空间智能安全监护系统，"
                "负责环境采集、本地安全联动、Qt 显示、语音交互和云端多模型分析。"
            )
        if any(keyword in user_text for keyword in ["上下文", "限制", "隐私"]):
            return (
                f"当前语音问答只保留最近 {self.max_history_turns} 轮对话，"
                f"问题限制 {self.max_question_chars} 字，回复限制 {self.max_reply_chars} 字，"
                "并只向模型提供必要设备状态。"
            )
        if any(keyword in user_text for keyword in ["状态", "数据", "环境"]):
            return self.mock_llm.analyze("当前状态怎么样", device_context).get("reply", "")
        return local_result.get("reply") or "大模型暂不可用，我已保留本地安全控制和基础问答功能。"

    def _remember(self, user_text: str, reply: str) -> None:
        self.history.append({"user": user_text, "assistant": reply})
        self.history = self.history[-self.max_history_turns :]

    @staticmethod
    def _clip_text(text: str, limit: int) -> str:
        clean = " ".join(str(text).split())
        if limit <= 0 or len(clean) <= limit:
            return clean
        return clean[: max(0, limit - 1)] + "…"
