from functools import lru_cache
from pathlib import Path
import os


def _load_local_env(base_dir: Path) -> None:
    env_path = base_dir / ".env"
    if not env_path.exists():
        return
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        return


class Settings:
    """Minimal environment based settings for the demo cloud service."""

    def __init__(self) -> None:
        base_dir = Path(__file__).resolve().parents[2]
        _load_local_env(base_dir)
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
        self.mqtt_control_enabled = os.getenv("SAFECLOUD_MQTT_CONTROL_ENABLED", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.mqtt_control_host = os.getenv("SAFECLOUD_2K0301_MQTT_HOST", "").strip()
        self.mqtt_control_port = int(os.getenv("SAFECLOUD_2K0301_MQTT_PORT", "1883"))
        self.mqtt_control_qos = int(os.getenv("SAFECLOUD_2K0301_MQTT_QOS", "1"))
        self.mqtt_control_ack_timeout = float(os.getenv("SAFECLOUD_2K0301_ACK_TIMEOUT", "3.0"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
