#!/bin/bash
# BAGO Launcher — arranque con puerto libre
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="/tmp/bago_launcher.log"
echo "=== start_launcher $(date) ===" >> "$LOG"

# Puerto libre desde 7430
find_free_port() {
  local p=7430
  while lsof -i TCP:$p >/dev/null 2>&1; do p=$((p+1)); done
  echo $p
}

# Reutilizar si ya corre
for p in $(seq 7430 7445); do
  if curl -s --max-time 1 "http://localhost:$p/api/status" >/dev/null 2>&1; then
    echo "BAGO Launcher ya en ejecución → http://localhost:$p"
    command -v open >/dev/null && open "http://localhost:$p"
    exit 0
  fi
done

PORT=$(find_free_port)
echo "⬡ BAGO Launcher arrancando en http://localhost:$PORT"
echo "Puerto: $PORT" >> "$LOG"

cd "$SCRIPT_DIR"
BAGO_PORT=$PORT python3 server.py &
SERVER_PID=$!

# Esperar hasta 10s
for i in $(seq 1 20); do
  sleep 0.5
  if curl -s --max-time 1 "http://localhost:$PORT/api/status" >/dev/null 2>&1; then
    echo "✓ Listo en http://localhost:$PORT"
    command -v open >/dev/null && open "http://localhost:$PORT"
    wait $SERVER_PID
    exit 0
  fi
done

echo "⚠ Timeout esperando servidor — revisa /tmp/bago_launcher.log"
wait $SERVER_PID
