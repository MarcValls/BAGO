#!/usr/bin/env python3
"""
BAGO Canary — Trampas éticas de detección LOCAL
══════════════════════════════════════════════════════════════════
Genera señuelos con credenciales FALSAS pero REALISTAS y monitorea
si alguien los lee, modifica o elimina.

Tipos soportados (sin dependencia de red):
  - aws_keys      : Par AccessKey + SecretAccessKey falso (formato real)
  - openai_api    : Key sk-... falsa
  - github_pat    : Token ghp_... falso
  - telegram_bot  : Token numerico:falso
  - google_api    : Key AIzaSy... falsa
  - web_bug       : Enlace a webhook público que captura IP del visitante

USO:
    python bago_canary.py deploy --type aws_keys
    python bago_canary.py check                    # revisa si alguien tocó los señuelos
    python bago_canary.py list                     # lista señuelos activos
    python bago_canary.py purge                    # elimina todos

ETHICAL USE:
    Señuelos en TU propio disco, en TU propio sistema.
    Si alguien que NO eres tú los toca, te avisa.
    Equivalente a dejar una moneda marcada en tu escritorio.
══════════════════════════════════════════════════════════════════
"""

import os
import sys
import json
import hashlib
import secrets
import string
import tempfile
import base64
import urllib.request
import ssl
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any

# ── Paths ──────────────────────────────────────────────────────────────────
BAGO_STATE = Path("e:/bago_fw/.bago/state")
CANARY_STATE = BAGO_STATE / "canary_tokens.json"
CANARY_LOG = BAGO_STATE / "canary_log.jsonl"

BAIT_ROOTS = [Path("e:/.bago"), Path("e:/bago_fw"), Path("e:/tmp")]

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@dataclass
class BaitFile:
    path: str
    kind: str           # aws_keys | openai_api | github_pat | telegram | google_api | web_bug
    display_name: str   # nombre para listados
    content_sha256: str   # hash del contenido ORIGINAL
    size: int
    mtime_at_deploy: float
    ctime_at_deploy: float
    created_at: str
    note: str
    url_bug: str = ""      # si es web_bug, la URL a vigilar
    visits_detected: int = 0


# ── Helpers ────────────────────────────────────────────────────────────────
def _now() -> str:
    return datetime.now().isoformat()


def _now_epoch() -> float:
    return datetime.now().timestamp()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_state() -> dict:
    if CANARY_STATE.exists():
        return json.loads(CANARY_STATE.read_text(encoding='utf-8'))
    return {"baits": [], "enabled": True}


