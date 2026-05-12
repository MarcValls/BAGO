#!/bin/bash
# BAGO Launcher — Ollama local bootstrap (selección dinámica de modelo)
export TERM_TITLE="BAGO-ollama"
echo -ne "\033]0;BAGO-ollama\007"
BAGO_CORE="/Volumes/bago_core"
OLLAMA_BIN="$BAGO_CORE/.bago/bin/ollama-macos"
OLLAMA_MODELS_DIR="$BAGO_CORE/.bago/.models"
export OLLAMA_MODELS="$OLLAMA_MODELS_DIR"
cd "$BAGO_CORE"

# ── Detectar modelos disponibles en el pendrive ───────────────────────────────
available_models() {
  local manifests="$OLLAMA_MODELS_DIR/manifests/registry.ollama.ai/library"
  [ -d "$manifests" ] || return
  for model_dir in "$manifests"/*/; do
    for tag_file in "$model_dir"*/; do
      echo "$(basename "$model_dir"):$(basename "$tag_file")"
    done
  done
}
AVAILABLE=$(available_models)

has_model() {
  echo "$AVAILABLE" | grep -q "^$1$"
}

# ── Selección dinámica por palabras clave de la tarea ────────────────────────
select_model() {
  local task
  task="$(echo "$BAGO_TASK" | tr '[:upper:]' '[:lower:]')"  # lowercase (bash 3 compat)

  # Si el usuario ya especificó modelo → respetarlo
  if [ -n "$BAGO_AGENT_MODEL" ]; then
    echo "$BAGO_AGENT_MODEL"; return
  fi

  # Sin tarea → el más capaz disponible
  if [ -z "$task" ]; then
    has_model "qwen2.5-coder:7b"  && echo "qwen2.5-coder:7b"  && return
    has_model "llama3.2:latest"   && echo "llama3.2:latest"    && return
    has_model "llama3.2:1b"       && echo "llama3.2:1b"        && return
    has_model "qwen2.5:0.5b"      && echo "qwen2.5:0.5b"       && return
    echo "$AVAILABLE" | head -1; return
  fi

  # Palabras clave → código/técnico → qwen2.5-coder:7b
  local code_kw="código code función function script bash python javascript typescript clase class método method api json xml html css refactor bug fix error debug implementar implement loop array objeto object test prueba deploy server"
  for kw in $code_kw; do
    if echo "$task" | grep -qw "$kw"; then
      has_model "qwen2.5-coder:7b" && echo "qwen2.5-coder:7b" && return
      break
    fi
  done

  # Palabras clave → análisis/texto largo → llama3.2:latest
  local analysis_kw="analiza análisis explica explicar redacta redactar documento razona razonamiento resumen resume describe descripción estrategia plan planifica comparar evalúa evaluar pros contras decisión"
  for kw in $analysis_kw; do
    if echo "$task" | grep -qw "$kw"; then
      has_model "llama3.2:latest" && echo "llama3.2:latest" && return
      break
    fi
  done

  # Palabras clave → rápido/ligero → llama3.2:1b
  local quick_kw="rápido rapido simple corto lista nota apunta idea ideas brainstorm pregunta responde traduce traducir"
  for kw in $quick_kw; do
    if echo "$task" | grep -qw "$kw"; then
      has_model "llama3.2:1b"   && echo "llama3.2:1b"   && return
      has_model "qwen2.5:0.5b"  && echo "qwen2.5:0.5b"  && return
      break
    fi
  done

  # Default → más capaz disponible
  has_model "qwen2.5-coder:7b" && echo "qwen2.5-coder:7b" && return
  has_model "llama3.2:latest"  && echo "llama3.2:latest"  && return
  has_model "llama3.2:1b"      && echo "llama3.2:1b"      && return
  has_model "qwen2.5:0.5b"     && echo "qwen2.5:0.5b"     && return
  echo "$AVAILABLE" | head -1
}

MODEL=$(select_model)

# ── Razón de la selección (para mostrar al usuario) ───────────────────────────
model_reason() {
  case "$1" in
    qwen2.5-coder:7b) echo "especialista en código (7B)" ;;
    llama3.2:latest)  echo "análisis y texto (3B)" ;;
    llama3.2:1b)      echo "respuesta rápida (1B)" ;;
    qwen2.5:0.5b)     echo "ultraligero (0.5B)" ;;
    *)                echo "$1" ;;
  esac
}

clear
echo ""
echo "  ⬡ BAGO + Ollama (local)"
echo "  ─────────────────────────────────────────"
python3 bago hello --quick 2>/dev/null || echo "  [bago hello no disponible]"
echo ""
echo "  Agente : Ollama local"
echo "  Modelo : $MODEL  ← $(model_reason "$MODEL")"
echo "  Sin internet · Privado · Rápido"
echo ""

# ── Arrancar servidor si no está corriendo ────────────────────────────────────
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

# ── Leer estado BAGO ──────────────────────────────────────────────────────────
STATE="$BAGO_CORE/.bago/state/global_state.json"
if [ -f "$STATE" ]; then
  BAGO_VERSION=$(python3 -c "import json; d=json.load(open('$STATE')); print(d.get('bago_version','?'))" 2>/dev/null)
  BAGO_MODE=$(python3 -c "import json; d=json.load(open('$STATE')); print(d.get('mode','?'))" 2>/dev/null)
fi

echo "  ─────────────────────────────────────────"
[ -n "$BAGO_TASK" ] && echo "  Tarea  : $BAGO_TASK" && echo ""
echo "  Contexto: BAGO v${BAGO_VERSION:-3.3.0} · modo ${BAGO_MODE:-autonomous}"
echo ""
echo "  Chat interactivo — /bye para salir"

if [ -n "$BAGO_TASK" ]; then
  echo ""
  echo "  💡 Primer mensaje sugerido:"
  echo "     Estoy en BAGO v${BAGO_VERSION:-3.3.0}. Ayúdame a: $BAGO_TASK"
fi

echo "  ─────────────────────────────────────────"
echo ""

# ── Sesión interactiva ────────────────────────────────────────────────────────
"$OLLAMA_BIN" run "$MODEL"
