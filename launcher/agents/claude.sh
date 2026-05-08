#!/bin/bash
# BAGO Launcher — Claude CLI (no instalado)
export TERM_TITLE="BAGO-claude"
echo -ne "\033]0;BAGO-claude\007"
clear
echo ""
echo "  ⬡ BAGO + Claude CLI"
echo "  ─────────────────────────────────────────"
echo ""
echo "  ⚠ Claude CLI no está instalado en este sistema."
echo ""
echo "  Para instalarlo:"
echo "  npm install -g @anthropic-ai/claude-code"
echo ""
echo "  O visita: https://docs.anthropic.com/claude/docs/cli"
echo ""
echo "  Una vez instalado, reinicia BAGO Launcher."
echo ""
read -p "  Presiona Enter para cerrar..."
