#!/usr/bin/env bash
# BAGO One-Click Installer v3.4.4
# Uso:
#   curl -fsSL https://github.com/MarcValls/BAGO/releases/download/v3.4.4/install-bago.sh | bash
#   O descarga install-bago.sh, chmod +x install-bago.sh, ./install-bago.sh

set -euo pipefail

REPO="https://github.com/MarcValls/BAGO"
ZIP_URL="$REPO/releases/download/v3.4.4/BAGO-3.4.1.zip"
INSTALL_DIR="$HOME/BAGO"
TMP_ZIP="/tmp/BAGO-3.4.1.zip"

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; RESET='\033[0m'
ok()  { echo -e "${GREEN}[OK]${RESET} $*"; }
err() { echo -e "${RED}[XX]${RESET} $*"; exit 1; }
info(){ echo -e "${CYAN}[..]${RESET} $*"; }

echo ""
echo "==========================================="
echo "  BAGO Framework v3.4.4 — Instalador Rapido"
echo "==========================================="
echo ""

# --- Check Python ---
info "Comprobando Python..."
command -v python3 >/dev/null || err "Python 3.9+ requerido. Instalalo desde https://python.org"
PY_VER=$(python3 -c "import sys; print(sys.version_info.minor)")
[[ "$PY_VER" -ge 9 ]] || err "Se requiere Python 3.9+. Version actual: 3.$PY_VER"
ok "Python $(python3 --version | cut -d' ' -f2)"

# --- Download ---
info "Descargando BAGO desde GitHub..."
if command -v curl >/dev/null; then
    curl -fsSL "$ZIP_URL" -o "$TMP_ZIP" || err "Descarga fallida"
elif command -v wget >/dev/null; then
    wget -q "$ZIP_URL" -O "$TMP_ZIP" || err "Descarga fallida"
else
    err "curl o wget requeridos para descargar el paquete"
fi
ok "Descarga completa"

# --- Extract ---
[[ -d "$INSTALL_DIR" ]] && rm -rf "$INSTALL_DIR"
info "Extrayendo..."
python3 -c "import zipfile, os; z=zipfile.ZipFile('$TMP_ZIP'); z.extractall('$INSTALL_DIR'); z.close()" || err "Extraccion fallida"
BAGO_ROOT="$INSTALL_DIR/BAGO-3.4.1"
[[ -f "$BAGO_ROOT/bago" ]] || err "Estructura inesperada despues de extraer"
ok "Extraido en $INSTALL_DIR"

# --- Bootstrap ---
info "Inicializando estado limpio..."
python3 "$BAGO_ROOT/.bago/tools/bootstrap_state.py" "$BAGO_ROOT" || err "Bootstrap fallido"

# --- Validate ---
info "Validando instalacion..."
if python3 "$BAGO_ROOT/bago" validate; then
    ok "bago validate → OK"
else
    err "VALIDACION FALLIDA — Instalacion abortada."
fi

# --- Encoding ---
info "Verificando encoding..."
if python3 "$BAGO_ROOT/.bago/tools/encoding_guard.py" "$BAGO_ROOT"; then
    ok "encoding → OK"
else
    err "Encoding check fallo"
fi

# --- Alias ---
SHELL_RC=""
shell_name=$(basename "${SHELL:-bash}")
case "$shell_name" in
    zsh)  SHELL_RC="$HOME/.zshrc" ;;
    bash) SHELL_RC="$HOME/.bashrc" ;;
    fish) SHELL_RC="$HOME/.config/fish/config.fish" ;;
    *)    SHELL_RC="$HOME/.profile" ;;
esac

ALIAS_LINE="alias bago='python3 $BAGO_ROOT/bago'"
if [[ -f "$SHELL_RC" ]] && grep -q "alias bago=" "$SHELL_RC" 2>/dev/null; then
    ok "Alias bago ya existe en $SHELL_RC"
else
    echo "" >> "$SHELL_RC"
    echo "# BAGO Framework v3.4.4" >> "$SHELL_RC"
    echo "$ALIAS_LINE" >> "$SHELL_RC"
    ok "Alias anadido a $SHELL_RC"
fi

# --- Resumen ---
echo ""
echo "==========================================="
echo -e "  ${GREEN}BAGO v3.4.4 instalado correctamente${RESET}"
echo "==========================================="
echo ""
echo -e "  Directorio: ${CYAN}$BAGO_ROOT${RESET}"
echo -e "  Comando:    ${CYAN}bago${RESET} (tras recargar el shell)"
echo ""
echo "  Primeros pasos:"
echo "    source $SHELL_RC"
echo "    bago --version"
echo "    bago help"
echo ""
