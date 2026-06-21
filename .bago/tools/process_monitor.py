"""
BAGO Process Monitor — monitor HTML en tiempo real de todos los procesos internos.

Observa .bago/state/ y genera/sirve un monitor.html con auto-refresh.

CLI:
  python process_monitor.py [--root DIR] [--port N] [--test]
  python process_monitor.py serve [--port N] [--root DIR]
  python process_monitor.py generate [--root DIR] [--out PATH]

Integrado como:
  bago monitor [serve|generate] [--port N] [--root DIR]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import threading
import http.server
import socketserver
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── portabilidad ──────────────────────────────────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))
try:
    from bago_utils import get_scan_root, timestamp_iso
except ImportError:
    def get_scan_root(override=None):
        return Path(override) if override else Path(os.environ.get("BAGO_SCAN_ROOT", os.getcwd()))
    def timestamp_iso():
        return datetime.now(timezone.utc).isoformat()

MONITOR_VERSION = "1.0.0"


# ══════════════════════════════════════════════════════════════════════════════
#  COLECTORES DE ESTADO
# ══════════════════════════════════════════════════════════════════════════════

def _safe_json(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _safe_jsonl(path: Path, limit: int = 20) -> list[dict]:
    lines = []
    try:
        raw = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in reversed(raw[-limit:]):
            line = line.strip()
            if line:
                try:
                    lines.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        pass
    return lines


def collect_llm_state(state_dir: Path) -> dict:
    data = _safe_json(state_dir / "llm_start.json") or {}
    return {
        "provider": data.get("provider", "—"),
        "model": data.get("model", "—"),
        "mode": data.get("mode", "—"),
        "started_at": data.get("started_at", "—"),
    }


def collect_sessions(state_dir: Path, limit: int = 8) -> list[dict]:
    sessions_dir = state_dir / "sessions"
    result = []
    if not sessions_dir.exists():
        return result
    for entry in sorted(sessions_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        meta_file = entry / "meta.json" if entry.is_dir() else entry
        meta = _safe_json(meta_file) or {}
        if not meta and entry.suffix == ".json":
            meta = _safe_json(entry) or {}
        if meta:
            ts_raw = meta.get("created_at") or meta.get("started_at") or ""
            result.append({
                "id": str(meta.get("session_id", entry.name))[:12],
                "provider": meta.get("provider", "—"),
                "model": meta.get("model", "—"),
                "turns": meta.get("turn_count", meta.get("turns", "?")),
                "started": str(ts_raw)[:19] if ts_raw else "—",
                "status": meta.get("status", "closed"),
            })
    return result


def collect_orchestrator(state_dir: Path) -> list[dict]:
    orc_dir = state_dir / "orchestrator"
    if not orc_dir.exists():
        return []
    briefs = []
    for f in sorted(orc_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]:
        data = _safe_json(f) or {}
        brief = data.get("brief", data)
        briefs.append({
            "id": brief.get("brief_id", f.stem)[:16],
            "task": (brief.get("task_description", brief.get("task", "—")))[:60],
            "domain": brief.get("domain", "—"),
            "priority": brief.get("priority", "—"),
            "status": brief.get("status", "—"),
            "assigned_to": brief.get("assigned_to", "—"),
            "phase": data.get("current_phase", "—"),
            "created_at": brief.get("created_at", "—")[:19] if brief.get("created_at") else "—",
        })
    return briefs


def collect_rl_rewards(state_dir: Path, limit: int = 5) -> list[dict]:
    rewards_file = state_dir / "rl" / "rewards.jsonl"
    entries = _safe_jsonl(rewards_file, limit)
    result = []
    for e in entries:
        result.append({
            "action": e.get("action", "—"),
            "reward": e.get("reward", "?"),
            "ts": str(e.get("timestamp", e.get("ts", "—")))[:19],
        })
    return result


def collect_rl_policy(state_dir: Path) -> dict:
    policy_file = state_dir / "rl_policies" / "bc_policy.json"
    data = _safe_json(policy_file) or {}
    return {
        "type": data.get("type", "—"),
        "n_actions": data.get("n_actions", "—"),
        "trained_at": str(data.get("trained_at", "—"))[:19],
        "accuracy": data.get("accuracy", "—"),
    }


def collect_agents(state_dir: Path) -> list[dict]:
    agents_dir = state_dir / "agents"
    if not agents_dir.exists():
        return []
    agents = []
    for f in sorted(agents_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:8]:
        data = _safe_json(f) or {}
        agents.append({
            "id": data.get("agent_id", f.stem)[:16],
            "phase": data.get("current_phase", data.get("phase", "—")),
            "skills": ", ".join(data.get("skills", [])) or "—",
            "status": data.get("status", "—"),
            "updated": data.get("updated_at", "—")[:19] if data.get("updated_at") else "—",
        })
    return agents


def collect_toolsmith(state_dir: Path) -> list[dict]:
    ts_dir = state_dir / "toolboxes"
    if not ts_dir.exists():
        return []
    tools = []
    for f in sorted(ts_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:8]:
        data = _safe_json(f) or {}
        tools.append({
            "name": data.get("name", f.stem),
            "status": data.get("status", "—"),
            "category": data.get("category", "—"),
            "sprint": data.get("sprint", "—"),
            "updated": data.get("updated_at", "—")[:19] if data.get("updated_at") else "—",
        })
    return tools


def collect_shadow(state_dir: Path) -> dict:
    data = _safe_json(state_dir / "ui_control_shadow.json") or {}
    return {
        "mode": data.get("mode", "—"),
        "last_command": data.get("last_command", "—"),
        "ts": str(data.get("timestamp", "—"))[:19],
    }


def collect_all(root: Path) -> dict:
    override = os.environ.get("BAGO_STATE_ROOT", "").strip()
    state_dir = Path(override).expanduser().resolve() if override else root / ".bago" / "state"
    now = datetime.now(timezone.utc).isoformat()
    return {
        "generated_at": now,
        "root": str(root),
        "llm": collect_llm_state(state_dir),
        "sessions": collect_sessions(state_dir),
        "orchestrator": collect_orchestrator(state_dir),
        "rl_rewards": collect_rl_rewards(state_dir),
        "rl_policy": collect_rl_policy(state_dir),
        "agents": collect_agents(state_dir),
        "toolsmith": collect_toolsmith(state_dir),
        "shadow": collect_shadow(state_dir),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  GENERADOR HTML
# ══════════════════════════════════════════════════════════════════════════════

_STATUS_COLORS = {
    "open": "#f0a500", "in_progress": "#3b9ddd", "pending": "#aaaaaa",
    "done": "#4caf50", "closed": "#888888", "active": "#4caf50",
    "failed": "#e74c3c", "error": "#e74c3c", "running": "#3b9ddd",
    "idle": "#aaaaaa", "dry-run": "#9b59b6", "chat": "#4caf50",
    "—": "#555555",
}

def _badge(text: str) -> str:
    color = _STATUS_COLORS.get(str(text).lower(), "#555555")
    return (f'<span style="background:{color};color:#fff;padding:2px 8px;'
            f'border-radius:4px;font-size:0.78em;font-weight:600;">{text}</span>')


def _card(title: str, icon: str, body: str) -> str:
    return f"""
