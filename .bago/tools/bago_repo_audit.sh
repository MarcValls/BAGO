#!/bin/bash
# bago_repo_audit.sh — Auditoría automática de repositorio con propose-tasks
# Detecta: cambios git, TODOs, CI faltante, archivos grandes
# Fuente: PANEL_ORQUESTADOR/scripts/propose-tasks.mjs (MarcValls)
#
# Uso: bago_repo_audit.sh [--path /ruta/repo] [--format json|md] [--output out.md]

TOOL_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$TOOL_DIR/bago_propose_tasks.mjs"

if [ ! -f "$SCRIPT" ]; then
  echo "[ERROR] No se encuentra $SCRIPT"
  exit 1
fi

# Default: current dir
ARGS=("$@")
if [[ "$*" != *"--path"* ]]; then
  ARGS+=("--path" "$(pwd)")
fi

node "$SCRIPT" "${ARGS[@]}"
