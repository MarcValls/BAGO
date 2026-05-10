#!/usr/bin/env python3
"""
BAGO Launcher — servidor local
Puerto: 7430  |  Dependencias: solo stdlib Python
"""
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

LAUNCHER_DIR     = Path(__file__).parent.resolve()
BAGO_CORE        = LAUNCHER_DIR.parent
STATIC_DIR       = LAUNCHER_DIR / "static"
AGENTS_DIR       = LAUNCHER_DIR / "agents"
STATE_DIR        = BAGO_CORE / ".bago" / "state"
STATE_FILE       = STATE_DIR / "global_state.json"
ROUTING_HISTORY  = STATE_DIR / "routing_history.jsonl"
SESSIONS_DIR     = STATE_DIR / "sessions"
PENDING_TASK     = STATE_DIR / "pending_w2_task.json"
IDEAS_FILE       = STATE_DIR / "implemented_ideas.json"
LLM_CONFIG_FILE  = STATE_DIR / "llm_config.json"
PORT             = 7430

# Keywords that classify a bago command as sensitive (require confirmation)
_SENSITIVE_KW: frozenset[str] = frozenset({
    "install", "deploy", "auto", "autonomous", "reset", "delete",
    "remove", "drop", "db", "migrate", "destroy",
})

TOOLS_DIR = BAGO_CORE / ".bago" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
import agent_router

# Single source of truth: launcher delegates routing and agent detection to
# .bago/tools/agent_router.py, which is also used by `bago route`.
detect_agents = agent_router.detect_agents

def route_task(task: str, agents: list) -> dict:
    return agent_router.route_task(task, agents=agents, record=True)

# ─── BAGO Status ──────────────────────────────────────────────────────────────

def bago_status():
    if not STATE_FILE.exists():
        return {"error": "global_state.json no encontrado"}
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
        # system_health is a string: "ok" / "warning" / "error"
        sys_health = state.get("system_health", state.get("health", "?"))
        if isinstance(sys_health, dict):
            health_score = sys_health.get("score", "?")
        elif sys_health == "ok":
            health_score = 100
        elif sys_health in ("warning", "warn"):
            health_score = 70
        elif sys_health == "error":
            health_score = 30
        else:
            health_score = sys_health
        return {
            "version":      state.get("bago_version", "?"),
            "mode":         state.get("mode", "?"),
            "health":       health_score,
            "active_flow":  (state.get("sprint_status") or {}).get("active_workflow") or state.get("active_flow") or "ninguno",
            "ideas_count":  len(state.get("ideas", [])),
            "last_w2":      ((state.get("sprint_status") or {}).get("last_completed_workflow") or {}).get("title", "?"),
            "last_session": state.get("last_session_date") or state.get("updated_at", "?"),
            "project":      state.get("project", "bago-core"),
        }
    except Exception as e:
        return {"error": str(e)}

# ─── Terminal launcher ────────────────────────────────────────────────────────

def open_terminal(script_path: str, env_vars: dict = None):
    if sys.platform == "win32":
        env_vars = env_vars or {}
        env_prefix = ""
        for key, value in env_vars.items():
            safe = str(value).replace("'", "''")
            env_prefix += f"$env:{key}='{safe}'; "
        script = Path(script_path).name
        agent_id = script.removesuffix(".sh")
        task = env_vars.get("BAGO_TASK", "")
        model = env_vars.get("BAGO_AGENT_MODEL", "")
        if agent_id == "ollama":
            if task:
                cmd = f"{env_prefix}Set-Location '{BAGO_CORE}'; python .\\bago llm chat '{str(task).replace(chr(39), chr(39)+chr(39))}'; Read-Host 'Enter para cerrar'"
            else:
                cmd = f"{env_prefix}Set-Location '{BAGO_CORE}'; python .\\bago llm status; Read-Host 'Enter para cerrar'"
        elif agent_id == "codex":
            prompt = f"Lee .bago/state/global_state.json para contexto BAGO. Tarea: {task}" if task else ""
            model_arg = f"--model '{str(model).replace(chr(39), chr(39)+chr(39))}'" if model else ""
            prompt_arg = f"'{prompt.replace(chr(39), chr(39)+chr(39))}'" if prompt else ""
            cmd = f"{env_prefix}Set-Location '{BAGO_CORE}'; codex {model_arg} {prompt_arg}; Read-Host 'Enter para cerrar'"
        elif agent_id == "copilot":
            prompt = f"Estoy usando BAGO. Ayudame a: {task}" if task else ""
            if shutil.which("copilot"):
                prompt_arg = f"-i '{prompt.replace(chr(39), chr(39)+chr(39))}'" if prompt else ""
                cmd = f"{env_prefix}Set-Location '{BAGO_CORE}'; copilot {prompt_arg}; Read-Host 'Enter para cerrar'"
            else:
                prompt_arg = f"-- --prompt '{prompt.replace(chr(39), chr(39)+chr(39))}'" if prompt else ""
                cmd = f"{env_prefix}Set-Location '{BAGO_CORE}'; gh copilot {prompt_arg}; Read-Host 'Enter para cerrar'"
        else:
            cmd = f"{env_prefix}Set-Location '{BAGO_CORE}'; python .\\bago route '{str(task).replace(chr(39), chr(39)+chr(39))}'; Read-Host 'Enter para cerrar'"
        subprocess.Popen(["powershell", "-NoExit", "-Command", cmd])
        return

    env_str = ""
    if env_vars:
        parts = [f"export {k}='{v}';" for k, v in env_vars.items()]
        env_str = " ".join(parts) + " "
    osa = f'tell application "Terminal" to do script "{env_str}bash \\"{script_path}\\""'
    subprocess.Popen(["osascript", "-e", osa])

