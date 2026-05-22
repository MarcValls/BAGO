#!/bin/bash
# launch_miniapp.sh — Lanza BAGO Mini App (servidor local + ngrok HTTPS)
# La URL de ngrok se inyecta automáticamente en el bot de Telegram.
#
# Uso: bash launch_miniapp.sh [--port 8080]
#
# Requiere:
#   - Python 3 (ya disponible)
#   - ngrok instalado: ~/.local/bin/ngrok
#   - Token Telegram en notify_config.json

set -e

PORT=${1:-8080}
TOOLS_DIR="$(cd "$(dirname "$0")" && pwd)"
NGROK_BIN="${HOME}/.local/bin/ngrok"
CONFIG_FILE="$TOOLS_DIR/notify_config.json"
LOG_FILE="/tmp/bago_miniapp.log"
NGROK_LOG="/tmp/bago_ngrok.log"

echo "🤖 BAGO Mini App — Lanzando..."

# 1) Matar instancias previas
pkill -f "bago_miniapp_server.py" 2>/dev/null || true
pkill -f "ngrok http $PORT" 2>/dev/null || true
sleep 1

# 2) Iniciar servidor Python en background
echo "[1/3] Iniciando servidor local en :$PORT..."
python3 "$TOOLS_DIR/bago_miniapp_server.py" --port "$PORT" > "$LOG_FILE" 2>&1 &
SERVER_PID=$!
sleep 2

# Verificar que arrancó
if ! kill -0 "$SERVER_PID" 2>/dev/null; then
  echo "❌ Error al iniciar servidor. Ver $LOG_FILE"
  exit 1
fi
echo "    ✅ Servidor PID $SERVER_PID"

# 3) Iniciar ngrok
echo "[2/3] Iniciando ngrok HTTPS tunnel..."
"$NGROK_BIN" http "$PORT" --log "$NGROK_LOG" --log-format json &
NGROK_PID=$!
sleep 4

# 4) Obtener URL pública de ngrok
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null \
  | python3 -c "
import json,sys
try:
    d = json.load(sys.stdin)
    tunnels = d.get('tunnels', [])
    for t in tunnels:
        if t.get('proto') == 'https':
            print(t['public_url'])
            break
except:
    pass
")

if [ -z "$NGROK_URL" ]; then
  echo "❌ No se pudo obtener URL de ngrok. Comprueba ngrok auth."
  echo "   Log: $NGROK_LOG"
  kill "$SERVER_PID" 2>/dev/null || true
  exit 1
fi

echo "    ✅ URL pública: $NGROK_URL"

# 5) Notificar al bot de Telegram con la URL
echo "[3/3] Notificando al bot..."
TG_TOKEN=$(python3 -c "
import json
with open('$CONFIG_FILE') as f:
    d=json.load(f)
print(d.get('telegram',{}).get('bot_token',''))
" 2>/dev/null)

OWNER_ID=$(python3 -c "
import json
with open('$CONFIG_FILE') as f:
    d=json.load(f)
print(d.get('telegram',{}).get('owner_chat_id',''))
" 2>/dev/null)

# Guardar miniapp_url en notify_config.json para que el bot pueda leerla
python3 - <<PYEOF
import json
from pathlib import Path
cfg_path = Path("$CONFIG_FILE")
d = json.loads(cfg_path.read_text())
d.setdefault("telegram", {})["miniapp_url"] = "$NGROK_URL"
cfg_path.write_text(json.dumps(d, indent=2, ensure_ascii=False))
PYEOF
echo "    ✅ URL guardada en notify_config.json"

if [ -n "$TG_TOKEN" ] && [ -n "$OWNER_ID" ]; then
  MSG="🌐 *BAGO Mini App activa*%0A%0AURL: ${NGROK_URL}%0A%0AAbre con /app o el botón del menú."
  curl -s "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
    -d "chat_id=${OWNER_ID}&text=${MSG}&parse_mode=Markdown" > /dev/null && \
    echo "    ✅ Mensaje enviado al bot"
fi

# 6) Configurar botón del bot con la URL (setMenuButton)
if [ -n "$TG_TOKEN" ]; then
  curl -s "https://api.telegram.org/bot${TG_TOKEN}/setChatMenuButton" \
    -H "Content-Type: application/json" \
    -d "{\"menu_button\": {\"type\": \"web_app\", \"text\": \"📊 BAGO\", \"web_app\": {\"url\": \"${NGROK_URL}\"}}}" \
    > /dev/null && echo "    ✅ Menu button configurado en el bot"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ BAGO Mini App ACTIVA"
echo "   Local:   http://localhost:$PORT"
echo "   HTTPS:   $NGROK_URL"
echo "   Logs:    $LOG_FILE"
echo "   Server:  PID $SERVER_PID"
echo "   ngrok:   PID $NGROK_PID"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Abre Telegram → @bago_amtec_bot → botón 📊 BAGO"
echo ""
echo "Para parar: kill $SERVER_PID $NGROK_PID"
echo "           (o pkill -f bago_miniapp_server.py)"
