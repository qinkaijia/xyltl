"""Command-line voice interaction demo configuration."""

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2
FRAME_MS = 30

NOISE_CALIBRATION_SECONDS = 1.0
START_SPEECH_FRAMES = 3
END_SILENCE_SECONDS = 1.0
MAX_RECORD_SECONDS = 10.0
MIN_RECORD_SECONDS = 0.5
THRESHOLD_RATIO = 3.0
MIN_ABSOLUTE_THRESHOLD = 300

USE_REAL_LLM = False

# ASR mode: manual / baidu / xfyun
ASR_MODE = "manual"

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
