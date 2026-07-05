#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$REPO_ROOT/safecloud"
HOST="${SAFECLOUD_HOST:-127.0.0.1}"
PORT="${SAFECLOUD_PORT:-8000}"

echo "[run_safecloud] starting SafeCloud at http://$HOST:$PORT"
uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
