from __future__ import annotations

import json
import urllib.error
import urllib.request

import config


class ASRClient:
    def transcribe(self, audio_path: str) -> str:
        if not config.USE_REAL_ASR:
            print(f"录音已保存：{audio_path}")
            return input("请手动输入模拟 ASR 识别文本：").strip()
        return self._transcribe_http(audio_path)

    def _transcribe_http(self, audio_path: str) -> str:
        try:
            with open(audio_path, "rb") as audio_file:
                payload = audio_file.read()
            request = urllib.request.Request(
                config.ASR_API_URL,
                data=payload,
                headers={"Content-Type": "audio/wav"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                body = json.loads(response.read().decode("utf-8"))
            return str(body.get("text", "")).strip()
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            print(f"真实 ASR 暂不可用，错误：{exc}")
            return input("请改为手动输入模拟 ASR 识别文本：").strip()

