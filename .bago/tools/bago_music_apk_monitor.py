#!/usr/bin/env python3
"""BAGO Music — monitor APK build + send Telegram notification"""

from bago_utils import load_json, save_json, timestamp_iso
import json, os, sys, time, subprocess
import requests

TOKEN = os.environ.get("BAGO_TELEGRAM_TOKEN", "").strip()
if not TOKEN:
    raise SystemExit("[FATAL] BAGO_TELEGRAM_TOKEN no definido. Exporta el token antes de ejecutar.")
CHAT_ID = os.environ.get("BAGO_TELEGRAM_CHAT", "7752787448")
REPO = "MarcValls/bago-music-saas"

def send_message(text):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={
            "chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"
        }, timeout=30)
    except Exception as e:
        print(f"[ERR] {e}")

def poll_apk_build(timeout=600):
    """Poll GitHub Actions until APK build completes"""
    send_message("🎵 <b>BAGO Music</b>\n🔄 Compilando APK...\n⏱️ Puede tardar 5-10 minutos")
    
    gh = os.path.expandvars(r"%LOCALAPPDATA%\Programs\GitHub CLI\gh.exe")
    start = time.time()
    
    while time.time() - start < timeout:
        try:
            result = subprocess.run(
                [gh, "run", "list", "--repo", REPO, "--workflow=build-apk.yml", "--limit=1", "--json", "status,conclusion,databaseId,url"],
                capture_output=True, text=True, timeout=30
            )
            runs = json.loads(result.stdout) if result.stdout else []
            if not runs:
                time.sleep(10)
                continue
            
            run = runs[0]
            status = run.get("status", "")
            conclusion = run.get("conclusion", "")
            url = run.get("url", "")
            
            if status == "completed":
                if conclusion == "success":
                    # Get artifact or release URL
                    artifact_url = f"https://github.com/{REPO}/actions/runs/{run['databaseId']}"
                    release_url = f"https://github.com/{REPO}/releases/latest"
                    
                    send_message(
                        f"✅ <b>APK BAGO Music lista</b>\n\n"
                        f"📥 <a href='{release_url}'>Descargar APK</a>\n"
                        f"🔍 <a href='{artifact_url}'>Ver build</a>\n\n"
                        f"Instala la APK y abre la app.\n"
                        f"Tambien disponible como PWA:\n"
                        f"https://marcvalls.github.io/bago-music-saas/"
                    )
                    return True
                else:
                    send_message(f"❌ Build fallo: {conclusion}\n{url}")
                    return False
            
            # Still running
            time.sleep(15)
        except Exception as e:
            print(f"[poll err] {e}")
            time.sleep(15)
    
    send_message("⏱️ Timeout esperando APK. Revisa manualmente:\nhttps://github.com/MarcValls/bago-music-saas/actions")
    return False

if __name__ == "__main__":
    poll_apk_build()
