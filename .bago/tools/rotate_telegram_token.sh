#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# rotate_telegram_token.sh — Rotación segura del token de Telegram para BAGO
#
# Uso:
#   bash rotate_telegram_token.sh <NUEVO_TOKEN>
#   bash rotate_telegram_token.sh <NUEVO_TOKEN> --render-key <RENDER_API_KEY> --service <RENDER_SERVICE_ID>
#
# Qué hace:
#   1. Valida el nuevo token con Telegram (getMe)
#   2. Borra el webhook del token VIEJO (si tienes el viejo)
#   3. Registra el webhook del nuevo token en la URL de Render
#   4. Actualiza BAGO_TELEGRAM_TOKEN en Render.com (si tienes API key)
#   5. Guarda el token en ~/.bago_music_saas.json (config local)
#   6. Muestra instrucciones para revocar el token viejo en @BotFather
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── colores ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
ok()   { echo -e "${GREEN}✓${RESET}  $*"; }
warn() { echo -e "${YELLOW}⚠ ${RESET} $*"; }
err()  { echo -e "${RED}✗${RESET}  $*" >&2; }
info() { echo -e "${CYAN}→${RESET}  $*"; }

# ── args ──────────────────────────────────────────────────────────────────────
NEW_TOKEN="${1:-}"
RENDER_API_KEY=""
RENDER_SERVICE_ID=""
WEBHOOK_URL=""

shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --render-key)    RENDER_API_KEY="$2";    shift 2 ;;
    --service)       RENDER_SERVICE_ID="$2"; shift 2 ;;
    --webhook-url)   WEBHOOK_URL="$2";       shift 2 ;;
    *) warn "Argumento desconocido: $1"; shift ;;
  esac
done

if [[ -z "$NEW_TOKEN" ]]; then
  echo ""
  echo -e "${BOLD}rotate_telegram_token.sh${RESET} — Rotación segura del token Telegram"
  echo ""
  echo "  Uso: bash rotate_telegram_token.sh <NUEVO_TOKEN> [opciones]"
  echo ""
  echo "  Opciones:"
  echo "    --render-key <key>      API key de Render.com (para actualizar env var)"
  echo "    --service <id>          Service ID de Render (p.ej. srv-abc123)"
  echo "    --webhook-url <url>     URL del servidor (p.ej. https://mi-app.onrender.com)"
  echo ""
  echo "  Ejemplo mínimo:"
  echo "    bash rotate_telegram_token.sh 123456:ABC-NUEVO"
  echo ""
  echo "  Ejemplo completo:"
  echo "    bash rotate_telegram_token.sh 123456:ABC-NUEVO \\"
  echo "      --render-key rnd_xxxx \\"
  echo "      --service srv-xxxx \\"
  echo "      --webhook-url https://bago-music.onrender.com"
  echo ""
  exit 1
fi

