#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/fetch_2k301_logs.sh"
"$SCRIPT_DIR/fetch_2k1000la_logs.sh"
echo "[fetch_all_logs] SafeCloud log fetch placeholder complete."
