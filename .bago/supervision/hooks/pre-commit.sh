#!/bin/sh
# BAGO pre-commit hook — verifica deriva de contratos antes de cada commit.
# Instalado por: python .bago/supervision/install_hooks.py
#
# Ejecuta contract_drift_loop en modo dry-run (no escribe artefactos).
# Sale con código 1 si detecta deriva bloqueante — aborta el commit.

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
SUPERVISOR="$REPO_ROOT/.bago/supervision/supervisor.py"

# Si no existe el supervisor o está deshabilitado, dejar pasar
if [ ! -f "$SUPERVISOR" ]; then
    exit 0
fi
if [ -n "$BAGO_SUPERVISION_SKIP" ]; then
    exit 0
fi

echo "🔍 BAGO: verificando contrato antes del commit..."
python "$SUPERVISOR" run --loop contract_drift --dry-run
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ BAGO Supervision: deriva detectada. Revisa el estado con:"
    echo "   python .bago/supervision/supervisor.py status"
    echo "   Para omitir: BAGO_SUPERVISION_SKIP=1 git commit ..."
    exit 1
fi

echo "✅ BAGO: contrato verificado."
exit 0