<div class="card">
  <div class="card-header">{icon} {title}</div>
  <div class="card-body">{body}</div>
</div>"""


def _table(headers: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{h}</th>" for h in headers)
    body_rows = ""
    for row in rows:
        tds = "".join(f"<td>{cell}</td>" for cell in row)
        body_rows += f"<tr>{tds}</tr>"
    if not rows:
        body_rows = f'<tr><td colspan="{len(headers)}" style="color:#666;text-align:center;">— sin datos —</td></tr>'
    return f"<table><thead><tr>{th}</tr></thead><tbody>{body_rows}</tbody></table>"


def _kv(data: dict) -> str:
    rows = ""
    for k, v in data.items():
        rows += f'<div class="kv-row"><span class="kv-key">{k}</span><span class="kv-val">{v}</span></div>'
    return f'<div class="kv">{rows}</div>'


def generate_html(snapshot: dict, refresh: int = 5, live_port: int = 0) -> str:
    llm = snapshot["llm"]
    sessions = snapshot["sessions"]
    orchestrator = snapshot["orchestrator"]
    rl_rewards = snapshot["rl_rewards"]
    rl_policy = snapshot["rl_policy"]
    agents = snapshot["agents"]
    toolsmith_items = snapshot["toolsmith"]
    shadow = snapshot["shadow"]
    ts = snapshot["generated_at"][:19].replace("T", " ") + " UTC"
    root = snapshot["root"]

    # Auto-refresh via JS fetch para live mode, o meta refresh para static
    if live_port > 0:
        refresh_script = f"""