def launch_agent(agent_id: str, model: str = None, task: str = None):
    script = AGENTS_DIR / f"{agent_id}.sh"
    if not script.exists():
        return {"ok": False, "error": f"Script {script} no encontrado"}
    env = {}
    if model:
        env["BAGO_AGENT_MODEL"] = model
    if task:
        env["BAGO_TASK"] = task.replace("'", "").replace('"', "")
    open_terminal(str(script), env)
    return {"ok": True, "agent": agent_id, "model": model}

# ─── New API helpers ──────────────────────────────────────────────────────────

def get_routing_history(limit: int = 50) -> list:
    """Read last N entries from routing_history.jsonl (newest first)."""
    if not ROUTING_HISTORY.exists():
        return []
    try:
        raw = ROUTING_HISTORY.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        lines = raw.splitlines()
        entries = []
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
            if len(entries) >= limit:
                break
        return entries
    except Exception:
        return []


def get_sessions(limit: int = 20) -> list:
    """List recent session JSON files from the sessions directory."""
    if not SESSIONS_DIR.exists():
        return []
    try:
        files = sorted(
            [f for f in SESSIONS_DIR.iterdir() if f.suffix == ".json"],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:limit]
        result = []
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                data.setdefault("_file", f.name)
                result.append(data)
            except Exception:
                result.append({"_file": f.name, "error": "parse error"})
        return result
    except Exception:
        return []


def get_pending_task() -> dict:
    """Read pending W2 task state."""
    if not PENDING_TASK.exists():
        return {"status": "none"}
    try:
        return json.loads(PENDING_TASK.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "error", "error": "parse error"}


