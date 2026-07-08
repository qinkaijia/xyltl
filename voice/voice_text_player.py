from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


def extract_voice_text(payload: Dict[str, Any]) -> str:
    if "final_status" in payload and isinstance(payload["final_status"], dict):
        payload = payload["final_status"]
    return str(payload.get("voice_text") or payload.get("voiceText") or "").strip()


class VoiceTextPlayer:
    def __init__(self, mode: str = "") -> None:
        self.mode = mode or os.environ.get("VOICE_TTS_MODE", "print")
        self.audio_dir = Path(os.environ.get("VOICE_AUDIO_DIR", "voice/audio"))

    def speak(self, text: str) -> bool:
        text = text.strip()
        if not text:
            print("[voice] voice_text 为空，跳过播报")
            return False

        if self.mode == "none":
            return True
        if self.mode == "print":
            print(f"[voice] {text}")
            return True
        if self.mode == "espeak":
            return self._run(["espeak", "-v", "zh", text], text)
        if self.mode == "spd-say":
            return self._run(["spd-say", text], text)
        if self.mode == "audio":
            return self._play_audio(text)
        if self.mode == "baidu":
            return self._speak_baidu(text)

        print(f"[voice] 未知 VOICE_TTS_MODE={self.mode}，回退打印：{text}")
        return True

    def _play_audio(self, text: str) -> bool:
        audio_path = self._audio_path_for_text(text)
        if not audio_path.exists():
            print(f"[voice] 预录音频不存在，回退打印：{text}")
            print(f"[voice] 缺少文件：{audio_path}")
            return False
        return self._run(["aplay", str(audio_path)], text)

    def _audio_path_for_text(self, text: str) -> Path:
        if "报警" in text:
            return self.audio_dir / "alarm.wav"
        if "预警" in text:
            return self.audio_dir / "warning.wav"
        if "正常" in text:
            return self.audio_dir / "normal.wav"
        return self.audio_dir / "default.wav"

    def _speak_baidu(self, text: str) -> bool:
        voice_demo_dir = Path(__file__).resolve().parents[1] / "voice_llm_demo"
        if str(voice_demo_dir) not in sys.path:
            sys.path.insert(0, str(voice_demo_dir))
        try:
            from tts import VoiceSpeaker  # type: ignore

            return bool(VoiceSpeaker("baidu").speak(text))
        except Exception as exc:  # noqa: BLE001 - alarm voice must not crash the monitor loop.
            print(f"[voice] 百度 TTS 播报失败，回退打印：{text}")
            print(f"[voice] 错误：{exc}")
            return False

    @staticmethod
    def _run(command: list[str], fallback_text: str) -> bool:
        try:
            subprocess.run(command, check=True)
            return True
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"[voice] 播报命令不可用，回退打印：{fallback_text}")
            print(f"[voice] 错误：{exc}")
            return False


def load_payload(path: str) -> Dict[str, Any]:
    if path == "-":
        return json.loads(sys.stdin.read())
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Speak voice_text from SafeCloud/analyzer JSON.")
    parser.add_argument("--input-file", default="-", help="Response JSON file, or '-' for stdin.")
    parser.add_argument("--mode", default="", choices=["", "print", "none", "espeak", "spd-say", "audio", "baidu"])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = load_payload(args.input_file)
    text = extract_voice_text(payload)
    ok = VoiceTextPlayer(args.mode).speak(text)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