<script>
  (function poll() {{
    setTimeout(function() {{
      fetch('/snapshot')
        .then(r => r.json())
        .then(data => {{
          document.getElementById('ts').textContent = data.generated_at.slice(0,19).replace('T',' ') + ' UTC';
          // reload page for simplicity
          location.reload();
        }})
        .catch(() => setTimeout(poll, {refresh * 1000}));
    }}, {refresh * 1000});
  }})();
</script>"""
    else:
        refresh_script = f'<meta http-equiv="refresh" content="{refresh}">'

    # ── Cards ──────────────────────────────────────────────────────────────
    llm_body = _kv({
        "Provider": llm["provider"],
        "Modelo": llm["model"],
        "Modo": _badge(llm["mode"]),
        "Iniciado": llm["started_at"][:19] if llm["started_at"] != "—" else "—",
    })
    card_llm = _card("LLM Session", "🤖", llm_body)

    card_shadow = _card("RL Shadow", "👁", _kv({
        "Modo": shadow["mode"],
        "Último cmd": shadow["last_command"],
        "Timestamp": shadow["ts"],
    }))

    card_policy = _card("RL Policy (BC)", "📊", _kv({
        "Tipo": rl_policy["type"],
        "Acciones": str(rl_policy["n_actions"]),
        "Entrenado": rl_policy["trained_at"],
        "Accuracy": str(rl_policy["accuracy"]),
    }))

    # Sessiones
    sess_rows = []
    for s in sessions:
        sess_rows.append([
            f'<code>{s["id"]}</code>',
            s["provider"], s["model"],
            str(s["turns"]),
            s["started"],
            _badge(s["status"]),
        ])
    card_sessions = _card("Sesiones recientes", "💬",
        _table(["ID", "Provider", "Modelo", "Turnos", "Inicio", "Estado"], sess_rows))

    # Orchestrator
    orc_rows = []
    for b in orchestrator:
        orc_rows.append([
            f'<code>{b["id"]}</code>',
            b["task"],
            b["domain"],
            _badge(b["priority"]),
            _badge(b["status"]),
            b["phase"],
            b["created_at"],
        ])
    card_orc = _card("Orchestrator v4 — Task Briefs", "🎯",
        _table(["ID", "Tarea", "Dominio", "Prioridad", "Estado", "Fase", "Creado"], orc_rows))

    # Agents
    agent_rows = []
    for a in agents:
        agent_rows.append([
            f'<code>{a["id"]}</code>',
            a["phase"], a["skills"],
            _badge(a["status"]), a["updated"],
        ])
    card_agents = _card("Spiral Agents", "🌀",
        _table(["ID", "Fase", "Skills", "Estado", "Actualizado"], agent_rows))

    # Toolsmith
    ts_rows = []
    for t in toolsmith_items:
        ts_rows.append([t["name"], t["category"], t["sprint"],
                         _badge(t["status"]), t["updated"]])
    card_toolsmith = _card("Toolsmith", "🔧",
        _table(["Herramienta", "Categoría", "Sprint", "Estado", "Actualizado"], ts_rows))

    # RL Rewards
    rl_rows = []
    for r in rl_rewards:
        reward_val = r["reward"]
        color = "#4caf50" if isinstance(reward_val, (int, float)) and reward_val > 0 else "#e74c3c" if isinstance(reward_val, (int, float)) and reward_val < 0 else "#aaa"
        rl_rows.append([
            r["action"],
            f'<span style="color:{color};font-weight:600">{reward_val}</span>',
            r["ts"],
        ])
    card_rl = _card("RL Rewards recientes", "📈",
        _table(["Acción", "Reward", "Timestamp"], rl_rows))

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BAGO Process Monitor</title>
{refresh_script}
<style>
  :root {{
    --bg: #0d1117; --surface: #161b22; --border: #30363d;
    --text: #c9d1d9; --text-dim: #8b949e; --accent: #58a6ff;
    --green: #3fb950; --orange: #d29922; --red: #f85149;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Cascadia Code','Consolas',monospace; font-size: 13px; }}
  header {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 12px 24px; display: flex; align-items: center; justify-content: space-between; }}
  header h1 {{ font-size: 1.1em; color: var(--accent); letter-spacing: 0.05em; }}
  header .meta {{ color: var(--text-dim); font-size: 0.85em; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; padding: 16px; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }}
  .card-header {{ background: #1c2128; padding: 8px 14px; font-weight: 700; font-size: 0.9em; color: var(--accent); border-bottom: 1px solid var(--border); }}
  .card-body {{ padding: 12px 14px; overflow-x: auto; }}
  .card-wide {{ grid-column: 1 / -1; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85em; }}
  th {{ text-align: left; color: var(--text-dim); padding: 4px 8px; border-bottom: 1px solid var(--border); font-weight: 600; }}
  td {{ padding: 5px 8px; border-bottom: 1px solid #21262d; vertical-align: top; }}
  tr:last-child td {{ border-bottom: none; }}
  code {{ background: #21262d; padding: 1px 5px; border-radius: 3px; font-size: 0.9em; color: #79c0ff; }}
  .kv {{ display: flex; flex-direction: column; gap: 5px; }}
  .kv-row {{ display: flex; justify-content: space-between; gap: 8px; align-items: center; }}
  .kv-key {{ color: var(--text-dim); flex-shrink: 0; }}
  .kv-val {{ text-align: right; }}
  .root-badge {{ background: #21262d; border: 1px solid var(--border); border-radius: 4px; padding: 2px 8px; color: var(--text-dim); font-size: 0.8em; }}
  .pulse {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--green); animation: pulse 2s infinite; }}
  @keyframes pulse {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:0.3; }} }}
</style>
</head>
<body>
<header>
  <h1>⚡ BAGO Process Monitor <span style="color:#8b949e;font-weight:400;">v{MONITOR_VERSION}</span></h1>
  <div class="meta">
    <span class="pulse"></span>&nbsp;
    <span id="ts">{ts}</span>&nbsp;&nbsp;
    <span class="root-badge">{root}</span>
  </div>
</header>
<div class="grid">
  {card_llm}
  {card_shadow}
  {card_policy}
  <div class="card card-wide">{card_sessions}</div>
  <div class="card card-wide">{card_orc}</div>
  {card_agents}
  {card_toolsmith}
  {card_rl}
</div>
<footer style="text-align:center;padding:16px;color:var(--text-dim);font-size:0.8em;">
  BAGO v4.1.5 — Process Monitor — auto-refresh cada {refresh}s
</footer>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════════════
#  SERVIDOR HTTP LIVE
# ══════════════════════════════════════════════════════════════════════════════

def _make_handler(root: Path, refresh: int, port: int):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # silenciar logs

        def do_GET(self):
            if self.path == "/snapshot":
                data = collect_all(root)
                body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                snapshot = collect_all(root)
                html = generate_html(snapshot, refresh=refresh, live_port=port)
                body = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
    return Handler


def serve(root: Path, port: int = 7890, refresh: int = 5, silent: bool = False) -> None:
    Handler = _make_handler(root, refresh, port)
    with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
        httpd.allow_reuse_address = True
        url = f"http://127.0.0.1:{port}/"
        if not silent:
            print(f"[BAGO Monitor] Sirviendo en {url}")
            print(f"[BAGO Monitor] Raíz observada: {root}")
            print(f"[BAGO Monitor] Auto-refresh: {refresh}s")
            print("[BAGO Monitor] Ctrl+C para parar")
        try:
            if not silent:
                # Intentar abrir navegador
                import webbrowser
                threading.Timer(0.8, lambda: webbrowser.open(url)).start()
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            if not silent:
                print("\n[BAGO Monitor] Detenido.")


# ══════════════════════════════════════════════════════════════════════════════
#  TESTS
# ══════════════════════════════════════════════════════════════════════════════

def _run_tests(root: Path) -> int:
    import tempfile
    tests = []

    def ok(name, cond, detail=""):
        tests.append((name, cond, detail))
        marker = "✓" if cond else "✗"
        print(f"  [{marker}] {name}" + (f" — {detail}" if detail else ""))
        return cond

    print("process_monitor.py self-tests")
    print("─" * 40)

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        state = td / ".bago" / "state"
        state.mkdir(parents=True)

        # T1: collect_all on empty dir
        try:
            snap = collect_all(td)
            ok("collect_all_empty", isinstance(snap, dict), "dict returned")
        except Exception as e:
            ok("collect_all_empty", False, str(e))

        # T2: LLM state
        (state / "llm_start.json").write_text(json.dumps({
            "provider": "ollama-local", "model": "llama3.2:3b",
            "mode": "chat", "started_at": timestamp_iso()
        }), encoding="utf-8")
        llm = collect_llm_state(state)
        ok("llm_provider", llm["provider"] == "ollama-local")
        ok("llm_model", llm["model"] == "llama3.2:3b")

        # T3: Sessions
        sess_dir = state / "sessions" / "abc123"
        sess_dir.mkdir(parents=True)
        (sess_dir / "meta.json").write_text(json.dumps({
            "session_id": "abc123", "provider": "codex",
            "model": "gpt-5.4-mini", "turn_count": 7,
            "created_at": "2025-01-01T12:00:00Z", "status": "closed"
        }), encoding="utf-8")
        sessions = collect_sessions(state)
        ok("sessions_count", len(sessions) >= 1)
        ok("sessions_turns", sessions[0]["turns"] == 7 if sessions else False)

        # T4: Orchestrator
        orc_dir = state / "orchestrator"
        orc_dir.mkdir()
        brief_data = {
            "brief": {
                "brief_id": "BRF-001", "task_description": "Test task",
                "domain": "Backend", "priority": "P1",
                "status": "open", "assigned_to": "Backend Specialist",
                "created_at": "2025-01-01T12:00:00Z",
            },
            "current_phase": "execution"
        }
        (orc_dir / "BRF-001.json").write_text(
            json.dumps(brief_data), encoding="utf-8")
        orc = collect_orchestrator(state)
        ok("orchestrator_count", len(orc) == 1)
        ok("orchestrator_domain", orc[0]["domain"] == "Backend" if orc else False)

        # T5: RL rewards
        rl_dir = state / "rl"
        rl_dir.mkdir()
        rewards = [{"action": "accept", "reward": 1.0, "timestamp": "2025-01-01T12:00:00Z"}]
        (rl_dir / "rewards.jsonl").write_text("\n".join(json.dumps(r) for r in rewards))
        rl = collect_rl_rewards(state)
        ok("rl_rewards", len(rl) == 1)
        ok("rl_reward_val", rl[0]["reward"] == 1.0 if rl else False)

        # T6: HTML generation
        snap = collect_all(td)
        html = generate_html(snap, refresh=5)
        ok("html_generated", "<!DOCTYPE html>" in html)
        ok("html_has_monitor", "BAGO Process Monitor" in html)
        ok("html_has_table", "<table>" in html)
        ok("html_has_card", "card-header" in html)

        # T7: generate_html with live port
        html_live = generate_html(snap, refresh=3, live_port=7890)
        ok("html_live_script", "fetch('/snapshot')" in html_live)

        # T8: snapshot JSON
        ok("snapshot_has_llm", "llm" in snap)
        ok("snapshot_has_sessions", "sessions" in snap)
        ok("snapshot_has_orchestrator", "orchestrator" in snap)

    total = len(tests)
    passed = sum(1 for _, ok_val, _ in tests if ok_val)
    print("─" * 40)
    if passed == total:
        print(f"✓ ALL {total} TESTS PASS")
        return 0
    else:
        print(f"✗ {total - passed}/{total} TESTS FAILED")
        return 1


# ══════════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="process_monitor",
        description="BAGO Process Monitor — genera y sirve monitor HTML en tiempo real"
    )
    parser.add_argument("subcmd", nargs="?", choices=["serve", "generate"],
                        default="serve", help="serve (default) | generate")
    parser.add_argument("--root", default="", help="Raíz del proyecto BAGO (default: cwd/BAGO_SCAN_ROOT)")
    parser.add_argument("--port", type=int, default=7890, help="Puerto HTTP para 'serve' (default: 7890)")
    parser.add_argument("--refresh", type=int, default=5, help="Segundos entre auto-refresh (default: 5)")
    parser.add_argument("--out", default="", help="Ruta de salida para 'generate' (default: .bago/monitor.html)")
    parser.add_argument("--test", action="store_true", help="Ejecuta self-tests")

    args = parser.parse_args(argv)
    root = get_scan_root(args.root or None)

    if args.test:
        return _run_tests(root)

    if args.subcmd == "generate" or args.subcmd is None:
        snapshot = collect_all(root)
        html = generate_html(snapshot, refresh=args.refresh)
        out_path = Path(args.out) if args.out else root / ".bago" / "monitor.html"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8")
        print(f"[BAGO Monitor] Monitor generado: {out_path}")
        return 0

    # serve (default)
    try:
        serve(root, port=args.port, refresh=args.refresh)
    except OSError as e:
        print(f"[BAGO Monitor] Error al iniciar servidor: {e}")
        print(f"[BAGO Monitor] Intenta con otro puerto: --port {args.port + 1}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
