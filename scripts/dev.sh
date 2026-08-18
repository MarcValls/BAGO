#!/usr/bin/env bash
# dev.sh — Arranca backend + build frontend + electron (todo en background).
#
# Uso:
#   ./scripts/dev.sh start     # arranca todo
#   ./scripts/dev.sh stop      # mata todo
#   ./scripts/dev.sh status    # muestra qué está corriendo
#   ./scripts/dev.sh restart   # stop + start
#   ./scripts/dev.sh logs      # muestra los logs en tail -f (Ctrl+C para salir)
#
# Estructura:
#   .run/                      # PIDs y logs (ignorado por git)
#     backend.pid / backend.log
#     electron.pid / electron.log
#   backend/ui-react/dist/     # bundle de producción que sirve el backend

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN="$ROOT/.run"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
ELECTRON_DIR="$ROOT/electron-viewer"
API_URL="http://127.0.0.1:8080"

mkdir -p "$RUN"

# ─── Helpers ───────────────────────────────────────────────
log() { printf '\033[36m[dev]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[dev]\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[31m[dev]\033[0m %s\n' "$*" >&2; }

is_running() {
    local pidfile="$1"
    [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null
}

wait_for_url() {
    local url="$1" timeout="${2:-30}" i
    for ((i = 0; i < timeout; i++)); do
        if curl -fsS -m 2 "$url" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    return 1
}

# ─── Backend ───────────────────────────────────────────────
start_backend() {
    local pidfile="$RUN/backend.pid"
    local logfile="$RUN/backend.log"
    if is_running "$pidfile"; then
        log "backend ya corre (pid $(cat "$pidfile"))"
        return 0
    fi
    log "arrancando backend en $API_URL …"
    (cd "$BACKEND" && nohup python -m bago_core.launcher serve \
        --host 127.0.0.1 --port 8080 \
        > "$logfile" 2>&1 & echo $! > "$pidfile")
    if wait_for_url "$API_URL/health" 30; then
        log "backend listo (pid $(cat "$pidfile"))"
    else
        err "backend no respondió en 30s. Log: $logfile"
        return 1
    fi
}

stop_backend() {
    local pidfile="$RUN/backend.pid"
    if is_running "$pidfile"; then
        local pid; pid="$(cat "$pidfile")"
        log "matando backend (pid $pid)"
        # Matar el árbol de procesos del backend (python.exe + hijos)
        cmd //c "taskkill /F /PID $pid /T" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
        rm -f "$pidfile"
    else
        log "backend no está corriendo"
    fi
}

# ─── Frontend build ────────────────────────────────────────
build_frontend() {
    log "compilando frontend…"
    (cd "$FRONTEND" && npm run build) > "$RUN/frontend-build.log" 2>&1 || {
        err "build del frontend falló. Log: $RUN/frontend-build.log"
        return 1
    }
    # Copiar dist al backend
    rm -rf "$BACKEND/ui-react/dist"
    cp -r "$FRONTEND/dist" "$BACKEND/ui-react/"
    log "frontend compilado y copiado a backend/ui-react/dist"
}

# ─── Electron ──────────────────────────────────────────────
resolve_electron_bin() {
    local electron_bin
    electron_bin="$(
        cd "$ELECTRON_DIR"
        node -e 'const executable = require("electron"); if (typeof executable !== "string") process.exit(1); process.stdout.write(executable)'
    )" 2>/dev/null || return 1
    [[ -f "$electron_bin" ]] || return 1
    printf '%s\n' "$electron_bin"
}

start_electron() {
    local pidfile="$RUN/electron.pid"
    local logfile="$RUN/electron.log"
    local electron_bin
    if ! electron_bin="$(resolve_electron_bin)"; then
        err "electron no está instalado. Ejecuta npm ci desde la raíz"
        return 1
    fi
    if is_running "$pidfile"; then
        log "electron ya corre (pid $(cat "$pidfile"))"
        return 0
    fi
    log "arrancando electron…"
    (cd "$ELECTRON_DIR" && nohup "$electron_bin" . > "$logfile" 2>&1 & echo $! > "$pidfile")
    log "electron lanzado (pid $(cat "$pidfile"))"
}

stop_electron() {
    local pidfile="$RUN/electron.pid"
    if is_running "$pidfile"; then
        local pid; pid="$(cat "$pidfile")"
        log "matando electron (pid $pid)"
        cmd //c "taskkill /F /PID $pid /T" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
        rm -f "$pidfile"
    else
        log "electron no está corriendo"
    fi
}

# ─── Status ────────────────────────────────────────────────
status() {
    log "estado:"
    if is_running "$RUN/backend.pid"; then
        echo "  backend  : RUNNING (pid $(cat "$RUN/backend.pid")) — $API_URL"
    else
        echo "  backend  : stopped"
    fi
    if is_running "$RUN/electron.pid"; then
        echo "  electron : RUNNING (pid $(cat "$RUN/electron.pid"))"
    else
        echo "  electron : stopped"
    fi
    echo "  logs     : $RUN/*.log"
}

# ─── Logs ──────────────────────────────────────────────────
logs() {
    if [[ ! -f "$RUN/backend.log" && ! -f "$RUN/electron.log" && ! -f "$RUN/frontend-build.log" ]]; then
        warn "no hay logs aún"
        return
    fi
    # tail -f de todos los logs en paralelo
    tail -F "$RUN"/*.log 2>/dev/null
}

# ─── Acciones ──────────────────────────────────────────────
cmd="${1:-start}"
case "$cmd" in
    start)
        build_frontend
        start_backend
        start_electron
        echo
        status
        echo
        log "abrir $API_URL en el navegador, o usar la ventana de electron que acaba de abrirse"
        log "logs: tail -f $RUN/*.log  |  parar: ./scripts/dev.sh stop"
        ;;
    stop)
        stop_electron
        stop_backend
        log "todo detenido"
        ;;
    restart)
        "$0" stop || true
        sleep 2
        "$0" start
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    build)
        build_frontend
        ;;
    backend)
        start_backend
        ;;
    electron)
        start_electron
        ;;
    *)
        echo "uso: $0 {start|stop|restart|status|logs|build|backend|electron}" >&2
        exit 1
        ;;
esac
