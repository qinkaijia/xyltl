from functools import lru_cache
from pathlib import Path
import os


class Settings:
    """Minimal environment based settings for the demo cloud service."""

    def __init__(self) -> None:
        base_dir = Path(__file__).resolve().parents[2]
        self.app_name = os.getenv("SAFECLOUD_APP_NAME", "SafeCloud")
        self.api_prefix = os.getenv("SAFECLOUD_API_PREFIX", "/api")
        self.database_url = os.getenv(
            "SAFECLOUD_DATABASE_URL",
            f"sqlite:///{base_dir / 'safecloud.db'}",
        )
        self.cors_origins = [
            item.strip()
            for item in os.getenv("SAFECLOUD_CORS_ORIGINS", "*").split(",")
            if item.strip()
        ]
        self.online_timeout_seconds = int(os.getenv("SAFECLOUD_ONLINE_TIMEOUT_SECONDS", "120"))
        self.metric_thresholds = {
            "temperature": float(os.getenv("SAFECLOUD_THRESHOLD_TEMPERATURE", "45")),
            "humidity": float(os.getenv("SAFECLOUD_THRESHOLD_HUMIDITY", "85")),
            "gas": float(os.getenv("SAFECLOUD_THRESHOLD_GAS", "300")),
            "smoke": float(os.getenv("SAFECLOUD_THRESHOLD_SMOKE", "200")),
            "noise": float(os.getenv("SAFECLOUD_THRESHOLD_NOISE", "85")),
            "voltage": float(os.getenv("SAFECLOUD_THRESHOLD_VOLTAGE", "250")),
            "current": float(os.getenv("SAFECLOUD_THRESHOLD_CURRENT", "20")),
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
