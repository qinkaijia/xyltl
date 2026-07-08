#!/bin/sh
# 2K0301 MQTT mock bridge for XYLT integration.
# Runs on the 2K0301 board. It publishes sensor/heartbeat packets to
# the 2K1000LA MQTT broker and ACKs command messages.
#
# Usage on 2K0301:
#   /root/xylt_mqtt_tools/xylt_301_mqtt_mock.sh 192.168.43.36 1883

BROKER="${1:-192.168.43.36}"
PORT="${2:-1883}"
DEVICE_ID="${DEVICE_ID:-board_2k0301}"
TOOL_DIR="/root/xylt_mqtt_tools"
PUB="$TOOL_DIR/mosquitto_pub"
SUB="$TOOL_DIR/mosquitto_sub"
export LD_LIBRARY_PATH="$TOOL_DIR:${LD_LIBRARY_PATH}"

SENSOR_TOPIC="device/${DEVICE_ID}/sensor"
HEARTBEAT_TOPIC="device/${DEVICE_ID}/heartbeat"
ACK_TOPIC="device/${DEVICE_ID}/ack"
COMMAND_TOPIC="device/${DEVICE_ID}/command"
LOG_FILE="/tmp/xylt_301_mqtt_mock.log"

publish() {
  topic="$1"
  payload="$2"
  "$PUB" -h "$BROKER" -p "$PORT" -q 1 -t "$topic" -m "$payload"
}

ack_loop() {
  "$SUB" -h "$BROKER" -p "$PORT" -q 1 -t "$COMMAND_TOPIC" | while IFS= read -r msg; do
    echo "$(date '+%Y-%m-%d %H:%M:%S') RX $msg" >> "$LOG_FILE"
    seq=$(echo "$msg" | sed -n 's/.*"seq":\([0-9][0-9]*\).*/\1/p')
    cmd=$(echo "$msg" | sed -n 's/.*"command":"\([^"]*\)".*/\1/p')
    [ -z "$seq" ] && seq=0
    case "$cmd" in
      fan_control|buzzer_control|alarm_light|device_reset)
        payload="{\"type\":\"ack\",\"seq\":$seq,\"ok\":true,\"message\":\"$cmd accepted by 2K0301 mock\"}"
        ;;
      *)
        payload="{\"type\":\"ack\",\"seq\":$seq,\"ok\":false,\"error_code\":\"UNKNOWN_COMMAND\",\"message\":\"unknown command\"}"
        ;;
    esac
    publish "$ACK_TOPIC" "$payload"
    echo "$(date '+%Y-%m-%d %H:%M:%S') ACK $payload" >> "$LOG_FILE"
  done
}

: > "$LOG_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') starting broker=$BROKER:$PORT device=$DEVICE_ID" >> "$LOG_FILE"
ack_loop &
ACK_PID=$!
trap 'kill $ACK_PID 2>/dev/null; exit 0' INT TERM EXIT

seq=0
hb=0
while true; do
  ts=$(date '+%Y-%m-%dT%H:%M:%S')
  temp=$(awk "BEGIN { printf \"%.1f\", 25.0 + (($seq % 10) / 10.0) }")
  hum=$(awk "BEGIN { printf \"%.1f\", 55.0 + (($seq % 6) / 10.0) }")
  payload="{\"type\":\"sensor_packet\",\"seq\":$seq,\"payload\":{\"device_id\":\"$DEVICE_ID\",\"timestamp\":\"$ts\",\"temperature\":$temp,\"humidity\":$hum,\"tvoc\":120,\"eco2\":450,\"mq3_value\":0.123,\"flame_detected\":false,\"risk_score\":0}}"
  publish "$SENSOR_TOPIC" "$payload"
  if [ $((seq % 2)) -eq 0 ]; then
    hb=$((hb + 1))
    hb_payload="{\"type\":\"heartbeat\",\"seq\":$hb,\"device_id\":\"$DEVICE_ID\",\"uptime_ms\":$((hb * 2000)),\"sensor_online\":true,\"actuator_online\":true,\"error_flags\":[]}"
    publish "$HEARTBEAT_TOPIC" "$hb_payload"
  fi
  seq=$((seq + 1))
  sleep 1
done
