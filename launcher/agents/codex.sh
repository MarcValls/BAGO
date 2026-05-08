#!/bin/bash
# BAGO Launcher — OpenAI Codex bootstrap
export TERM_TITLE="BAGO-codex"
echo -ne "\033]0;BAGO-codex\007"
BAGO_CORE="/Volumes/bago_core"
cd "$BAGO_CORE"

clear
echo ""
echo "  ⬡ BAGO + OpenAI Codex"
echo "  ─────────────────────────────────────────"
python3 bago hello --quick 2>/dev/null || echo "  [bago hello no disponible]"
echo ""
echo "  Agente : OpenAI Codex CLI"
echo "  Modelo : ${BAGO_AGENT_MODEL:-o4-mini}"
echo ""

if [ -n "$BAGO_TASK" ]; then
  echo "  Tarea  : $BAGO_TASK"
  echo ""
fi

echo "  ─────────────────────────────────────────"
echo "  Iniciando codex..."
echo ""
# Inyectar contexto BAGO como prompt inicial si hay tarea
if [ -n "$BAGO_TASK" ]; then
  codex --model "${BAGO_AGENT_MODEL:-o4-mini}" \
    "Lee el archivo .bago/state/global_state.json para contexto BAGO. Tarea: $BAGO_TASK"
else
  codex --model "${BAGO_AGENT_MODEL:-o4-mini}"
fi
