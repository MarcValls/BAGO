#!/usr/bin/env python3
"""
bago_miniapp_server.py — BAGO Mini App Server v2
Sirve la Mini App con API completa: estado, chat, tareas, git, notas.
"""

import json
import os
import re
import subprocess
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from datetime import datetime
import urllib.parse

BAGO_ROOT    = Path(os.environ.get("BAGO_PADRE_PATH") or Path(__file__).parent.parent.parent)
STATE_PATH   = BAGO_ROOT / ".bago/state/global_state.json"
TAREAS_PATH  = BAGO_ROOT / ".bago/state/tareas_telegram.json"
CHAT_PATH    = BAGO_ROOT / ".bago/state/chat_history.json"
MINIAPP_DIR  = Path(__file__).parent / "miniapp"

# ── Helpers ───────────────────────────────────────────────────────────────────
def read_state() -> dict:
    try: return json.loads(STATE_PATH.read_text())
    except Exception as e: return {"error": str(e)}

def write_state(data: dict):
    STATE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))

def load_tareas() -> list:
    if not TAREAS_PATH.exists(): return []
    try: return json.loads(TAREAS_PATH.read_text())
    except: return []

def save_tareas(t: list):
    TAREAS_PATH.write_text(json.dumps(t, indent=2, ensure_ascii=False))

def load_chat() -> list:
    if not CHAT_PATH.exists(): return []
    try: return json.loads(CHAT_PATH.read_text())
    except: return []

def save_chat(msgs: list):
    CHAT_PATH.write_text(json.dumps(msgs[-120:], indent=2, ensure_ascii=False))

def run_git(args_list: list, timeout=10) -> str:
    try:
        r = subprocess.run(["git", "-C", str(BAGO_ROOT)] + args_list,
                           capture_output=True, text=True, timeout=timeout)
        return (r.stdout or r.stderr or "").strip()
    except Exception as e: return f"Error: {e}"

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mABCDEFGHJKSTfnsuhl]")

def run_bago_cmd(cmd: str, timeout: int = 30) -> str:
    """Ejecuta `python3 <BAGO_ROOT>/bago <cmd>` y retorna stdout limpio."""
    try:
        r = subprocess.run(
            ["python3", str(BAGO_ROOT / "bago"), cmd],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(BAGO_ROOT), stdin=subprocess.DEVNULL
        )
        out = (r.stdout + ("\n" + r.stderr if r.stderr.strip() else "")).strip()
        return ANSI_RE.sub("", out) or "(sin salida)"
    except subprocess.TimeoutExpired:
        return f"⏱ Timeout ({timeout}s) — comando demasiado lento"
    except Exception as e:
        return f"❌ Error: {e}"

def run_reparar() -> str:
    """Auto-repara KOs del health — versión servidor."""
    vp_path = BAGO_ROOT / ".bago" / "tools" / "validate_pack.py"
    health_before = run_bago_cmd("health", 30)
    if "100/100" in health_before:
        return f"✅ Sistema sano — nada que reparar\n\n{health_before}"
    fixes = []
    vp_text = vp_path.read_text(encoding="utf-8")
    if '"ImageStudio/"' not in vp_text:
        vp_text = vp_text.replace(
            '"docs/V2_PROPUESTA.md",\n]',
            '"docs/V2_PROPUESTA.md",\n    "ImageStudio/",\n    "tools/dist/",\n]'
        )
        vp_path.write_text(vp_text, encoding="utf-8")
        fixes.append("✔ validate_pack: excluidos directorios de terceros")
    health_after = run_bago_cmd("health", 30)
    result = "🔧 REPARAR\n" + "─"*40 + "\n"
    if fixes:
        result += "Reparaciones:\n" + "\n".join(fixes) + "\n\n"
    else:
        result += "No se encontraron reparaciones automáticas disponibles.\n\n"
    result += health_after
    return result

