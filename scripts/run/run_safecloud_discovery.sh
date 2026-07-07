#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$REPO_ROOT/safecloud"

DISCOVERY_HOST="${SAFECLOUD_DISCOVERY_HOST:-0.0.0.0}"
DISCOVERY_PORT="${SAFECLOUD_DISCOVERY_PORT:-8011}"
SERVICE_PORT="${SAFECLOUD_PORT:-8010}"

echo "[run_safecloud_discovery] listening udp://$DISCOVERY_HOST:$DISCOVERY_PORT -> SafeCloud port $SERVICE_PORT"
python discovery_responder.py \
  --bind-host "$DISCOVERY_HOST" \
  --discovery-port "$DISCOVERY_PORT" \
  --service-port "$SERVICE_PORT"