def save_state(data: dict):
    BAGO_STATE.mkdir(parents=True, exist_ok=True)
    CANARY_STATE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def log_event(level: str, msg: str, detail: dict = None):
    CANARY_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": _now(), "level": level, "msg": msg}
    if detail:
        entry["detail"] = detail
    with open(CANARY_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── Generadores de tokens falsos (realistas) ─────────────────────────────────────────
def _rand_id(n: int, chars: str = string.ascii_uppercase + string.ascii_lowercase + string.digits) -> str:
    return ''.join(secrets.choice(chars) for _ in range(n))


def fake_aws_keys() -> tuple:
    """AccessKeyId + SecretAccessKey realistas (pero falsas)."""
    access = 'AKIA' + _rand_id(16, string.ascii_uppercase + string.digits)
    secret = base64.b64encode(secrets.token_bytes(30)).decode().rstrip('=')
    return access, secret


def fake_openai_key() -> str:
    return 'sk-' + _rand_id(24) + _rand_id(24)


def fake_github_pat() -> str:
    return 'ghp_' + _rand_id(36, string.ascii_letters + string.digits)


def fake_telegram_token() -> str:
    return str(secrets.randbelow(9000000000) + 1000000000) + ':' + _rand_id(35)


def fake_google_api_key() -> str:
    return 'AIzaSy' + _rand_id(33, string.ascii_letters + string.digits + '-_')


def fake_web_bug_url() -> str:
    """Devuelve una URL de webhook.site como bug detector."""
    print("  [canary] Generando web bug via webhook.site ...")
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request('https://webhook.site/token', method='POST')
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            token = data.get('uuid', '')
            if token:
                url = f"https://webhook.site/{token}"
                uniq = f"https://webhook.site/{token}/bago-canary-{secrets.token_hex(4)}"
                return uniq, url
    except Exception as e:
        print(f"  ⚠ webhook.site no disponible: {e}")
    # Fallback: user genera manual
    return "", ""


# ── Writers de archivos señuelo ────────────────────────────────────────────
def write_bait_aws(path: Path):
    key, secret = fake_aws_keys()
    content = f"""AWS_ACCESS_KEY_ID={key}
AWS_SECRET_ACCESS_KEY={secret}
AWS_REGION=us-east-1
S3_BUCKET=bago-backup-{_now()[:10]}
"""
    content_bytes = content.encode('utf-8')
    info = {
        "access_key": key, "secret_key": secret,
        "format": "aws", "note": "Falso — Señuelo BAGO Canary"
    }
    return content_bytes, info


def write_bait_openai(path: Path):
    key = fake_openai_key()
    content = f"""OPENAI_API_KEY={key}
OPENAI_ORG_ID=org-{_rand_id(24)}
"""
    content_bytes = content.encode('utf-8')
    return content_bytes, {"api_key": key, "format": "openai"}


def write_bait_github(path: Path):
    key = fake_github_pat()
    content = f"""GITHUB_TOKEN={key}
GITHUB_USER=bago-dev
"""
    content_bytes = content.encode('utf-8')
    return content_bytes, {"pat": key, "format": "github"}


def write_bait_telegram(path: Path):
    token = fake_telegram_token()
    content = f"""TELEGRAM_BOT_TOKEN={token}
TELEGRAM_CHAT_ID=7752787448
"""
    content_bytes = content.encode('utf-8')
    return content_bytes, {"bot_token": token, "format": "telegram"}


def write_bait_google(path: Path):
    key = fake_google_api_key()
    content = f"""GOOGLE_API_KEY={key}
GOOGLE_CSE_ID=0123456789abcdefghijklmnop
"""
    content_bytes = content.encode('utf-8')
    return content_bytes, {"api_key": key, "format": "google"}


def write_bait_webbug(path: Path, url: str):
    content = f"""{{
  "webhook_url": "{url}",
  "service": "BAGO Notifier",
  "configured_at": "{_now()}",
  "note": "No modificar — configurado por BAGO",
  "health_check": false
}}
"""
    content_bytes = content.encode('utf-8')
    return content_bytes, {"url": url, "format": "web_bug"}


# ── Colocación de señuelos ──────────────────────────────────────────────────
def pick_bait_location() -> Path:
    candidates = [
        Path("e:/.bago/user/aws_credentials.bak.json"),
        Path("e:/.bago/user/credentials_old.json"),
        Path("e:/.bago/state/backup_tokens.env"),
        Path("e:/bago_fw/.bago/.env.backup"),
        Path("e:/bago_fw/.bago/remote_config.json"),
        Path("e:/tmp/bago/session_export.json"),
        Path("e:/bago_projects/legacy_config.json"),
        Path("e:/bago_fw_backup_3.4.6/.bago/aws_credentials.json"),
        Path("e:/bago_fw.backup.20260521-194300/projects/.aws/credentials"),
        Path("e:/tmp/bago/secrets.json"),
    ]
    for c in candidates:
        if not c.exists():
            c.parent.mkdir(parents=True, exist_ok=True)
            return c
    # Fallback
    f = Path(tempfile.mktemp(suffix="_config.json", dir="e:/tmp"))
    return f


def deploy_bait(kind: str) -> Optional[BaitFile]:
    path = pick_bait_location()
    url_bug = ""

    writers = {
        "aws_keys": write_bait_aws,
        "openai_api": write_bait_openai,
        "github_pat": write_bait_github,
        "telegram_bot": write_bait_telegram,
        "google_api": write_bait_google,
        "web_bug": write_bait_webbug,
    }

    if kind not in writers:
        print(f"  ❌ Tipo '{kind}' no soportado: {list(writers.keys())}")
        return None

    if kind == "web_bug":
        uniq, base = fake_web_bug_url()
        if not uniq:
            print("  ⚠ No se pudo generar web bug via webhook.site")
            print("  💡 Genera manualmente en https://webhook.site")
            print("     Luego: python bago_canary.py manual web_bug \u003curl\u003e \u003cfile\u003e")
            return None
        content_bytes, meta = writers[kind](path, uniq)
        url_bug = base
    else:
        content_bytes, meta = writers[kind](path)

    path.write_bytes(content_bytes)
    stats = path.stat()

    bait = BaitFile(
        path=str(path),
        kind=kind,
        display_name=path.name,
        content_sha256=_sha256(content_bytes),
        size=len(content_bytes),
        mtime_at_deploy=stats.st_mtime,
        ctime_at_deploy=stats.st_ctime,
        created_at=_now(),
        note=json.dumps(meta),
        url_bug=url_bug,
        visits_detected=0,
    )

    log_event("INFO", f"Bait desplegado: {path}", {"kind": kind, "sha256": bait.content_sha256})
    return bait


# ── Revisión de integridad local ────────────────────────────────────────────
def check_local_integrity(state: dict) -> List[Dict[str, Any]]:
    """Revisa si los archivos bait han sido leídos (atime mod), modificados o eliminados."""
    anomalies = []
    now = datetime.now()
    now_epoch = now.timestamp()

    for raw in state.get("baits", []):
        bait = BaitFile(**raw)
        p = Path(bait.path)

        if not p.exists():
            anomalies.append({
                "ts": _now(), "severity": "CRITICAL",
                "kind": "FILE_DELETED",
                "file": str(p), "bait_kind": bait.kind,
                "message": "🚨 ALERTA: El archivo señuelo ha sido ELIMINADO"
            })
            log_event("ALERT", f"Archivo señuelo ELIMINADO: {p}", {"kind": bait.kind})
            continue

        stats = p.stat()
        current_hash = _sha256(p.read_bytes())

        # Verificar si se modificó el contenido
        if current_hash != bait.content_sha256:
            anomalies.append({
                "ts": _now(), "severity": "CRITICAL",
                "kind": "FILE_MODIFIED",
                "file": str(p), "bait_kind": bait.kind,
                "message": "🚨 ALERTA: El archivo señuelo ha sido MODIFICADO"
            })
            log_event("ALERT", f"Archivo señuelo MODIFICADO: {p}", {"kind": bait.kind})
            # Actualizar hash para no repetir alertas en bucle
            raw["content_sha256"] = current_hash
            continue

        # Verificar si se leyó recientemente (atime móvil desde deploy)
        # En Windows, el atime no siempre es fiable, pero si lo es, útil
        if stats.st_atime > bait.ctime_at_deploy + 5:
            # Solo alertar si hace más de 5min del deploy y no habíamos visto este atime antes
            last_alerted_atime = raw.get("last_alerted_atime", 0)
            if stats.st_atime > last_alerted_atime:
                anomalies.append({
                    "ts": _now(), "severity": "HIGH",
                    "kind": "FILE_READ",
                    "file": str(p), "bait_kind": bait.kind,
                    "message": "🚨 ALERTA: El archivo señuelo ha sido LEÍDO"
                })
                log_event("ALERT", f"Archivo señuelo LEÍDO: {p}", {"kind": bait.kind})
                raw["last_alerted_atime"] = stats.st_atime
            continue

    return anomalies


# ── Revisión de web bug remoto ──────────────────────────────────────────────
def check_webbug_visits(state: dict) -> List[Dict[str, Any]]:
    """Revisa si alguien visitó las URLs de webhook.site."""
    alerts = []
    for raw in state.get("baits", []):
        if raw.get("kind") != "web_bug" or not raw.get("url_bug"):
            continue
        base = raw["url_bug"]
        # Ejemplo: https://webhook.site/UUID/    → GET /token/UUID/requests
        parts = base.rstrip('/').split('/')
        if len(parts) < 4:
            continue
        token = parts[3]
        try:
            ctx = ssl.create_default_context()
            req = urllib.request.Request(f'https://webhook.site/token/{token}/requests')
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                reqs = data.get('data', data if isinstance(data, list) else [])
                if not isinstance(reqs, list):
                    reqs = []
                if len(reqs) > raw.get("visits_detected", 0):
                    new_visits = reqs[raw.get("visits_detected", 0):]
                    for v in new_visits:
                        alert = {
                            "ts": _now(), "severity": "CRITICAL",
                            "kind": "WEB_BUG_TRIGGERED",
                            "file": raw.get("path", "n/a"),
                            "bait_kind": "web_bug",
                            "source_ip": v.get("ip") or v.get("request.remote_ip", "?"),
                            "user_agent": v.get("user_agent") or v.get("request.headers.user-agent", "?"),
                            "method": v.get("method", "?"),
                            "requested_at": v.get("created_at", v.get("timestamp", "?")),
                        }
                        alerts.append(alert)
                        raw["visits_detected"] = raw.get("visits_detected", 0) + 1
                        log_event("ALERT", f"🚨 WEB BUG ACTIVADO: {raw['path']}", alert)
        except Exception as e:
            print(f"  ⚠ No se pudo consultar webhook.site: {e}")

    return alerts


# ── CLI ───────────────────────────────────────────────────────────────────────
def cmd_deploy(args: list):
    kind = "aws_keys"
    if "--type" in args:
        idx = args.index("--type")
        if idx + 1 < len(args):
            kind = args[idx + 1]

    state = load_state()

    print("══════════════════════════════════════════════════════════════")
    print("  🔐 BAGO CANARY DEPLOY — Trampas éticas de detección")
    print("══════════════════════════════════════════════════════════════\n")

    bait = deploy_bait(kind)
    if not bait:
        print("\n  ❌ No se pudo desplegar el señuelo.\n")
        return

    state.setdefault("baits", []).append(asdict(bait))
    save_state(state)

    print(f"  ✅ Señuelo desplegado:")
    print(f"     Tipo:   {bait.kind}")
    print(f"     Archivo: {bait.path}")
    print(f"     Tamaño: {bait.size} bytes")
    print(f"     SHA256: {bait.content_sha256[:16]}...")
    if bait.url_bug:
        print(f"     WebBug:  {bait.url_bug}")
    print(f"\n  ⏰ Revisa con: python bago_canary.py check")
    print("══════════════════════════════════════════════════════════════\n")


def cmd_check():
    state = load_state()
    if not state.get("baits"):
        print("  ℹ No hay señuelos. Ejecuta: python bago_canary.py deploy")
        return

    print("══════════════════════════════════════════════════════════════")
    print("  🔍 BAGO CANARY CHECK — Revisando alertas ...")
    print("══════════════════════════════════════════════════════════════\n")

    # Check local: integridad de archivos
    local_alerts = check_local_integrity(state)
    # Check remoto: web bugs
    web_alerts = check_webbug_visits(state)

    all_events = local_alerts + web_alerts

    if not all_events:
        print("  ✅ Ningún evento. Los señuelos están intactos.\n")
        for raw in state.get("baits", []):
            status = "🟢" if Path(raw.get("path", "")).exists() else "🔴 MISSING"
            print(f"    {status} {raw['kind']:14} → {raw.get('display_name', '?')}")
    else:
        print(f"  🚨 {len(all_events)} EVENTOS DETECTADOS\n")
        print("  " + "─" * 62)
        for ev in all_events:
            print(f"\n    ⚠️  [{ev.get('severity','HIGH')}] {ev.get('kind','ALERTA')}")
            print(f"       Archivo: {ev.get('file','?')}")
            print(f"       {ev.get('message','')}")
            if 'source_ip' in ev:
                print(f"       IP origen:  {ev['source_ip']}")
                print(f"       User-Agent: {ev.get('user_agent','?')}")
                print(f"       Método:     {ev.get('method','?')}")
                print(f"       Timestamp:  {ev.get('requested_at', ev.get('ts','?'))}")
            print()
        print("  " + "─" * 62)

    save_state(state)
    print(f"  📝 Log completo: {CANARY_LOG}")
    print("══════════════════════════════════════════════════════════════\n")


def cmd_list():
    state = load_state()
    print("══════════════════════════════════════════════════════════════")
    print("  📋 BAGO CANARY — Señuelos activos")
    print("══════════════════════════════════════════════════════════════\n")
    if not state.get("baits"):
        print("  ℹ No hay señuelos activos.\n")
        return
    for raw in state["baits"]:
        status = "🟢" if Path(raw.get("path", "")).exists() else "🔴 MISSING"
        print(f"  {status} {raw['kind']:14} {raw.get('display_name','?')}")
        print(f"     Path:  {raw.get('path','n/a')}")
        note = json.loads(raw.get("note","{}"))
        for k,v in note.items():
            if k != "format":
                print(f"     {k}: {v[:40]}...")
        if raw.get("url_bug"):
            print(f"     URL:   {raw['url_bug']}")
        if raw.get("visits_detected"):
            print(f"     Visitas detectadas: {raw['visits_detected']}")
        print()
    print("══════════════════════════════════════════════════════════════\n")


def cmd_purge():
    state = load_state()
    print("══════════════════════════════════════════════════════════════")
    print("  🗑️ BAGO CANARY PURGE")
    print("══════════════════════════════════════════════════════════════\n")
    for raw in state.get("baits", []):
        p = Path(raw.get("path", ""))
        if p.exists():
            p.unlink()
            print(f"  ✅ Eliminado: {p}")
    state["baits"] = []
    save_state(state)
    print(f"\n  📝 Estado purgado. Log conservado.\n")
    print("══════════════════════════════════════════════════════════════\n")


def main():
    import argparse
    ap = argparse.ArgumentParser(description="BAGO Canary — Trampas éticas LOCALES")
    ap.add_argument("command", choices=["deploy", "check", "list", "purge"])
    ap.add_argument("--type", default="aws_keys", help="aws_keys|openai_api|github_pat|telegram_bot|google_api|web_bug")
    args = ap.parse_args()

    BAGO_STATE.mkdir(parents=True, exist_ok=True)

    if args.command == "deploy":
        cmd_deploy(["--type", args.type])
    elif args.command == "check":
        cmd_check()
    elif args.command == "list":
        cmd_list()
    elif args.command == "purge":
        cmd_purge()


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        print("\n  🛑 Cancelado")
        sys.exit(130)
