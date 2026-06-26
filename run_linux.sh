#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLIENT_DIR="$SCRIPT_DIR/instantclient-basic-linux.x64-23.26.2.0.0/instantclient_23_26"

export LD_LIBRARY_PATH="$CLIENT_DIR:${LD_LIBRARY_PATH:-}"
exec python -m src.main "$@"