# ── Motor de chat BAGO ────────────────────────────────────────────────────────
def bago_responder(texto: str) -> str:
    """Interpreta el mensaje del usuario y devuelve respuesta con datos reales."""
    tl = texto.lower().strip()
    state = read_state()

    # ── Estado / health ──────────────────────────────────────────────────────
    if re.search(r"\b(estado|status|health|salud|como estas|cómo estás|hola|hi|hello)\b", tl):
        v  = state.get("bago_version", "?")
        h  = state.get("system_health", "?")
        wf = state.get("sprint_status", {}).get("active_workflow", {})
        t  = [x for x in load_tareas() if x["status"] == "pendiente"]
        return (
            f"🤖 **BAGO v{v}** — Sistema operativo\n\n"
            f"⚕️ Health: `{h}`\n"
            f"⚡ Workflow activo: **{wf.get('code','?')}** — {wf.get('title','sin título')}\n"
            f"📋 Tareas pendientes: **{len(t)}**\n\n"
            f"¿Qué necesitas?"
        )

    # ── Sprint / workflow ────────────────────────────────────────────────────
    elif re.search(r"\b(sprint|workflow|wf|proyecto activo)\b", tl):
        sp   = state.get("sprint_status", {})
        wf   = sp.get("active_workflow", {})
        last = sp.get("last_completed_workflow", {})
        return (
            f"⚡ **Workflow activo**\n\n"
            f"Código: `{wf.get('code','?')}`\n"
            f"Título: {wf.get('title','?')}\n"
            f"Inicio: `{str(wf.get('started','?'))[:16]}`\n\n"
            f"✅ Último completado: _{last.get('title','?')}_"
        )

    # ── Tareas ───────────────────────────────────────────────────────────────
    elif re.search(r"\b(tareas|tasks|pendientes|qué tengo|que tengo)\b", tl):
        tareas = [t for t in load_tareas() if t["status"] == "pendiente"]
        if not tareas:
            return "📋 No hay tareas pendientes. ¡Todo al día! 🎉\n\nPuedes crear una con:\n`tarea: descripción de la tarea`"
        lineas = [f"📋 **{len(tareas)} tarea(s) pendiente(s)**\n"]
        for t in tareas[:10]:
            proj = f"[{t['proyecto'].upper()}] " if t['proyecto'] != 'general' else ""
            lineas.append(f"• `{t['id']}` {proj}{t['titulo']}")
        return "\n".join(lineas)

    # ── Crear tarea ──────────────────────────────────────────────────────────
    elif re.search(r"^(tarea|task|crear tarea|nueva tarea|añadir tarea|add task)[:\s]", tl):
        m = re.sub(r"^(tarea|task|crear tarea|nueva tarea|añadir tarea|add task)\s*:?\s*", "", texto, flags=re.I).strip()
        if not m:
            return "📝 Dime qué tarea crear:\n`tarea: descripción de la tarea`"
        proyecto = "general"
        titulo = m
        if ":" in m and len(m.split(":")[0]) < 20:
            p, t = m.split(":", 1)
            proyecto = p.strip().lower()
            titulo = t.strip()
        tareas = load_tareas()
        nueva = {
            "id": f"tg-{len(tareas)+1:03d}",
            "titulo": titulo,
            "proyecto": proyecto,
            "status": "pendiente",
            "created_at": datetime.now().isoformat(),
            "completado_at": None
        }
        tareas.append(nueva)
        save_tareas(tareas)
        return f"✅ Tarea creada `{nueva['id']}`\n\n**{proyecto.upper()}**: {titulo}"

    # ── Completar tarea ──────────────────────────────────────────────────────
    elif re.search(r"\b(completar|completa|done|hecho|hice|terminé|terminé)\b", tl):
        m = re.search(r"(tg-\d+)", tl)
        if m:
            tid = m.group(1)
            tareas = load_tareas()
            for t in tareas:
                if t["id"] == tid:
                    t["status"] = "hecho"
                    t["completado_at"] = datetime.now().isoformat()
                    save_tareas(tareas)
                    return f"✅ Tarea `{tid}` marcada como completada.\n\n_{t['titulo']}_"
            return f"❌ No encontré la tarea `{tid}`"
        return "¿Qué tarea quieres completar? Dime el ID, ej: `completar tg-001`"

    # ── Git ──────────────────────────────────────────────────────────────────
    elif re.search(r"\b(git|commits?|log|branch|rama|diff)\b", tl):
        branch = run_git(["branch", "--show-current"])
        log    = run_git(["log", "--oneline", "-6"])
        status = run_git(["status", "--short"])
        status_txt = f"\nCambios:\n```\n{status}\n```" if status else "\n_(sin cambios pendientes)_"
        return (
            f"🌿 **Rama:** `{branch}`\n\n"
            f"```\n{log}\n```"
            f"{status_txt}"
        )

    # ── Notas ────────────────────────────────────────────────────────────────
    elif re.search(r"^(nota|note|apunta|recordar|guardar)[:\s]", tl):
        contenido = re.sub(r"^(nota|note|apunta|recordar|guardar)\s*:?\s*", "", texto, flags=re.I).strip()
        if not contenido:
            return "📝 ¿Qué quieres anotar?\n`nota: tu texto aquí`"
        state = read_state()
        ts   = datetime.now().strftime("%Y-%m-%d %H:%M")
        prev = state.get("notes", "")
        state["notes"] = f"{prev}\n{ts} [APP]: {contenido}".strip()
        write_state(state)
        return f"📝 Nota guardada:\n\n_{contenido}_"

    elif re.search(r"\b(notas|mis notas|ver notas)\b", tl):
        notes = state.get("notes", "")
        items = [n for n in notes.split("\n") if n.strip()][-8:]
        if not items:
            return "📝 No hay notas guardadas."
        return "📝 **Notas recientes:**\n\n" + "\n".join(f"• {n}" for n in reversed(items))

    # ── Logs ─────────────────────────────────────────────────────────────────
    elif re.search(r"\b(log|logs|errores?|output)\b", tl):
        lines = []
        for lf in ["/tmp/bago_telegram.log", "/tmp/bago_miniapp.log"]:
            p = Path(lf)
            if p.exists():
                tail = [l for l in p.read_text().splitlines() if "HTTP" not in l][-5:]
                if tail:
                    lines.append(f"**{p.name}**\n```\n" + "\n".join(tail) + "\n```")
        return "\n\n".join(lines) if lines else "📋 Logs vacíos."

    # ── Ayuda ────────────────────────────────────────────────────────────────
    elif re.search(r"\b(ayuda|help|comandos|qué puedes|que puedes|qué haces)\b", tl):
        return (
            "🤖 **Soy BAGO** — tu asistente de desarrollo.\n\n"
            "Puedes hablar conmigo en lenguaje natural:\n\n"
            "📊 **Estado**\n`estado` / `hola` / `cómo estás`\n\n"
            "📋 **Tareas**\n`tareas` — ver pendientes\n"
            "`tarea: descripción` — crear\n"
            "`tarea DERIVA: fix X` — con proyecto\n"
            "`completar tg-001` — marcar hecho\n\n"
            "📁 **Git**\n`git` / `commits` / `rama`\n\n"
            "📝 **Notas**\n`nota: texto` — guardar\n"
            "`notas` — ver recientes\n\n"
            "⚡ **Sprint**\n`sprint` / `workflow`\n\n"
            "📜 **Sistema**\n`logs` / `errores`"
        )

    # ── Respuesta por defecto ─────────────────────────────────────────────────
    else:
        wf = state.get("sprint_status", {}).get("active_workflow", {})
        t  = [x for x in load_tareas() if x["status"] == "pendiente"]
        return (
            f"🤖 Recibido: _{texto[:80]}_\n\n"
            f"Workflow activo: **{wf.get('code','?')}** — {wf.get('title','?')}\n"
            f"Tareas pendientes: **{len(t)}**\n\n"
            f"Escribe `ayuda` para ver qué puedo hacer."
        )


