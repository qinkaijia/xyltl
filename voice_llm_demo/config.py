"""Command-line voice interaction demo configuration."""

import os


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _load_local_env() -> None:
    """Load optional KEY=VALUE pairs from .env without adding extra dependencies."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError as exc:
        print("读取 .env 失败：{}".format(exc))


_load_local_env()

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2
FRAME_MS = 30
AUDIO_DEVICE = os.environ.get("AUDIO_DEVICE", "")

NOISE_CALIBRATION_SECONDS = _float_env("NOISE_CALIBRATION_SECONDS", 1.0)
START_SPEECH_FRAMES = _int_env("START_SPEECH_FRAMES", 3)
END_SILENCE_SECONDS = _float_env("END_SILENCE_SECONDS", 1.0)
MAX_RECORD_SECONDS = _float_env("MAX_RECORD_SECONDS", 10.0)
MIN_RECORD_SECONDS = _float_env("MIN_RECORD_SECONDS", 0.5)
THRESHOLD_RATIO = _float_env("THRESHOLD_RATIO", 3.0)
MIN_ABSOLUTE_THRESHOLD = _float_env("MIN_ABSOLUTE_THRESHOLD", 300.0)
CONTINUOUS_INTERVAL_SECONDS = float(os.environ.get("CONTINUOUS_INTERVAL_SECONDS", "0.2"))

USE_REAL_LLM = False

# ASR mode: manual / baidu / xfyun
ASR_MODE = os.environ.get("ASR_MODE", "manual")

# Baidu short speech recognition
BAIDU_API_KEY_ENV = "BAIDU_API_KEY"
BAIDU_SECRET_KEY_ENV = "BAIDU_SECRET_KEY"
BAIDU_CUID = "voice_llm_demo"
BAIDU_DEV_PID = 1537

# iFlytek voice dictation
XFYUN_APP_ID_ENV = "XFYUN_APP_ID"
XFYUN_API_KEY_ENV = "XFYUN_API_KEY"
XFYUN_API_SECRET_ENV = "XFYUN_API_SECRET"
XFYUN_LANGUAGE = "zh_cn"
XFYUN_DOMAIN = "iat"
XFYUN_ACCENT = "mandarin"

RECORDED_DIR = "data/recorded"
LOG_FILE = "logs/demo.log"

ASR_API_URL = "http://127.0.0.1:8000/api/asr"
LLM_API_URL = "http://127.0.0.1:8000/api/llm/intent"
