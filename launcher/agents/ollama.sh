#!/bin/bash
# BAGO Launcher — Ollama local bootstrap
export TERM_TITLE="BAGO-ollama"
echo -ne "\033]0;BAGO-ollama\007"
BAGO_CORE="/Volumes/bago_core"
OLLAMA_BIN="$BAGO_CORE/.bago/bin/ollama-macos"
MODEL="${BAGO_AGENT_MODEL:-llama3.2:latest}"
cd "$BAGO_CORE"

clear
echo ""
echo "  ⬡ BAGO + Ollama (local)"
echo "  ─────────────────────────────────────────"
python3 bago hello --quick 2>/dev/null || echo "  [bago hello no disponible]"
echo ""
echo "  Agente : Ollama local"
echo "  Modelo : $MODEL"
echo "  Sin internet · Privado · Rápido"
echo ""

# Arrancar servidor ollama si no está corriendo
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
  echo "  Iniciando servidor Ollama..."
  "$OLLAMA_BIN" serve > /tmp/bago_ollama.log 2>&1 &
  OLLAMA_PID=$!
  sleep 2
  echo "  Servidor listo (PID $OLLAMA_PID)"
  echo ""
fi

# Leer estado BAGO para contexto
BAGO_CONTEXT=""
STATE="$BAGO_CORE/.bago/state/global_state.json"
if [ -f "$STATE" ]; then
  BAGO_VERSION=$(python3 -c "import json; d=json.load(open('$STATE')); print(d.get('bago_version','?'))" 2>/dev/null)
  BAGO_MODE=$(python3 -c "import json; d=json.load(open('$STATE')); print(d.get('mode','?'))" 2>/dev/null)
  BAGO_CONTEXT="Contexto BAGO: versión=$BAGO_VERSION, modo=$BAGO_MODE."
fi

echo "  ─────────────────────────────────────────"

if [ -n "$BAGO_TASK" ]; then
  PROMPT="$BAGO_CONTEXT Eres un asistente técnico operando bajo el framework BAGO. Tarea: $BAGO_TASK"
  echo "  Tarea  : $BAGO_TASK"
  echo ""
  echo "  Iniciando sesión con $MODEL..."
  echo ""
  echo "$PROMPT" | "$OLLAMA_BIN" run "$MODEL"
else
  PROMPT="$BAGO_CONTEXT Eres un asistente técnico operando bajo el framework BAGO v3.3.0. Estás listo para ayudar. ¿Cuál es la tarea?"
  echo "  Iniciando sesión con $MODEL..."
  echo ""
  echo "$PROMPT" | "$OLLAMA_BIN" run "$MODEL"
fi
