import argparse
from datetime import datetime, timezone
import random
import time

import requests


def build_metrics() -> dict:
    return {
        "temperature": round(random.uniform(22, 55), 1),
        "humidity": round(random.uniform(40, 92), 1),
        "gas": round(random.uniform(80, 420), 1),
        "light": round(random.uniform(100, 800), 1),
        "noise": round(random.uniform(35, 95), 1),
    }


def post_json(url: str, payload: dict) -> dict:
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def put_json(url: str, payload: dict) -> dict:
    response = requests.put(url, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def get_json(url: str) -> dict | list:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


def ensure_device(base_url: str, device_id: str) -> None:
    payload = {
        "device_id": device_id,
        "device_name": f"Mock device {device_id}",
        "device_type": "mock_gateway",
        "location": "SafeCloud simulator",
        "status": "online",
        "firmware_version": "mock-0.1.0",
        "description": "Simulated device used before real Loongson hardware is ready.",
    }
    response = requests.post(f"{base_url}/api/devices", json=payload, timeout=10)
    if response.status_code not in (201, 409):
        response.raise_for_status()


def upload_telemetry(base_url: str, device_id: str) -> None:
    payload = {
        "device_id": device_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": build_metrics(),
    }
    result = post_json(f"{base_url}/api/telemetry", payload)
    alarm_count = len(result.get("generated_alarms", []))
    print(f"[mock_device] uploaded metrics={payload['metrics']} generated_alarms={alarm_count}")


def poll_and_execute_commands(base_url: str, device_id: str) -> None:
    commands = get_json(f"{base_url}/api/commands/pending/{device_id}")
    for command in commands:
        command_id = command["command_id"]
        command_type = command["command_type"]
        payload = command["command_payload"]
        print(f"[mock_device] executing {command_id} type={command_type} payload={payload}")
        put_json(
            f"{base_url}/api/commands/{command_id}/result",
            {
                "status": "executed",
                "result_message": f"{command_type} executed by mock device",
            },
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="SafeCloud mock device")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--device-id", default="gateway_001")
    parser.add_argument("--interval", type=float, default=5.0)
    args = parser.parse_args()

    ensure_device(args.base_url, args.device_id)
    print(f"[mock_device] started device_id={args.device_id} base_url={args.base_url}")

    while True:
        upload_telemetry(args.base_url, args.device_id)
        poll_and_execute_commands(args.base_url, args.device_id)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
