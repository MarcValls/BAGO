#!/bin/bash
# Arranca cloudflared, captura la URL pública y actualiza el bot automáticamente.
# Diseñado para ejecutarse como LaunchAgent o manualmente.

set -e

CLOUDFLARED_BIN="/tmp/cloudflared"
TUNNEL_LOG="/tmp/cloudflared.log"
BOT_PLIST="$HOME/Library/LaunchAgents/com.bago.tragaperras.plist"
ENV_FILE="/Volumes/bago_core/projects/tragaperras_bot/.env"
BOT_TOKEN="8519892399:AAHTKzfu_VyLUSpJ-iNjmSn9RcgFOsddeKA"

echo "[$(date)] Iniciando tunnel_manager..." | tee -a /tmp/tunnel_manager.log

# Matar cualquier cloudflared previo
pkill -f "cloudflared tunnel" 2>/dev/null || true
sleep 2

# Limpiar log anterior
> "$TUNNEL_LOG"

# Iniciar cloudflared en background
"$CLOUDFLARED_BIN" tunnel --url http://localhost:8080 --no-autoupdate \
    > "$TUNNEL_LOG" 2>&1 &
CF_PID=$!
echo "[$(date)] cloudflared PID: $CF_PID" | tee -a /tmp/tunnel_manager.log

# Esperar URL pública (máx 60 segundos)
WEBAPP_URL=""
for i in $(seq 1 30); do
    WEBAPP_URL=$(grep -o 'https://[a-zA-Z0-9-]*\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1)
    if [ -n "$WEBAPP_URL" ]; then
        WEBAPP_URL="${WEBAPP_URL}/index.html"
        echo "[$(date)] URL capturada: $WEBAPP_URL" | tee -a /tmp/tunnel_manager.log
        break
    fi
    sleep 2
done

if [ -z "$WEBAPP_URL" ]; then
    echo "[$(date)] ERROR: No se obtuvo URL pública en 60s" | tee -a /tmp/tunnel_manager.log
    exit 1
fi

# Actualizar .env
grep -v "WEBAPP_URL" "$ENV_FILE" > "$ENV_FILE.tmp" && mv "$ENV_FILE.tmp" "$ENV_FILE"
echo "WEBAPP_URL=$WEBAPP_URL" >> "$ENV_FILE"
echo "[$(date)] .env actualizado" | tee -a /tmp/tunnel_manager.log

# Actualizar plist del bot
/usr/bin/plutil -replace EnvironmentVariables.WEBAPP_URL -string "$WEBAPP_URL" "$BOT_PLIST"
echo "[$(date)] plist actualizado con nueva URL" | tee -a /tmp/tunnel_manager.log

# Reiniciar el bot para que tome el nuevo WEBAPP_URL
launchctl unload "$BOT_PLIST" 2>/dev/null || true
sleep 3
launchctl load "$BOT_PLIST"
echo "[$(date)] Bot reiniciado con nueva URL: $WEBAPP_URL" | tee -a /tmp/tunnel_manager.log

# Mantener proceso activo (esperar al cloudflared)
wait $CF_PID
echo "[$(date)] cloudflared terminó, tunnel_manager sale" | tee -a /tmp/tunnel_manager.log
