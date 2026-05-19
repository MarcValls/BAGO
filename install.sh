#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  BAGO Installer — macOS / Linux
#  Uso:
#    curl -fsSL https://raw.githubusercontent.com/MarcValls/BAGO/main/install.sh | bash
#  O con directorio personalizado:
#    curl -fsSL https://raw.githubusercontent.com/MarcValls/BAGO/main/install.sh | bash -s -- --dir ~/mis-proyectos/bago
# ─────────────────────────────────────────────────────────────
set -euo pipefail

REPO="https://github.com/MarcValls/BAGO.git"
DEFAULT_DIR="$HOME/BAGO"
INSTALL_DIR="$DEFAULT_DIR"
SHELL_RC=""

# ── Colores ──────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
ok()   { echo -e "${GREEN}✅ $*${RESET}"; }
warn() { echo -e "${YELLOW}⚠  $*${RESET}"; }
err()  { echo -e "${RED}❌ $*${RESET}"; exit 1; }
info() { echo -e "${CYAN}   $*${RESET}"; }

# ── Args ─────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir) INSTALL_DIR="$2"; shift 2 ;;
    *) shift ;;
  esac
done

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}  BAGO Framework — Instalador v3.4.3${RESET}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""

# ── Requisitos ───────────────────────────────────────────────
info "Comprobando requisitos..."
command -v python3 >/dev/null || err "Python 3.9+ requerido. Instálalo desde https://python.org"
command -v git     >/dev/null || err "Git requerido. Instálalo desde https://git-scm.com"

PY_VER=$(python3 -c "import sys; print(sys.version_info.minor)")
[[ "$PY_VER" -ge 9 ]] || err "Se requiere Python 3.9+. Versión actual: 3.$PY_VER"
ok "Python $(python3 --version | cut -d' ' -f2)"
ok "Git $(git --version | cut -d' ' -f3)"

# ── Clonar / actualizar ──────────────────────────────────────
if [[ -d "$INSTALL_DIR/.git" ]]; then
  info "Actualizando repo existente en $INSTALL_DIR..."
  git -C "$INSTALL_DIR" pull --quiet
  ok "Repo actualizado"
else
  info "Clonando en $INSTALL_DIR..."
  git clone --quiet "$REPO" "$INSTALL_DIR"
  ok "Repo clonado"
fi

# ── Dependencias Python ──────────────────────────────────────
info "Instalando dependencias Python..."
python3 -m pip install --quiet litellm rich prompt_toolkit 2>/dev/null || \
  warn "pip tuvo advertencias (puede ser normal)"
ok "Dependencias instaladas"

# ── global_state.json ────────────────────────────────────────
TMPL="$INSTALL_DIR/.bago/templates/global_state.clean.json"
STATE="$INSTALL_DIR/.bago/state/global_state.json"
if [[ ! -f "$STATE" && -f "$TMPL" ]]; then
  python3 "$INSTALL_DIR/.bago/tools/bootstrap_state.py" "$INSTALL_DIR"
  ok "global_state.json creado"
fi

# ── Alias en shell ───────────────────────────────────────────
detect_rc() {
  local shell_name
  shell_name=$(basename "${SHELL:-bash}")
  case "$shell_name" in
    zsh)  echo "$HOME/.zshrc" ;;
    bash) echo "$HOME/.bashrc" ;;
    fish) echo "$HOME/.config/fish/config.fish" ;;
    *)    echo "$HOME/.profile" ;;
  esac
}

SHELL_RC=$(detect_rc)
ALIAS_LINE="alias bago='python3 $INSTALL_DIR/bago'"

if grep -q "alias bago=" "$SHELL_RC" 2>/dev/null; then
  sed -i.bak "s|alias bago=.*|$ALIAS_LINE|" "$SHELL_RC"
  ok "Alias bago actualizado en $SHELL_RC"
else
  echo "" >> "$SHELL_RC"
  echo "# BAGO Framework" >> "$SHELL_RC"
  echo "$ALIAS_LINE" >> "$SHELL_RC"
  ok "Alias bago añadido en $SHELL_RC"
fi

# ── Validar instalación ──────────────────────────────────────
info "Validando instalación..."
if python3 "$INSTALL_DIR/bago" validate; then
  ok "bago validate → OK"
else
  err "bago validate → KO. Instalación abortada."
fi

# ── Resumen ──────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${GREEN}${BOLD}  ✅ BAGO instalado correctamente${RESET}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo -e "  Directorio : ${CYAN}$INSTALL_DIR${RESET}"
echo -e "  Shell RC   : ${CYAN}$SHELL_RC${RESET}"
echo ""
echo -e "  ${BOLD}Próximos pasos:${RESET}"
echo -e "    1) Recarga tu shell:  ${YELLOW}source $SHELL_RC${RESET}"
echo -e "    2) Lanza BAGO:        ${YELLOW}bago launch${RESET}"
echo -e "    3) Verifica estado:   ${YELLOW}bago health${RESET}"
echo ""

