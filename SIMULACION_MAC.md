# SIMULACIÓN: Inicio BAGO en Mac (usuario nuevo)
# ================================================

# 1. Insertas el pendrive. macOS lo monta automáticamente en:
#    /Volumes/BAGO_USB  (o el nombre que le haya dado al pendrive)
#
# 2. Abres Terminal (Cmd + Espacio, escribe "Terminal", Enter)
#
# 3. Navegas al pendrive:

cd /Volumes/BAGO_USB/bago_fw

# 4. (Opcional) Das permisos de ejecución al launcher:
chmod +x bago.sh

# 5. Inicias BAGO:
./bago.sh status

# 6. O directamente el chat:
./bago.sh launch

# Resultado esperado:
# Fuente de verdad: /Volumes/BAGO_USB/bago_fw/.bago (PENDRIVE)
# Banner ASCII + estado
#
# NOTAS PARA MAC:
# - bago.sh usa python3, git, y rsync (todos vienen en macOS por defecto)
# - Si falta alguna dependencia Python, el script lo indicará
# - Ollama debe estar instalado previamente para modelos locales
# - Para Copilot/Codex/Claude necesitas credenciales configuradas en tu ~/.env o similar