def get_ideas(limit: int = 30) -> list:
    """Read implemented ideas list."""
    if not IDEAS_FILE.exists():
        return []
    try:
        data = json.loads(IDEAS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data[:limit]
        return data.get("implemented", [])[:limit]
    except Exception:
        return []


def get_llm_status() -> dict:
    """Return LLM config + Ollama availability and model list."""
    cfg: dict = {}
    if LLM_CONFIG_FILE.exists():
        try:
            cfg = json.loads(LLM_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    server_url = cfg.get("server_url", "http://127.0.0.1:11434")
    ollama_available = False
    ollama_models: list = []
    try:
        req = urllib.request.Request(
            f"{server_url}/api/tags",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            ollama_models = [m["name"] for m in data.get("models", [])]
            ollama_available = True
    except Exception:
        pass

    return {
        "engine": cfg.get("engine", "ollama"),
        "active_model": cfg.get("active_model", "qwen25-coder"),
        "server_url": server_url,
        "ollama_available": ollama_available,
        "ollama_models": ollama_models,
    }


def llm_chat(message: str, model: str | None = None) -> dict:
    """Send a prompt to the local Ollama instance and return the response."""
    if not message.strip():
        return {"ok": False, "error": "mensaje vacío"}

    cfg: dict = {}
    if LLM_CONFIG_FILE.exists():
        try:
            cfg = json.loads(LLM_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    server_url   = cfg.get("server_url", "http://127.0.0.1:11434")
    active_model = model or cfg.get("active_model", "qwen25-coder")
    payload      = json.dumps(
        {"model": active_model, "prompt": message, "stream": False}
    ).encode()
    try:
        req = urllib.request.Request(
            f"{server_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return {"ok": True, "response": data.get("response", ""), "model": active_model}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def bago_run(command: str, confirmed: bool = False) -> dict:
    """Run a bago sub-command.

    Sensitive keywords require explicit ``confirmed=True`` to proceed.
    The first token of ``command`` must be in the known sub-command set;
    additional arguments are validated to contain no shell metacharacters.
    """
    import shlex

    try:
        parts = shlex.split(command)
    except ValueError as e:
        return {"ok": False, "error": f"Comando inválido: {e}"}

    if not parts:
        return {"ok": False, "error": "command vacío"}

    # Validate sub-command (first token) against the known keyword sets
    sub_cmd = parts[0].lower()
    is_sensitive = sub_cmd in _SENSITIVE_KW

    # Extra check: reject any arg containing shell-special characters
    _SHELL_CHARS = set(";&|`$<>\\()")
    for arg in parts:
        if any(ch in arg for ch in _SHELL_CHARS):
            return {"ok": False, "error": "Argumento contiene caracteres no permitidos"}

    if is_sensitive and not confirmed:
        return {
            "ok": False,
            "requires_confirmation": True,
            "command": command,
            "warning": (
                "Esta acción puede modificar el sistema de forma irreversible. "
                "Confirma para continuar."
            ),
        }

    bago_bin = BAGO_CORE / "bago"
    try:
        result = subprocess.run(
            [sys.executable, str(bago_bin)] + parts,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(BAGO_CORE),
        )
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─── HTTP Handler ─────────────────────────────────────────────────────────────

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, fmt, *args):
        if args and str(args[1]) not in ("200", "304"):
            super().log_message(fmt, *args)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/agents":
            self._json(detect_agents())
        elif path == "/api/status":
            self._json(bago_status())
        elif path == "/api/routing-history":
            self._json(get_routing_history())
        elif path == "/api/sessions":
            self._json(get_sessions())
        elif path == "/api/task":
            self._json(get_pending_task())
        elif path == "/api/ideas":
            self._json(get_ideas())
        elif path == "/api/llm/status":
            self._json(get_llm_status())
        elif path in ("/", ""):
            self.path = "/index.html"
            super().do_GET()
        elif path == "/favicon.ico":
            # Serve inline SVG favicon to avoid 404 noise
            svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><text y="26" font-size="28">\xe2\xac\xa1</text></svg>'
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Content-Length", str(len(svg)))
            self.end_headers()
            self.wfile.write(svg)
        else:
            super().do_GET()

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length)) if length else {}

        if path == "/api/launch":
            agent = body.get("agent")
            model = body.get("model")
            task  = body.get("task")
            if not agent:
                self._json({"ok": False, "error": "agent requerido"}, 400)
                return
            self._json(launch_agent(agent, model, task))

        elif path == "/api/route":
            task = body.get("task", "")
            if not task.strip():
                self._json({"error": "task vacío"}, 400)
                return
            agents = detect_agents()
            result = route_task(task, agents)
            self._json(result)

        elif path == "/api/llm/chat":
            message = body.get("message", "")
            model   = body.get("model")
            if not message.strip():
                self._json({"ok": False, "error": "mensaje vacío"}, 400)
                return
            self._json(llm_chat(message, model))

        elif path == "/api/bago/run":
            command   = body.get("command", "")
            confirmed = bool(body.get("confirmed", False))
            if not command.strip():
                self._json({"ok": False, "error": "command vacío"}, 400)
                return
            self._json(bago_run(command, confirmed))

        else:
            self._json({"error": "not found"}, 404)

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    url = f"http://localhost:{PORT}"
    print(f"""
╔══════════════════════════════════════════╗
║  BAGO Launcher v1.0  ·  modo dinámico   ║
║  {url}                    ║
╚══════════════════════════════════════════╝
  Ctrl+C para detener
""")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    server = http.server.HTTPServer(("localhost", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n✅ BAGO Launcher detenido.")
        server.shutdown()

if __name__ == "__main__":
    main()
