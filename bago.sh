#!/usr/bin/env bash
# bago.sh — BAGO Launcher para macOS/Linux (portable)
# Uso: ./bago.sh <comando> [args]
# Coloca este archivo junto a .bago/ y runtime_contract.json

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

if [ -n "${PYTHONPATH:-}" ]; then
    export PYTHONPATH="${SCRIPT_DIR}:${SCRIPT_DIR}/.bago/tools:${PYTHONPATH}"
else
    export PYTHONPATH="${SCRIPT_DIR}:${SCRIPT_DIR}/.bago/tools"
fi

SOURCE=""
PRIMARY=""
SECONDARY=""

# Colores
CLR_CYAN='\033[0;36m'
CLR_GREEN='\033[0;32m'
CLR_YELLOW='\033[0;33m'
CLR_RED='\033[0;31m'
CLR_WHITE='\033[0;37m'
CLR_DGRAY='\033[0;90m'
CLR_MAGENTA='\033[0;35m'
CLR_RESET='\033[0m'

# === Detección de fuente de verdad ===
detect_source() {
    local exeDir="$SCRIPT_DIR"
    local usbBago="${exeDir}/.bago"
    local pcBago="${HOME}/BAGO/.bago"
    local pcDocs="${HOME}/Documents/BAGO/.bago"

    local usbExists=false
    if [ -d "$usbBago" ]; then usbExists=true; fi

    local pcExists=false
    local pcPath=""
    if [ -d "$pcBago" ]; then pcExists=true; pcPath="$pcBago"; elif [ -d "$pcDocs" ]; then pcExists=true; pcPath="$pcDocs"; fi

    local isRemovable=false
    # Heuristica: si estamos en /Volumes o /media, es removible
    if [[ "$exeDir" == /Volumes/* ]] || [[ "$exeDir" == /media/* ]]; then
        isRemovable=true
    fi

    if [ "$usbExists" = true ] && [ "$isRemovable" = true ]; then
        SOURCE="usb"
        PRIMARY="$usbBago"
        if [ "$pcExists" = true ] && [ "$pcPath" != "$usbBago" ]; then
            SECONDARY="$pcPath"
        fi
        echo -e "${CLR_CYAN}Fuente de verdad: ${usbBago} (PENDRIVE)${CLR_RESET}"
    elif [ "$usbExists" = true ]; then
        SOURCE="usb"
        PRIMARY="$usbBago"
        if [ "$pcExists" = true ] && [ "$pcPath" != "$usbBago" ]; then
            SECONDARY="$pcPath"
            echo -e "${CLR_CYAN}Fuente de verdad: ${usbBago} (DIRECTORIO LOCAL). PC: ${pcPath}${CLR_RESET}"
        else
            echo -e "${CLR_CYAN}Fuente de verdad: ${usbBago} (DIRECTORIO LOCAL)${CLR_RESET}"
        fi
    elif [ "$pcExists" = true ]; then
        SOURCE="pc"
        PRIMARY="$pcPath"
        echo -e "${CLR_GREEN}Fuente de verdad: ${pcPath} (PC INSTALADO)${CLR_RESET}"
    else
        SOURCE="none"
        echo -e "${CLR_RED}BAGO no detectado. Ejecuta: BAGO install${CLR_RESET}"
        exit 1
    fi

    if [ -n "$PRIMARY" ]; then
        local portableUserHome=""
        if [ -n "${ProgramData:-}" ]; then
            portableUserHome="${ProgramData}/BAGO/user"
        else
            portableUserHome="${PRIMARY}/user"
        fi
        mkdir -p "$portableUserHome"
        export BAGO_USER_HOME="$portableUserHome"
    fi
}

show_banner() {
    detect_source
    local bannerScript="${PRIMARY}/tools/bago_banner.py"
    if [ -f "$bannerScript" ]; then
        python3 "$bannerScript"
    else
        echo ""
        echo -e "${CLR_CYAN}  BAGO Framework v2026.05${CLR_RESET}"
        echo -e "${CLR_DGRAY}  Balanceado · Adaptativo · Generativo · Organizativo${CLR_RESET}"
        echo ""
    fi
}

show_status() {
    detect_source
    echo ""
    echo -e "${CLR_WHITE}  BAGO Status${CLR_RESET}"
    echo -e "${CLR_DGRAY}  ----------------------------------------------${CLR_RESET}"
    echo -e "${CLR_WHITE}  Modo:       ${SOURCE}${CLR_RESET}"
    echo -e "${CLR_GREEN}  Primaria:   ${PRIMARY}${CLR_RESET}"
    if [ -n "${SECONDARY:-}" ]; then
        echo -e "${CLR_CYAN}  Secundaria: ${SECONDARY}${CLR_RESET}"
    fi
    echo ""
}

install_component() {
    local component="${1:-}"
    if [ -z "$component" ]; then
        echo ""
        echo -e "${CLR_WHITE}  Componentes disponibles para instalar:${CLR_RESET}"
        echo -e "${CLR_GREEN}  Modelos locales (Ollama):${CLR_RESET}"
        echo -e "${CLR_WHITE}    qwen25-coder  — 4.5GB, código Python${CLR_RESET}"
        echo -e "${CLR_WHITE}    llama32       — 1.9GB, uso general${CLR_RESET}"
        echo -e "${CLR_WHITE}    llama32-1b    — 1.2GB, clasificación${CLR_RESET}"
        echo -e "${CLR_WHITE}    qwen25-mini   — 379MB, ultra-rápido${CLR_RESET}"
        echo -e "${CLR_GREEN}  Herramientas:${CLR_RESET}"
        echo -e "${CLR_WHITE}    codex         — OpenAI Codex CLI${CLR_RESET}"
        echo -e "${CLR_WHITE}    copilot       — GitHub Copilot CLI${CLR_RESET}"
        echo -e "${CLR_WHITE}    all           — Todos los modelos locales${CLR_RESET}"
        echo ""
        echo -e "${CLR_DGRAY}  Uso: BAGO install <componente>${CLR_RESET}"
        return
    fi
    detect_source
    echo -e "${CLR_GREEN}Instalando: ${component}${CLR_RESET}"
    case "$component" in
        qwen25-coder)
            echo -e "${CLR_CYAN}Descargando qwen2.5-coder:7b (4.5GB)...${CLR_RESET}"
            ollama pull qwen2.5-coder:7b
            echo -e "${CLR_GREEN}✓ qwen25-coder instalado${CLR_RESET}"
            ;;
        llama32)
            echo -e "${CLR_CYAN}Descargando llama3.2:latest (1.9GB)...${CLR_RESET}"
            ollama pull llama3.2:latest
            echo -e "${CLR_GREEN}✓ llama32 instalado${CLR_RESET}"
            ;;
        llama32-1b)
            echo -e "${CLR_CYAN}Descargando llama3.2:1b (1.2GB)...${CLR_RESET}"
            ollama pull llama3.2:1b
            echo -e "${CLR_GREEN}✓ llama32-1b instalado${CLR_RESET}"
            ;;
        qwen25-mini)
            echo -e "${CLR_CYAN}Descargando qwen2.5:0.5b (379MB)...${CLR_RESET}"
            ollama pull qwen2.5:0.5b
            echo -e "${CLR_GREEN}✓ qwen25-mini instalado${CLR_RESET}"
            ;;
        all)
            echo -e "${CLR_CYAN}Descargando todos los modelos locales...${CLR_RESET}"
            ollama pull qwen2.5-coder:7b
            ollama pull llama3.2:latest
            ollama pull llama3.2:1b
            ollama pull qwen2.5:0.5b
            echo -e "${CLR_GREEN}✓ Todos los modelos locales instalados${CLR_RESET}"
            ;;
        codex)
            echo -e "${CLR_CYAN}Codex CLI se instala vía npm:${CLR_RESET}"
            echo -e "${CLR_WHITE}  npm install -g @openai/codex${CLR_RESET}"
            ;;
        copilot)
            echo -e "${CLR_CYAN}Copilot CLI se instala vía gh:${CLR_RESET}"
            echo -e "${CLR_WHITE}  gh extension install github/gh-copilot${CLR_RESET}"
            ;;
        *)
            echo -e "${CLR_RED}Componente desconocido: ${component}${CLR_RESET}"
            ;;
    esac
}

sync_usb() {
    local direction="${1:-auto}"
    detect_source
    if [ -z "${SECONDARY:-}" ]; then
        echo -e "${CLR_RED}No se detectó USB secundario.${CLR_RESET}"
        exit 1
    fi
    local knowledgeSrc="${PRIMARY}/knowledge"
    local knowledgeDst="${SECONDARY}/knowledge"
    local stateSrc="${PRIMARY}/state"
    local stateDst="${SECONDARY}/state"

    mkdir -p "$knowledgeDst" "$stateDst"

    if [ "$direction" = "to-usb" ] || [ "$direction" = "auto" ]; then
        echo -e "${CLR_CYAN}Sync PC → USB...${CLR_RESET}"
        rsync -a --delete --exclude='.git' "$knowledgeSrc/" "$knowledgeDst/"
        rsync -a --delete --exclude='.git' "$stateSrc/" "$stateDst/"
    fi
    if [ "$direction" = "from-usb" ] || [ "$direction" = "auto" ]; then
        echo -e "${CLR_CYAN}Sync USB → PC...${CLR_RESET}"
        rsync -a --delete --exclude='.git' "$knowledgeDst/" "$knowledgeSrc/"
        rsync -a --delete --exclude='.git' "$stateDst/" "$stateSrc/"
    fi
    echo -e "${CLR_GREEN}Sincronización completa.${CLR_RESET}"
}

sync_knowledge() {
    detect_source
    local knowledgeScript="${PRIMARY}/tools/knowledge_sync.py"
    if [ ! -f "$knowledgeScript" ]; then
        echo -e "${CLR_RED}No se encontró knowledge_sync.py${CLR_RESET}"
        return
    fi
    python3 "$knowledgeScript" "${@:-sync}"
}

invoke_bago_chat() {
    local provider="${1:-}"
    shift || true
    detect_source
    export BAGO_USER_CWD="$(pwd)"
    local chatScript="${PRIMARY}/tools/bago_chat.py"
    if [ -n "$provider" ]; then
        python3 "$chatScript" --provider "$provider"
    elif [ $# -gt 0 ]; then
        python3 "$chatScript" "$@"
    else
        python3 "$chatScript"
    fi
}

invoke_canonical_entry() {
    local from="${1:-launch}"
    local provider="${2:-}"
    shift 2 || true
    if [ "$from" != "launch" ]; then
        echo -e "${CLR_YELLOW}Alias '${from}' redirigido a entrada canónica: BAGO launch${CLR_RESET}"
    fi
    if [ -n "$provider" ]; then
        invoke_bago_chat "$provider" "$@"
    else
        invoke_bago_chat "" "$@"
    fi
}

# === Main ===
COMMAND="${1:-}"
shift || true

# Compatibilidad con mayúsculas/minúsculas
COMMAND_LC="$(echo "$COMMAND" | tr '[:upper:]' '[:lower:]')"

case "$COMMAND_LC" in
    "")
        show_banner
        invoke_canonical_entry "default"
        ;;
    status)
        show_banner
        show_status
        ;;
    launch|chat)
        invoke_canonical_entry "$COMMAND" "" "$@"
        ;;
    copilot)
        invoke_canonical_entry "copilot" "copilot"
        ;;
    codex|gpt)
        invoke_canonical_entry "codex" "codex"
        ;;
    claude)
        invoke_canonical_entry "claude" "claude"
        ;;
    ollama)
        invoke_canonical_entry "ollama" "ollama"
        ;;
    install)
        install_component "${1:-}"
        ;;
    sync)
        if [ "${1:-}" = "knowledge" ]; then
            shift || true
            sync_knowledge "$@"
        else
            sync_usb "${1:-auto}"
        fi
        ;;
    knowledge)
        sync_knowledge "$@"
        ;;
    menu)
        detect_source
        python3 "${PRIMARY}/tools/bago_menu.py" "$@"
        ;;
    pipeline)
        detect_source
        python3 "${PRIMARY}/tools/bago_pipeline.py" "$*"
        ;;
    inventory)
        detect_source
        python3 "${PRIMARY}/tools/bago_inventory.py" "$@"
        ;;
    contribute)
        detect_source
        echo "Contribute no implementado en bago.sh todavía."
        ;;
    repo)
        case "${1:-}" in
            init) echo "Repo init: crea manualmente con gh repo create..." ;;
            sync) echo "Repo sync: usa git add, commit, push manualmente." ;;
            *) echo -e "${CLR_YELLOW}Uso: BAGO repo init | BAGO repo sync${CLR_RESET}" ;;
        esac
        ;;
    build|test|lint|deploy|run|clean|db-reset|ideas|telegram|apk)
        detect_source
        echo -e "${CLR_YELLOW}Comando '${COMMAND}' delegado al launcher Python...${CLR_RESET}"
        local root="$(dirname "$PRIMARY")"
        local candidate="${root}/bago"
        local coreLauncher="${root}/bago_core/launcher.py"
        if [ -f "$candidate" ]; then
            python3 "$candidate" "$COMMAND" "$@"
        elif [ -f "$coreLauncher" ]; then
            python3 "$coreLauncher" "$COMMAND" "$@"
        else
            echo -e "${CLR_RED}No se encontró launcher Python para ${COMMAND}${CLR_RESET}"
        fi
        ;;
    help|--help|-h)
        echo ""
        echo -e "${CLR_WHITE}BAGO Launcher v2026.05 (macOS/Linux)${CLR_RESET}"
        echo ""
        echo "Uso: ./bago.sh <comando> [args]"
        echo ""
        echo -e "${CLR_GREEN}Comandos principales:${CLR_RESET}"
        echo "  launch, chat, copilot, codex, claude, ollama  → Entrada a la app"
        echo "  status                                        → Estado de BAGO"
        echo "  install [componente]                          → Instala modelo o herramienta"
        echo "  sync [to-usb|from-usb|knowledge]              → Sincroniza"
        echo "  menu                                          → Menú interactivo"
        echo "  pipeline <tarea>                              → Pipeline multi-modelo"
        echo "  inventory                                     → Inventario de herramientas"
        echo ""
        ;;
    *)
        echo -e "${CLR_RED}Comando desconocido: ${COMMAND}${CLR_RESET}"
        echo -e "${CLR_YELLOW}Ejecuta: ./bago.sh help${CLR_RESET}"
        exit 1
        ;;
esac
