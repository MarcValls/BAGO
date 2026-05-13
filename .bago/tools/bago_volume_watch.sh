#!/bin/bash
# ~/.bago_core_watch.sh
# Disparado por launchd cuando /Volumes cambia.
# Si bago_core está montado y no hay sesión abierta → abre Terminal con bago start.

BAGO_CORE="/Volumes/bago_core"
BAGO_BIN="$BAGO_CORE/bago"
LOCKFILE="/tmp/.bago_core_launched"
LOG="/tmp/bago_core_watch.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] watch triggered" >> "$LOG"

# ── Caso: volumen desmontado — limpia lockfile ─────────────────────────────
if [ ! -f "$BAGO_BIN" ]; then
    if [ -f "$LOCKFILE" ]; then
        rm -f "$LOCKFILE"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] bago_core desmontado — lockfile limpiado" >> "$LOG"
    fi
    exit 0
fi

# ── Caso: volumen montado — abre terminal si no hay sesión activa ──────────
if [ -f "$LOCKFILE" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ya hay sesión activa (lockfile existe)" >> "$LOG"
    exit 0
fi

# Crear lockfile antes de abrir para evitar race condition
touch "$LOCKFILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] bago_core montado — abriendo terminal BAGO" >> "$LOG"

# Abre Terminal.app con bago start
osascript <<'APPLESCRIPT'
tell application "Terminal"
    set w to do script "cd /Volumes/bago_core && python3 bago start"
    set custom title of w to "BAGO Core"
    activate
end tell
APPLESCRIPT

echo "[$(date '+%Y-%m-%d %H:%M:%S')] terminal abierto" >> "$LOG"
