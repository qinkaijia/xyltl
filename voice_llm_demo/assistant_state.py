from __future__ import annotations

from datetime import datetime
import json
import os
from typing import Any


class AssistantStateWriter:
    """Write a small JSON status file consumed by Qt HMI."""

    def __init__(self, path: str, max_history: int = 6) -> None:
        self.path = path
        self.max_history = max(1, max_history)
        self.history: list[dict[str, str]] = []
        self.snapshot: dict[str, Any] = {
            "state": "idle",
            "state_text": "待唤醒",
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "last_user_text": "",
            "last_reply": "",
            "last_intent": "",
            "safety_message": "",
            "execute_message": "",
            "llm_provider": "",
            "history": [],
        }

    def update(
        self,
        state: str,
        *,
        state_text: str = "",
        last_user_text: str | None = None,
        last_reply: str | None = None,
        last_intent: str | None = None,
        safety_message: str | None = None,
        execute_message: str | None = None,
        llm_provider: str | None = None,
        error: str | None = None,
        commit_history: bool = False,
    ) -> None:
        self.snapshot["state"] = state
        self.snapshot["state_text"] = state_text or state
        self.snapshot["updated_at"] = datetime.now().isoformat(timespec="seconds")
        if last_user_text is not None:
            self.snapshot["last_user_text"] = last_user_text
        if last_reply is not None:
            self.snapshot["last_reply"] = last_reply
        if last_intent is not None:
            self.snapshot["last_intent"] = last_intent
        if safety_message is not None:
            self.snapshot["safety_message"] = safety_message
        if execute_message is not None:
            self.snapshot["execute_message"] = execute_message
        if llm_provider is not None:
            self.snapshot["llm_provider"] = llm_provider
        if error is not None:
            self.snapshot["error"] = error

        if commit_history:
            question = str(self.snapshot.get("last_user_text") or "").strip()
            reply = str(self.snapshot.get("last_reply") or "").strip()
            if question or reply:
                self.history.append(
                    {
                        "time": str(self.snapshot["updated_at"]),
                        "user": question,
                        "assistant": reply,
                    }
                )
                self.history = self.history[-self.max_history :]

        self.snapshot["history"] = list(self.history)
        self._write()

    def _write(self) -> None:
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp_path = f"{self.path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as file:
            json.dump(self.snapshot, file, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.path)
