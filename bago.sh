#!/usr/bin/env bash
# bago.sh — BAGO 4.0 Unix Entrypoint

set -euo pipefail

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

BAGO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BAGO_CORE="$BAGO_ROOT/bago_core/cli.py"

if [[ ! -f "$BAGO_CORE" ]]; then
    echo "[ERROR] No se encontro bago_core/cli.py en $BAGO_ROOT" >&2
    exit 1
fi

exec python "$BAGO_CORE" "$@"
