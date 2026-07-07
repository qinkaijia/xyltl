#!/usr/bin/env bash
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
UNIT_NAME="xylt-safecloud-client.service"
UNIT_TEMPLATE="$REPO_ROOT/app_2k1000la/systemd/$UNIT_NAME.in"
SYSTEMD_USER_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
ENV_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/xylt"
ENV_FILE="$ENV_DIR/safecloud-client.env"
UNIT_FILE="$SYSTEMD_USER_DIR/$UNIT_NAME"

mkdir -p "$SYSTEMD_USER_DIR" "$ENV_DIR" "$REPO_ROOT/runtime"

if [ ! -f "$ENV_FILE" ]; then
  cat > "$ENV_FILE" <<'EOF'
# SafeCloud client user service settings.
# Leave SAFECLOUD_BASE_URL empty to use cache + UDP discovery.
# SAFECLOUD_BASE_URL=http://192.168.14.20:8010
XYLT_SENSOR_SOURCE=mock
# Use these when XYLT_SENSOR_SOURCE=2k0301.
XYLT_2K0301_MQTT_HOST=127.0.0.1
XYLT_2K0301_MQTT_PORT=1883
XYLT_2K0301_MQTT_QOS=1
XYLT_2K0301_FIRST_TIMEOUT=8
XYLT_2K0301_STALE_AFTER=5
XYLT_SCENARIO_FILE=tests/scenarios/evaluate/gas_alarm.json
XYLT_OUTPUT_FILE=runtime/latest_evaluate_response.json
XYLT_TIMEOUT=30
XYLT_DISCOVERY_TIMEOUT=3
XYLT_INTERVAL=2
EOF
fi

sed "s|@REPO_ROOT@|$REPO_ROOT|g" "$UNIT_TEMPLATE" > "$UNIT_FILE"

systemctl --user daemon-reload
systemctl --user enable "$UNIT_NAME"

if [ "${1:-}" != "--no-start" ]; then
  systemctl --user restart "$UNIT_NAME"
fi

echo "Installed $UNIT_NAME"
echo "Unit: $UNIT_FILE"
echo "Env : $ENV_FILE"
echo "Log : journalctl --user -u $UNIT_NAME -f"
