#!/bin/bash
# BAGO Launcher — arranque
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=7430

# Comprobar si ya está corriendo
if curl -s "http://localhost:$PORT/api/status" > /dev/null 2>&1; then
  echo "BAGO Launcher ya en ejecución → http://localhost:$PORT"
  open "http://localhost:$PORT"
  exit 0
fi

echo "⬡ BAGO Launcher arrancando en http://localhost:$PORT"
python3 "$SCRIPT_DIR/server.py"
