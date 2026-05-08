#!/bin/bash
# BAGO Launcher — Ollama local bootstrap
export TERM_TITLE="BAGO-ollama"
echo -ne "\033]0;BAGO-ollama\007"
BAGO_CORE="/Volumes/bago_core"
OLLAMA_BIN="$BAGO_CORE/.bago/bin/ollama-macos"
OLLAMA_MODELS_DIR="$BAGO_CORE/.bago/.models"
export OLLAMA_MODELS="$OLLAMA_MODELS_DIR"
MODEL="${BAGO_AGENT_MODEL:-qwen2.5-coder:7b}"
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

# Arrancar servidor ollama si no está corriendo (con modelos del pendrive)
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
  echo "  Iniciando servidor Ollama (modelos del pendrive)..."
  OLLAMA_MODELS="$OLLAMA_MODELS_DIR" "$OLLAMA_BIN" serve > /tmp/bago_ollama.log 2>&1 &
  OLLAMA_PID=$!
  sleep 3
  echo "  Servidor listo (PID $OLLAMA_PID)"
  echo ""
else
  echo "  Servidor Ollama ya activo"
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
  echo "  Tarea  : $BAGO_TASK"
  echo ""
fi

# Mostrar contexto BAGO como referencia visible (no lo inyectamos como pipe)
echo "  Contexto: BAGO v${BAGO_VERSION:-3.3.0} · modo ${BAGO_MODE:-autonomous}"
echo ""
echo "  Iniciando chat interactivo con $MODEL..."
echo "  (escribe tu mensaje · /bye para salir)"
echo "  ─────────────────────────────────────────"
echo ""

# Si hay tarea, la mostramos como primer mensaje sugerido
if [ -n "$BAGO_TASK" ]; then
  echo "  💡 Primer mensaje sugerido (cópialo y pulsa Enter):"
  echo "     Estoy en BAGO v${BAGO_VERSION:-3.3.0}. Ayúdame a: $BAGO_TASK"
  echo ""
fi

# Sesión interactiva limpia — ollama mantiene el TTY y el prompt >>>
"$OLLAMA_BIN" run "$MODEL"
