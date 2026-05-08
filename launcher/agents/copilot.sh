#!/bin/bash
# BAGO Launcher — GitHub Copilot bootstrap
export TERM_TITLE="BAGO-copilot"
echo -ne "\033]0;BAGO-copilot\007"
BAGO_CORE="/Volumes/bago_core"
cd "$BAGO_CORE"

clear
echo ""
echo "  ⬡ BAGO + GitHub Copilot"
echo "  ─────────────────────────────────────────"
python3 bago hello --quick 2>/dev/null || echo "  [bago hello no disponible]"
echo ""
echo "  Agente : GitHub Copilot CLI"
echo "  Comando: gh copilot suggest"
echo ""

if [ -n "$BAGO_TASK" ]; then
  echo "  Tarea  : $BAGO_TASK"
  echo ""
  echo "  ─────────────────────────────────────────"
  echo "  Copia este contexto para tu agente:"
  echo ""
  echo "  Lee .bago/state/global_state.json y"
  echo "  ayúdame a: $BAGO_TASK"
  echo ""
fi

echo "  ─────────────────────────────────────────"
echo "  Iniciando gh copilot..."
echo ""
gh copilot suggest
