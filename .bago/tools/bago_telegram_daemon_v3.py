import requests, subprocess, time, threading, os
from pathlib import Path
from datetime import datetime

TOKEN = "8519892399:AAHTKzfu_VyLUSpJ-iNjmSn9RcgFOsddeKA"
API = "https://api.telegram.org/bot" + TOKEN
BAGO = Path.home() / "BAGO"
LOG = Path.home() / ".bago" / "state" / "logs" / "daemon_v3.log"
LOG.parent.mkdir(parents=True, exist_ok=True)

def log(msg):
    line = "[" + datetime.now().strftime("%H:%M:%S") + "] " + msg
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)

log("START pid=" + str(os.getpid()))

OFFSET = 0
while True:
    try:
        r = requests.get(API + "/getUpdates", params={"offset": OFFSET, "limit": 5}, timeout=30)
        data = r.json()
        if not data.get("ok"):
            log("API_ERR: " + str(data))
            time.sleep(5)
            continue
        
        for u in data.get("result", []):
            OFFSET = max(OFFSET, u["update_id"] + 1)
            msg = u.get("message")
            if not msg:
                continue
            text = msg.get("text", "").strip()
            chat = msg["chat"]["id"]
            user = msg["from"].get("first_name", "?")
            log("MSG " + user + ": " + text)
            
            if text.startswith("/"):
                reply = "BAGO activo. Escribe un comando como 'status' o 'ideas'."
            else:
                ps1 = BAGO / "bago.ps1"
                try:
                    result = subprocess.run(
                        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps1)] + text.split(),
                        capture_output=True, text=True, timeout=60, cwd=str(BAGO)
                    )
                    reply = (result.stdout or result.stderr or "OK")[:3500]
                except Exception as e:
                    reply = "Error: " + str(e)
            
            try:
                requests.post(API + "/sendMessage", json={"chat_id": chat, "text": reply[:4000]}, timeout=30)
                log("REPLIED to " + user)
            except Exception as e:
                log("SEND_ERR: " + str(e))
        
        time.sleep(2)
    except KeyboardInterrupt:
        log("STOP")
        break
    except Exception as e:
        log("ERR: " + str(e))
        time.sleep(5)
