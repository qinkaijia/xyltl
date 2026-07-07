#!/usr/bin/env bash
set -euo pipefail

VM_HOST="${VM_HOST:-vm-build}"
BOARD_2K1000LA_HOST="${BOARD_2K1000LA_HOST:-board-2k1000la}"
BOARD_2K301_HOST="${BOARD_2K301_HOST:-board-2k301}"

for host in "$VM_HOST" "$BOARD_2K1000LA_HOST" "$BOARD_2K301_HOST"; do
  echo "[check_ssh] checking $host"
  ssh -o BatchMode=yes -o ConnectTimeout=5 "$host" "echo ok"
done
