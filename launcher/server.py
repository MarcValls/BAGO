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
STATE_FILE   = BAGO_CORE / ".bago" / "state" / "global_state.json"
OLLAMA_BIN   = BAGO_CORE / ".bago" / "bin" / "ollama-macos"
PORT         = 7430

# ─── Agent detection ──────────────────────────────────────────────────────────

def detect_agents():
    agents = []

    # 1. GitHub Copilot
    gh = shutil.which("gh")
    copilot_ok = False
    if gh:
        try:
            r = subprocess.run(["gh", "copilot", "--version"],
                               capture_output=True, text=True, timeout=4)
            copilot_ok = r.returncode == 0
        except subprocess.TimeoutExpired:
            copilot_ok = True  # command exists but slow (network check)
    agents.append({
        "id": "copilot",
        "name": "BAGO Copilot",
        "subtitle": "GitHub Copilot CLI",
        "icon": "🤖",
        "color": "#4f8ef7",
        "available": copilot_ok,
        "reason": None if copilot_ok else "gh copilot no instalado",
        "install_url": "https://github.com/github/gh-copilot",
        "models": ["github-copilot"],
        "strengths": ["código", "PR", "refactor", "tests", "git", "bug", "función", "implementar"],
    })

    # 2. OpenAI Codex
    codex = shutil.which("codex")
    agents.append({
        "id": "codex",
        "name": "BAGO Codex",
        "subtitle": "OpenAI Codex CLI",
        "icon": "⚡",
        "color": "#7c5ef7",
        "available": bool(codex),
        "reason": None if codex else "codex no instalado",
        "install_url": "https://github.com/openai/codex",
        "models": ["o4-mini", "gpt-4o"],
        "strengths": ["script", "archivo", "ejecutar", "automatizar", "pipeline", "api", "json"],
    })

    # 3. Ollama (pendrive — local, sin internet)
    ollama_ok = OLLAMA_BIN.exists()
    ollama_models = []
    if ollama_ok:
        try:
            r = subprocess.run([str(OLLAMA_BIN), "list"],
                               capture_output=True, text=True, timeout=5)
            for line in r.stdout.strip().splitlines()[1:]:
                if line.strip():
                    ollama_models.append(line.split()[0])
        except Exception:
            pass
    agents.append({
        "id": "ollama",
        "name": "BAGO Ollama",
        "subtitle": "Modelos locales (sin internet)",
        "icon": "🦙",
        "color": "#3ecf8e",
        "available": ollama_ok,
        "reason": None if ollama_ok else "ollama-macos no encontrado",
        "install_url": "https://ollama.ai",
        "models": ollama_models or (["qwen2.5:0.5b", "llama3.2:1b", "llama3.2:latest"] if ollama_ok else []),
        "strengths": ["local", "privado", "sin internet", "rápido", "offline", "ideas", "brainstorm"],
    })

    # 4. Claude CLI (placeholder)
    claude = shutil.which("claude")
    agents.append({
        "id": "claude",
        "name": "BAGO Claude",
        "subtitle": "Anthropic Claude CLI",
        "icon": "🐚",
        "color": "#f6ad55",
        "available": bool(claude),
        "reason": None if claude else "Claude CLI no instalado",
        "install_url": "https://docs.anthropic.com/claude/docs/cli",
        "models": ["claude-opus-4", "claude-sonnet-4"],
        "strengths": ["análisis", "redactar", "documento", "razonamiento", "largo", "complejo"],
    })

    return agents

# ─── Dynamic routing ──────────────────────────────────────────────────────────

ROUTING_RULES = [
    # (keywords, agent_id, model_hint, reason)
    (["código", "code", "bug", "función", "test", "pr", "refactor", "commit", "git", "error"],
     "copilot", None, "Copilot es ideal para tareas de código y revisión"),
    (["script", "archivo", "ejecutar", "automatizar", "pipeline", "api", "json", "bash", "python"],
     "codex", None, "Codex CLI es óptimo para scripts y automatización"),
    (["local", "privado", "sin internet", "offline", "rápido", "brainstorm", "idea", "notas"],
     "ollama", "qwen2.5:0.5b", "Ollama local: sin internet, rápido y privado"),
    (["análisis", "redactar", "documento", "razonamiento", "largo", "complejo", "explica"],
     "claude", None, "Claude destaca en análisis profundo y redacción"),
]

def route_task(task: str, agents: list) -> dict:
    task_lower = task.lower()
    available = {a["id"]: a for a in agents if a["available"]}

    if not available:
        return {"agent": None, "reason": "Ningún agente disponible", "confidence": 0}

    # Score each agent
    scores = {aid: 0 for aid in available}
    matched_reason = None
    matched_model = None

    for keywords, agent_id, model_hint, reason in ROUTING_RULES:
        if agent_id not in available:
            continue
        hits = sum(1 for kw in keywords if kw in task_lower)
        if hits > 0:
            scores[agent_id] = scores.get(agent_id, 0) + hits * 10
            if hits > 0 and scores[agent_id] >= max(scores.values()):
                matched_reason = reason
                matched_model  = model_hint

    best_id = max(scores, key=scores.get) if any(scores.values()) else list(available.keys())[0]
    best    = available[best_id]
    confidence = min(100, scores.get(best_id, 0) * 5) if any(scores.values()) else 50

    # Default model: first in list
    model = matched_model or (best["models"][0] if best["models"] else None)

    if not matched_reason:
        matched_reason = f"{best['name']} es el agente disponible con mayor capacidad general"

    return {
        "agent": best_id,
        "agent_name": best["name"],
        "agent_icon": best["icon"],
        "model": model,
        "reason": matched_reason,
        "confidence": confidence,
        "all_scores": scores,
    }

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
