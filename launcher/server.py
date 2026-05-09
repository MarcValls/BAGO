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
import urllib.parse
import webbrowser
from pathlib import Path

LAUNCHER_DIR = Path(__file__).parent.resolve()
BAGO_CORE    = LAUNCHER_DIR.parent
STATIC_DIR   = LAUNCHER_DIR / "static"
AGENTS_DIR   = LAUNCHER_DIR / "agents"
STATE_DIR    = BAGO_CORE / ".bago" / "state"
STATE_FILE   = STATE_DIR / "global_state.json"
PORT         = 7430

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
