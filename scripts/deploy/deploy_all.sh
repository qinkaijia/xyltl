#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/deploy_2k301.sh"
"$SCRIPT_DIR/deploy_2k1000la.sh"
echo "[deploy_all] Protocol and config sync placeholders complete."