# ── HTTP Handler ──────────────────────────────────────────────────────────────
class BAGOHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silenciar logs HTTP verbosos

    def send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path: Path, ct: str = "text/html"):
        try:
            content = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", f"{ct}; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_response(404); self.end_headers()

    def read_body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        if n == 0: return {}
        try: return json.loads(self.rfile.read(n))
        except: return {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_HEAD(self):
        # Responde 200 sin body para HEAD (algunos clientes/proxies hacen HEAD
        # antes del GET; evita 501 ruidosos en ngrok).
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        if path in ("/", "/index.html"):
            self.send_file(MINIAPP_DIR / "index.html", "text/html")
        elif path in ("/api/state", "/api/estado"):
            self.send_json(read_state())
        elif path == "/api/tareas":
            self.send_json({"tareas": load_tareas()})
        elif path == "/api/chat":
            self.send_json({"history": load_chat()})
        elif path == "/api/git":
            self.send_json({
                "branch": run_git(["branch", "--show-current"]),
                "log":    run_git(["log", "--oneline", "-8"]),
                "status": run_git(["status", "--short"]),
            })
        elif path == "/api/cartera":
            import sys as _sys
            _sys.path.insert(0, str(Path(__file__).parent))
            try:
                from wallet_tracker import portfolio_summary, format_summary, check_alerts
                data = portfolio_summary()
                alerts = check_alerts(data)
                assets = [
                    {
                        "coin":       p["symbol"],
                        "amount":     p["amount"],
                        "price_eur":  p["price"],
                        "value_eur":  p["value"],
                        "change_24h": p.get("change24", 0),
                    }
                    for p in data.get("positions", [])
                ]
                self.send_json({
                    "ok":        True,
                    "summary":   format_summary(data),
                    "assets":    assets,
                    "total_eur": data.get("total", 0),
                    "alerts":    alerts,
                    "ts":        data.get("updated", ""),
                })
            except Exception as e:
                self.send_json({"ok": False, "error": str(e)})
        elif path == "/api/airdrops":
            import sys as _sys
            _sys.path.insert(0, str(Path(__file__).parent))
            try:
                from airdrop_scanner import scan_airdrops, format_airdrops, get_ton_address
                address = get_ton_address()
                if not address:
                    self.send_json({"ok": False, "error": "no_address",
                                    "message": "Configura tu TON address con /airdrop set <ADDRESS>"})
                else:
                    data = scan_airdrops(address)
                    self.send_json({
                        "ok":          True,
                        "address":     address,
                        "ton_balance": data.get("ton_balance", 0),
                        "jettons":     data.get("jettons", []),
                        "nfts":        data.get("nfts", []),
                        "total_usd":   data.get("total_usd", 0),
                        "ts":          data.get("ts", ""),
                        "summary":     format_airdrops(data),
                    })
            except Exception as e:
                self.send_json({"ok": False, "error": str(e)})
        elif path == "/health":
            self.send_json({"ok": True, "service": "bago-miniapp-v2"})

        elif path == "/tonconnect-manifest.json":
            # Sirve manifest con URL dinámica (ngrok / Host header).
            # # COSECHA_TONCONNECT
            try:
                manifest_path = MINIAPP_DIR / "tonconnect-manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                manifest = {"name": "BAGO", "iconUrl": ""}
            host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or ""
            proto = self.headers.get("X-Forwarded-Proto") or ("https" if "ngrok" in host else "http")
            if host:
                manifest["url"] = f"{proto}://{host}"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(manifest, ensure_ascii=False).encode())

        elif path == "/api/wallet/status":
            try:
                from airdrop_scanner import get_ton_address
                addr = get_ton_address()
            except Exception as e:
                self.send_json({"ok": False, "error": str(e)}); return
            self.send_json({"ok": True, "address": addr or None, "connected": bool(addr)})

        elif path == "/api/airdrop/claimable":
            # Lista airdrops reclamables para la address conectada.
            try:
                from airdrop_scanner import get_ton_address
                from airdrop_protocols import scan_claimable, list_protocols
                addr = get_ton_address()
            except Exception as e:
                self.send_json({"ok": False, "error": str(e)}); return
            if not addr:
                self.send_json({"ok": False, "error": "no_wallet",
                                "protocols_known": len(list_protocols())})
                return
            try:
                items = scan_claimable(addr)
            except Exception as e:
                self.send_json({"ok": False, "error": str(e)}); return
            self.send_json({"ok": True, "address": addr,
                            "claimable": items,
                            "protocols_known": len(list_protocols())})

        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        body = self.read_body()

        if path == "/api/chat":
            texto = body.get("texto", "").strip()
            if not texto:
                self.send_json({"error": "vacío"}, 400)
                return
            ts = datetime.now().strftime("%H:%M")
            history = load_chat()
            history.append({"role": "user",  "text": texto, "ts": ts})
            respuesta = bago_responder(texto)
            history.append({"role": "bago",  "text": respuesta, "ts": ts})
            save_chat(history)
            self.send_json({"respuesta": respuesta, "ts": ts})

        elif path == "/api/nota":
            texto = body.get("texto", "").strip()
            if not texto:
                self.send_json({"error": "vacío"}, 400); return
            state = read_state()
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            prev = state.get("notes", "")
            state["notes"] = f"{prev}\n{ts} [APP]: {texto}".strip()
            write_state(state)
            self.send_json({"ok": True})

        elif path == "/api/tarea":
            titulo  = body.get("titulo", "").strip()
            proyecto = body.get("proyecto", "general").strip().lower() or "general"
            if not titulo:
                self.send_json({"error": "sin título"}, 400); return
            tareas = load_tareas()
            nueva  = {
                "id": f"tg-{len(tareas)+1:03d}",
                "titulo": titulo,
                "proyecto": proyecto,
                "status": "pendiente",
                "created_at": datetime.now().isoformat(),
                "completado_at": None
            }
            tareas.append(nueva)
            save_tareas(tareas)
            self.send_json({"ok": True, "tarea": nueva})

        elif path == "/api/tarea/completar":
            tid = body.get("id", "")
            tareas = load_tareas()
            for t in tareas:
                if t["id"] == tid:
                    t["status"] = "hecho"
                    t["completado_at"] = datetime.now().isoformat()
                    save_tareas(tareas)
                    self.send_json({"ok": True}); return
            self.send_json({"error": "no encontrada"}, 404)

        elif path == "/api/tarea/borrar":
            tid = body.get("id", "")
            tareas = load_tareas()
            nuevas = [t for t in tareas if t["id"] != tid]
            save_tareas(nuevas)
            self.send_json({"ok": True})

        elif path == "/api/run":
            cmd = body.get("cmd", "").strip().lower()
            ALLOWED = {"health", "ideas", "next", "doctor", "cosecha", "commit", "sync", "start", "reparar"}
            if cmd not in ALLOWED:
                self.send_json({"error": f"comando no permitido: {cmd}"}, 400)
                return
            if cmd == "start":
                h = run_bago_cmd("health", 30)
                i = run_bago_cmd("ideas", 30)
                output = f"=== bago health ===\n{h}\n\n=== bago ideas ===\n{i}"
            elif cmd == "reparar":
                output = run_reparar()
            else:
                output = run_bago_cmd(cmd, 30)
            self.send_json({"output": output, "cmd": cmd})

        elif path == "/api/cartera/add":
            coin = (body.get("coin") or "").strip().upper()
            try:
                amount = float(body.get("amount"))
            except (TypeError, ValueError):
                self.send_json({"error": "amount inválido"}, 400); return
            if not coin or amount <= 0:
                self.send_json({"error": "coin/amount requeridos"}, 400); return
            try:
                from wallet_tracker import load_config as _lc, save_config as _sc
            except ImportError as e:
                self.send_json({"error": f"wallet_tracker: {e}"}, 500); return
            cfg = _lc()
            cfg.setdefault("wallet", {}).setdefault("holdings", {})[coin] = amount
            _sc(cfg)
            self.send_json({"ok": True, "coin": coin, "amount": amount})

        elif path == "/api/cartera/remove":
            coin = (body.get("coin") or "").strip().upper()
            if not coin:
                self.send_json({"error": "coin requerido"}, 400); return
            try:
                from wallet_tracker import load_config as _lc, save_config as _sc
            except ImportError as e:
                self.send_json({"error": f"wallet_tracker: {e}"}, 500); return
            cfg = _lc()
            holdings = cfg.setdefault("wallet", {}).setdefault("holdings", {})
            existed = coin in holdings
            holdings.pop(coin, None)
            _sc(cfg)
            self.send_json({"ok": True, "coin": coin, "removed": existed})

        elif path == "/api/cartera/alerta":
            coin = (body.get("coin") or "").strip().upper()
            try:
                above = float(body.get("above"))
            except (TypeError, ValueError):
                self.send_json({"error": "above inválido"}, 400); return
            if not coin or above <= 0:
                self.send_json({"error": "coin/above requeridos"}, 400); return
            try:
                from wallet_tracker import load_config as _lc, save_config as _sc
            except ImportError as e:
                self.send_json({"error": f"wallet_tracker: {e}"}, 500); return
            cfg = _lc()
            cfg.setdefault("wallet", {}).setdefault("alerts", []).append({"coin": coin, "above": above})
            _sc(cfg)
            self.send_json({"ok": True, "coin": coin, "above": above})

        elif path == "/api/wallet/connect":
            # Recibe address (y opcionalmente ton_proof) tras TonConnect approve.
            # # COSECHA_TONCONNECT
            address = (body.get("address") or "").strip()
            if not address or len(address) < 40:
                self.send_json({"error": "address inválida"}, 400); return
            try:
                from airdrop_scanner import set_ton_address
                set_ton_address(address)
            except Exception as e:
                self.send_json({"error": f"set_ton_address: {e}"}, 500); return
            # ton_proof verification: TODO (no bloqueante para read-only airdrop scan).
            ton_proof_present = bool(body.get("ton_proof"))
            self.send_json({
                "ok": True,
                "address": address,
                "ton_proof_verified": False,
                "ton_proof_received": ton_proof_present,
                "note": "ton_proof verification pending (read-only address use is safe).",
            })

        elif path == "/api/wallet/disconnect":
            try:
                from wallet_tracker import load_config as _lc, save_config as _sc
            except ImportError as e:
                self.send_json({"error": f"wallet_tracker: {e}"}, 500); return
            cfg = _lc()
            wallet = cfg.setdefault("wallet", {})
            had = wallet.pop("ton_address", None)
            _sc(cfg)
            self.send_json({"ok": True, "was_connected": bool(had)})

        elif path == "/api/airdrop/claim":
            # Construye una Transaction para TonConnect sendTransaction().
            # BAGO NO firma — solo propone. La wallet del usuario firma.
            protocol_id = (body.get("protocol_id") or "").strip()
            if not protocol_id:
                self.send_json({"error": "protocol_id requerido"}, 400); return
            try:
                from airdrop_protocols import get_protocol, build_claim_transaction
                proto = get_protocol(protocol_id)
            except Exception as e:
                self.send_json({"error": f"airdrop_protocols: {e}"}, 500); return
            if not proto:
                self.send_json({"error": f"protocolo no encontrado: {protocol_id}"}, 404); return
            if proto.get("type") != "active":
                self.send_json({"error": "protocolo passive: no requiere claim tx",
                                "type": proto.get("type")}, 400); return
            try:
                tx = build_claim_transaction(proto)
            except Exception as e:
                self.send_json({"error": str(e)}, 500); return
            self.send_json({"ok": True, "transaction": tx,
                            "protocol": {"id": proto["id"],
                                         "name": proto.get("name", proto["id"]),
                                         "info_url": proto.get("info_url")}})

        else:
            self.send_response(404); self.end_headers()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    print(f"[BAGO Mini App v2] http://localhost:{args.port}", flush=True)
    server = HTTPServer(("0.0.0.0", args.port), BAGOHandler)
    try: server.serve_forever()
    except KeyboardInterrupt: print("\nParado.", flush=True)

if __name__ == "__main__":
    main()
