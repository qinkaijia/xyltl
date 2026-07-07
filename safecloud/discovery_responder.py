from __future__ import annotations

import argparse
import json
import os
import socket
from typing import Tuple


DISCOVER_MESSAGE = b"SAFECLOUD_DISCOVER"


def local_ip_for(peer: Tuple[str, int]) -> str:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect((peer[0], peer[1]))
        return probe.getsockname()[0]
    finally:
        probe.close()


def build_response(peer: Tuple[str, int], service_port: int, public_host: str = "") -> bytes:
    host = public_host or local_ip_for(peer)
    payload = {
        "service": "SafeCloud",
        "version": "0.1",
        "base_url": f"http://{host}:{service_port}",
        "host": host,
        "port": service_port,
    }
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def serve(bind_host: str, discovery_port: int, service_port: int, public_host: str = "") -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((bind_host, discovery_port))
    print(
        f"[safecloud-discovery] listening udp://{bind_host}:{discovery_port}, "
        f"service_port={service_port}"
    )
    while True:
        data, addr = sock.recvfrom(4096)
        if data.strip() != DISCOVER_MESSAGE:
            continue
        response = build_response(addr, service_port, public_host)
        sock.sendto(response, addr)
        print(f"[safecloud-discovery] replied to {addr[0]}:{addr[1]}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SafeCloud UDP discovery responder")
    parser.add_argument("--bind-host", default=os.environ.get("SAFECLOUD_DISCOVERY_HOST", "0.0.0.0"))
    parser.add_argument("--discovery-port", type=int, default=int(os.environ.get("SAFECLOUD_DISCOVERY_PORT", "8011")))
    parser.add_argument("--service-port", type=int, default=int(os.environ.get("SAFECLOUD_PORT", "8010")))
    parser.add_argument("--public-host", default=os.environ.get("SAFECLOUD_PUBLIC_HOST", ""))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    serve(args.bind_host, args.discovery_port, args.service_port, args.public_host)


if __name__ == "__main__":
    main()
