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
echo "  Comando: gh copilot"
echo ""

echo "  ─────────────────────────────────────────"

if [ -n "$BAGO_TASK" ]; then
  echo "  Iniciando con tarea: $BAGO_TASK"
  echo ""
  PROMPT="Estoy usando el framework BAGO v$(python3 -c "import json; d=json.load(open('.bago/state/global_state.json')); print(d.get('bago_version','3.3.0'))" 2>/dev/null || echo '3.3.0'). Ayúdame a: $BAGO_TASK"
  gh copilot -- --prompt "$PROMPT"
else
  echo "  Iniciando sesión interactiva..."
  echo ""
  gh copilot
fi
