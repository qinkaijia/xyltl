from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from urllib.parse import urlencode
import urllib.request

import config


class VoiceSpeaker:
    def __init__(self, mode: str = "") -> None:
        self.mode = (mode or config.VOICE_TTS_MODE or "none").strip().lower()
        self.output_dir = Path("data/tts")
        self._baidu_token = ""

    def speak(self, text: str) -> bool:
        clean = " ".join(str(text or "").split())
        if not clean or self.mode == "none":
            return False
        clean = clean[: config.VOICE_TTS_MAX_CHARS]
        try:
            if self.mode == "print":
                print("[TTS] {}".format(clean))
                return True
            elif self.mode == "baidu":
                self._speak_baidu(clean)
                return True
            else:
                print("未知 VOICE_TTS_MODE={}，跳过播报。".format(self.mode))
                return False
        except Exception as exc:  # noqa: BLE001 - field demo must not crash on TTS.
            print("语音播报失败：{}".format(exc))
            return False

    def _speak_baidu(self, text: str) -> None:
        if not shutil.which("aplay"):
            raise RuntimeError("未找到 aplay，无法播放百度 TTS 音频")
        token = self._get_baidu_token()
        params = {
            "tex": text,
            "tok": token,
            "cuid": config.BAIDU_CUID,
            "ctp": 1,
            "lan": "zh",
            "spd": 5,
            "pit": 5,
            "vol": 8,
            "per": 0,
            "aue": 6,
        }
        request = urllib.request.Request(
            "https://tsn.baidu.com/text2audio",
            data=urlencode(params).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read()
            content_type = response.headers.get("Content-Type", "")
        if "json" in content_type or body.startswith(b"{"):
            try:
                error = json.loads(body.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                error = body[:200].decode("utf-8", errors="replace")
            raise RuntimeError("百度 TTS 返回错误：{}".format(error))

        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / "reply_{}.wav".format(int(time.time() * 1000))
        path.write_bytes(body)
        playback_timeout = max(30, min(90, int(len(text) * 0.45) + 12))
        subprocess.run(["aplay", "-q", str(path)], check=False, timeout=playback_timeout)

    def _get_baidu_token(self) -> str:
        if self._baidu_token:
            return self._baidu_token
        api_key = os.environ.get(config.BAIDU_API_KEY_ENV, "")
        secret_key = os.environ.get(config.BAIDU_SECRET_KEY_ENV, "")
        if not api_key or not secret_key:
            raise RuntimeError("缺少百度 TTS 密钥环境变量")
        params = urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": api_key,
                "client_secret": secret_key,
            }
        )
        with urllib.request.urlopen("https://aip.baidubce.com/oauth/2.0/token?" + params, timeout=15) as response:
            body = json.loads(response.read().decode("utf-8"))
        token = body.get("access_token")
        if not token:
            raise RuntimeError("获取百度 access_token 失败：{}".format(body))
        self._baidu_token = str(token)
        return self._baidu_token
