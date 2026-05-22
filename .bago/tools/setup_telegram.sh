#!/bin/bash
# setup_telegram.sh — Configura y arranca el bot de Telegram de BAGO
# Uso: ./setup_telegram.sh <TOKEN_DE_BOTFATHER>

TOKEN="$1"
if [ -z "$TOKEN" ]; then
    echo "❌ Uso: $0 <TOKEN>"
    echo "   Ejemplo: $0 7123456789:AAFxxxxxxx"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BAGO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
CONFIG="$BAGO_ROOT/.bago/tools/notify_config.json"

# Añadir token al config
python3 - "$TOKEN" "$CONFIG" << 'PYEOF'
import json, sys
from pathlib import Path

token    = sys.argv[1]
cfg_path = Path(sys.argv[2])
cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
cfg.setdefault("telegram", {})["bot_token"] = token
cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
print(f"✅ Token guardado en notify_config.json")
PYEOF

# Cargar launchd
launchctl unload ~/Library/LaunchAgents/com.bago.tg-daemon.plist 2>/dev/null
sleep 1
launchctl load ~/Library/LaunchAgents/com.bago.tg-daemon.plist
sleep 3

echo "--- Log ---"
cat /tmp/bago_telegram.log
echo ""
echo "✅ Bot arrancado. Abre Telegram, busca tu bot y escribe /start"
