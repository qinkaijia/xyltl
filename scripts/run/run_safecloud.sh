#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$REPO_ROOT/safecloud"
echo "[run_safecloud] starting SafeCloud at http://127.0.0.1:8000"
uvicorn app.main:app --reload