echo ""
echo -e "${BOLD}🔐 BAGO — Rotación de token Telegram${RESET}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── paso 1: validar nuevo token ───────────────────────────────────────────────
info "Paso 1/5 — Validando nuevo token con Telegram..."
GETME=$(curl -sf "https://api.telegram.org/bot${NEW_TOKEN}/getMe" 2>/dev/null || echo "ERROR")
if echo "$GETME" | grep -q '"ok":true'; then
  BOT_NAME=$(echo "$GETME" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result']['username'])" 2>/dev/null || echo "?")
  ok "Token válido — bot: @${BOT_NAME}"
else
  err "Token inválido o sin conexión a Telegram."
  echo "   Respuesta: $GETME"
  echo ""
  echo "   ¿Cómo obtener un token nuevo?"
  echo "   1. Abre Telegram y busca @BotFather"
  echo "   2. Escribe /mybots → selecciona tu bot → API Token → Revoke current token"
  echo "   3. Copia el nuevo token y vuelve a ejecutar este script"
  exit 1
fi

# ── paso 2: borrar webhook del token viejo (si aplica) ───────────────────────
info "Paso 2/5 — Intentando borrar webhook del token VIEJO..."
OLD_TOKEN="8519892399:AAHTKzfu_VyLUSpJ-iNjmSn9RcgFOsddeKA"
DEL=$(curl -sf "https://api.telegram.org/bot${OLD_TOKEN}/deleteWebhook" 2>/dev/null || echo "")
if echo "$DEL" | grep -q '"ok":true'; then
  ok "Webhook del token viejo borrado."
elif echo "$DEL" | grep -q '401'; then
  ok "Token viejo ya inválido (revocado en BotFather) — correcto."
else
  warn "No se pudo borrar webhook del viejo token (posiblemente ya revocado)."
fi

# ── paso 3: registrar webhook del nuevo token ─────────────────────────────────
info "Paso 3/5 — Registrando webhook..."

# Intentar leer URL desde config local si no se pasó
if [[ -z "$WEBHOOK_URL" ]]; then
  LOCAL_CFG="$HOME/.bago_music_saas.json"
  if [[ -f "$LOCAL_CFG" ]]; then
    WEBHOOK_URL=$(python3 -c "
import json, sys
d = json.load(open('$LOCAL_CFG'))
print(d.get('api_url', '').rstrip('/'))
" 2>/dev/null || echo "")
  fi
fi

if [[ -n "$WEBHOOK_URL" ]]; then
  WH_ENDPOINT="${WEBHOOK_URL}/webhook"
  WH_RESP=$(curl -sf -X POST \
    "https://api.telegram.org/bot${NEW_TOKEN}/setWebhook" \
    -H "Content-Type: application/json" \
    -d "{\"url\": \"${WH_ENDPOINT}\"}" 2>/dev/null || echo "ERROR")
  if echo "$WH_RESP" | grep -q '"ok":true'; then
    ok "Webhook registrado en ${WH_ENDPOINT}"
  else
    warn "No se pudo registrar webhook automáticamente."
    warn "Hazlo manualmente: bago music-saas webhook ${WEBHOOK_URL}"
  fi
else
  warn "URL de servidor no especificada — webhook no registrado."
  info "  Ejecuta después: bago music-saas webhook <URL_RENDER>"
fi

# ── paso 4: actualizar en Render.com ─────────────────────────────────────────
info "Paso 4/5 — Actualizando Render.com..."

if [[ -n "$RENDER_API_KEY" && -n "$RENDER_SERVICE_ID" ]]; then
  # Render API v1: PATCH /services/{id}/env-vars
  RENDER_RESP=$(curl -sf -X PUT \
    "https://api.render.com/v1/services/${RENDER_SERVICE_ID}/env-vars" \
    -H "Authorization: Bearer ${RENDER_API_KEY}" \
    -H "Content-Type: application/json" \
    -d "[{\"key\": \"BAGO_TELEGRAM_TOKEN\", \"value\": \"${NEW_TOKEN}\"}]" \
    2>/dev/null || echo "ERROR")
  
  if echo "$RENDER_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print('ok' if isinstance(d,list) else 'err')" 2>/dev/null | grep -q "ok"; then
    ok "BAGO_TELEGRAM_TOKEN actualizado en Render.com"
    info "  El servicio se redesplegará automáticamente."
  else
    warn "No se pudo actualizar Render.com automáticamente."
    warn "Respuesta: ${RENDER_RESP:0:200}"
    echo ""
    info "  Hazlo manualmente:"
    info "  → https://dashboard.render.com/web/${RENDER_SERVICE_ID}/env"
    info "  → Clave: BAGO_TELEGRAM_TOKEN"
    info "  → Valor: ${NEW_TOKEN}"
  fi
else
  warn "Sin API key de Render — actualiza manualmente:"
  echo ""
  echo "    https://dashboard.render.com"
  echo "    → Tu servicio → Environment → BAGO_TELEGRAM_TOKEN"
  echo "    → Nuevo valor: ${NEW_TOKEN}"
  echo ""
fi

# ── paso 5: guardar en config local ──────────────────────────────────────────
info "Paso 5/5 — Guardando en configuración local..."
LOCAL_CFG="$HOME/.bago_music_saas.json"
if [[ -f "$LOCAL_CFG" ]]; then
  python3 - <<PYEOF
import json
p = "$LOCAL_CFG"
with open(p) as f:
    cfg = json.load(f)
cfg["telegram_token"] = "$NEW_TOKEN"
with open(p, "w") as f:
    json.dump(cfg, f, indent=2)
print("  Config actualizada: $LOCAL_CFG")
PYEOF
else
  python3 -c "
import json
cfg = {'telegram_token': '${NEW_TOKEN}'}
with open('${LOCAL_CFG}', 'w') as f:
    json.dump(cfg, f, indent=2)
print('  Config creada: ${LOCAL_CFG}')
"
fi
ok "Config local guardada."

# ── instrucciones manuales ────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BOLD}⚠️  ACCIÓN MANUAL REQUERIDA${RESET} — Revoca el token viejo en BotFather:"
echo ""
echo "  1. Abre Telegram → busca @BotFather"
echo "  2. Escribe: /mybots"
echo "  3. Selecciona tu bot"
echo "  4. API Token → Revoke current token"
echo "     (si ya tienes el nuevo token, esto revoca el VIEJO automáticamente)"
echo ""
echo -e "${BOLD}Token viejo comprometido:${RESET}"
echo "  ${OLD_TOKEN}"
echo ""
echo -e "${BOLD}Token nuevo activo:${RESET}"
echo "  ${NEW_TOKEN}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${GREEN}✅ Rotación completada.${RESET}"
echo ""
