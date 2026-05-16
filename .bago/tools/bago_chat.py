#!/usr/bin/env python3
"""
bago_chat.py — BAGO Multi-Model Chat REPL
Uso: python bago_chat.py [--provider copilot|codex|ollama] [--model <nombre>]

Caracteristicas:
  - Multi-modelo con LiteLLM (Ollama, OpenAI, Copilot/Anthropic)
  - Historial completo mantenido al cambiar de modelo (/switch)
  - Router BAGO: elige modelo optimo por tarea
  - Comandos: /switch /status /models /save /clear /help /exit
"""
import argparse, json, os, sys, datetime
from pathlib import Path

try:
    import litellm
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich import box
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.styles import Style
except ImportError as e:
    print(f"ERROR: {e}\n  Ejecuta: pip install litellm rich prompt_toolkit")
    sys.exit(1)

litellm.suppress_debug_info = True
litellm.set_verbose = False
console = Console()

# ── Rutas ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR     = Path(__file__).parent
BAGO_DIR       = SCRIPT_DIR.parent                    # .bago/
STATE_DIR      = BAGO_DIR / "state"
SESSIONS_DIR   = Path.home() / ".bago" / "sessions"
PROVIDERS_FILE = STATE_DIR / "model_providers.json"
ROUTING_FILE   = STATE_DIR / "model_routing.json"

BAGO_SYSTEM = (
    "Eres BAGO (Balanced Adaptive Generative Organizer), un framework de desarrollo "
    "asistido por IA. Reglas maestras: no generar antes de entender; no redisenar por "
    "impulso; preferir cambios minimos, claros y trazables; no cerrar sin dejar el "
    "siguiente paso claro; repo-first: inspeccionar antes de actuar; maximo 3 roles "
    "activos simultaneamente; cambios sensibles requieren validacion humana. "
    "Actua como MAESTRO_BAGO: coordina, analiza, genera y organiza. Se conciso pero completo."
)

# ── Config ────────────────────────────────────────────────────────────────────
def load_providers():
    try:   return json.loads(PROVIDERS_FILE.read_text(encoding="utf-8"))["providers"]
    except: return {}

def load_routing():
    try:   return json.loads(ROUTING_FILE.read_text(encoding="utf-8"))
    except: return {"rules": [], "fallback": {"provider": "codex", "model": "gpt-5.4"}}

# ── Modelo LiteLLM ────────────────────────────────────────────────────────────
def resolve_litellm(provider, wire_name):
    if provider in ("ollama-local", "ollama-cloud"):
        return f"ollama/{wire_name}", {"api_base": "http://127.0.0.1:11434"}
    if provider == "copilot":
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
        if token:
            return f"openai/{wire_name}", {
                "api_base": "https://models.inference.ai.azure.com",
                "api_key": token,
            }
        return wire_name, {}
    return wire_name, {}  # codex/openai

def get_default_model(provider_name, providers):
    prov   = providers.get(provider_name, {})
    models = prov.get("models", {})
    if not models: return "", "", provider_name
    k = next(iter(models))
    return k, models[k].get("wire_name", k), provider_name

def route_by_task(task, routing, providers):
    tl = task.lower()
    for rule in routing.get("rules", []):
        for kw in rule.get("keywords", []):
            if kw.lower() in tl:
                prov  = rule["provider"]
                model = rule["model"]
                wire  = providers.get(prov,{}).get("models",{}).get(model,{}).get("wire_name", model)
                return model, wire, prov
    fb = routing.get("fallback", {})
    return fb.get("model","gpt-5.4"), fb.get("model","gpt-5.4"), fb.get("provider","codex")

# ── Sesion ────────────────────────────────────────────────────────────────────
class BagoSession:
    def __init__(self, provider, model_name, wire_name):
        self.provider   = provider
        self.model_name = model_name
        self.wire_name  = wire_name
        self.history    = [{"role": "system", "content": BAGO_SYSTEM}]
        self.switches   = 0
        self.started_at = datetime.datetime.now()
        self.providers  = load_providers()
        self.routing    = load_routing()

    @property
    def litellm_info(self): return resolve_litellm(self.provider, self.wire_name)

    def switch_model(self, target):
        shortcuts = {"copilot":"copilot","codex":"codex",
                     "ollama":"ollama-local","ollama-local":"ollama-local","ollama-cloud":"ollama-cloud"}
        if target in shortcuts:
            name, wire, prov = get_default_model(shortcuts[target], self.providers)
        else:
            name, wire, prov = self._find(target)
        if not name: return f"'{target}' no encontrado. Usa /models."
        old = self.model_name
        self.provider, self.model_name, self.wire_name = prov, name, wire
        self.switches += 1
        return f"Cambiado: {old} -> {name} ({prov}) | {len(self.history)-1} msgs mantenidos"

    def _find(self, name):
        for pn, pd in self.providers.items():
            if name in pd.get("models", {}):
                return name, pd["models"][name].get("wire_name", name), pn
        return "", "", ""

    def save(self):
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        ts   = self.started_at.strftime("%Y-%m-%d_%H-%M-%S")
        path = SESSIONS_DIR / f"bago_chat_{ts}.json"
        path.write_text(json.dumps({
            "started_at": self.started_at.isoformat(), "provider": self.provider,
            "model": self.model_name, "switches": self.switches,
            "messages": len(self.history)-1, "history": self.history,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def models_table(self):
        lines = []
        for pn, pd in self.providers.items():
            lines.append(f"\n[{pn}]")
            for mn, md in pd.get("models", {}).items():
                act = " < ACTIVO" if mn == self.model_name else ""
                lines.append(f"  {mn:<30} {md.get('best_for',''):<25} {md.get('cost','')}{act}")
        return "\n".join(lines)

# ── UI ────────────────────────────────────────────────────────────────────────
COLORS = {"copilot":"yellow","codex":"magenta","ollama-local":"green","ollama-cloud":"cyan"}

def banner(session):
    c = COLORS.get(session.provider, "white")
    console.print(Panel(
        f"[bold {c}]BAGO Chat[/bold {c}]  modelo: [bold]{session.model_name}[/bold]  provider: {session.provider}\n"
        "[dim]/switch <modelo>   /models   /status   /save   /clear   /help   /exit[/dim]",
        box=box.ROUNDED, border_style=c))

def show_response(text, session):
    c = COLORS.get(session.provider, "white")
    try:    content = Markdown(text)
    except: content = text
    console.print(Panel(content, title=f"[{c}]{session.model_name}[/{c}]",
                        border_style=c, box=box.ROUNDED))

pi = lambda m: console.print(f"[dim cyan]  {m}[/dim cyan]")
pe = lambda m: console.print(f"[bold red]  x {m}[/bold red]")

HELP = """[bold]Comandos BAGO Chat:[/bold]
  [yellow]/switch <modelo|provider>[/yellow]  Cambia modelo SIN perder historial
    Ej: /switch copilot  /switch codex  /switch ollama  /switch gpt-5.4
  [yellow]/models[/yellow]    Lista todos los modelos del registry BAGO
  [yellow]/status[/yellow]    Estado: modelo, provider, msgs en memoria, tiempo
  [yellow]/save[/yellow]      Guarda la sesion en ~/.bago/sessions/
  [yellow]/clear[/yellow]     Limpia historial (mantiene sistema BAGO)
  [yellow]/help[/yellow]      Esta ayuda
  [yellow]/exit[/yellow]      Salir (tambien Ctrl+D)
"""

def cmd(line, session):
    parts = line.strip().split(None, 1)
    v = parts[0].lower(); a = parts[1].strip() if len(parts) > 1 else ""
    if v == "/exit":
        console.print("[dim]BAGO Chat terminado.[/dim]"); return False
    if v == "/help":
        console.print(HELP)
    elif v == "/switch":
        if not a: pe("Uso: /switch <modelo|provider>")
        else:
            msg = session.switch_model(a)
            pi(msg)
            c = COLORS.get(session.provider,"white")
            console.print(f"  [{c}]{session.model_name} ({session.provider})[/{c}]")
    elif v == "/models":
        console.print(Panel(session.models_table(), title="[bold]Registry BAGO[/bold]", box=box.SIMPLE))
    elif v == "/status":
        elapsed = str(datetime.datetime.now()-session.started_at).split(".")[0]
        console.print(Panel(
            f"Modelo:    {session.model_name}\nProvider:  {session.provider}\n"
            f"Wire:      {session.wire_name}\nHistorial: {len(session.history)-1} mensajes\n"
            f"Switches:  {session.switches}\nTiempo:    {elapsed}",
            title="[bold]Estado[/bold]", box=box.ROUNDED))
    elif v == "/save":
        pi(f"Guardado: {session.save()}")
    elif v == "/clear":
        session.history = [{"role":"system","content":BAGO_SYSTEM}]
        pi("Historial limpiado. Sistema BAGO mantenido.")
    else:
        pe(f"Comando desconocido: {v}  —  /help")
    return True

# ── Chat ──────────────────────────────────────────────────────────────────────
def chat(session, user_input):
    session.history.append({"role":"user","content":user_input})
    lm, kw = session.litellm_info
    try:
        with console.status(f"[dim]{session.model_name} ...[/dim]", spinner="dots"):
            r = litellm.completion(model=lm, messages=session.history, **kw)
        text = r.choices[0].message.content
        session.history.append({"role":"assistant","content":text})
        return text
    except Exception as e:
        session.history.pop()
        raise RuntimeError(str(e))

# ── Main ──────────────────────────────────────────────────────────────────────
def auto_detect_provider(providers):
    """Elige el mejor provider disponible sin intervención del usuario."""
    import subprocess
    if os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"):
        return "copilot"
    try:
        out = subprocess.check_output(["ollama", "list"], text=True, stderr=subprocess.DEVNULL)
        for mn, md in providers.get("ollama-local", {}).get("models", {}).items():
            base = md.get("wire_name","").split(":")[0]
            if base and base in out:
                return "ollama-local"
    except Exception:
        pass
    return "codex"

def main():
    p = argparse.ArgumentParser(description="BAGO Chat — Multi-modelo REPL")
    p.add_argument("--provider", default="",
                   choices=["","copilot","codex","ollama","ollama-local","ollama-cloud"])
    p.add_argument("--model", default="")
    p.add_argument("--task",  default="")
    args = p.parse_args()

    providers = load_providers()
    routing   = load_routing()

    if args.model:
        name, wire, prov = "", "", args.provider or "codex"
        for pn, pd in providers.items():
            if args.model in pd.get("models", {}):
                name, wire, prov = args.model, pd["models"][args.model].get("wire_name", args.model), pn
                break
        if not name:
            console.print(f"[red]Modelo '{args.model}' no encontrado.[/red]"); sys.exit(1)
    elif args.task:
        name, wire, prov = route_by_task(args.task, routing, providers)
        pi(f"Router BAGO -> {name} ({prov}) para: {args.task}")
    else:
        pm = {"copilot":"copilot","codex":"codex","ollama":"ollama-local",
              "ollama-local":"ollama-local","ollama-cloud":"ollama-cloud"}
        chosen = pm.get(args.provider, "") or auto_detect_provider(providers)
        if not args.provider:
            pi(f"Provider detectado automáticamente: {chosen}")
        name, wire, prov = get_default_model(chosen, providers)
        if not name:
            console.print(f"[red]No hay modelos para '{chosen}'.[/red]"); sys.exit(1)

    session = BagoSession(prov, name, wire)
    banner(session)

    hist_file = Path.home() / ".bago" / "state" / "chat_input_history.txt"
    hist_file.parent.mkdir(parents=True, exist_ok=True)
    pt = PromptSession(history=FileHistory(str(hist_file)),
                       auto_suggest=AutoSuggestFromHistory(),
                       style=Style.from_dict({"prompt":"bold cyan"}))

    while True:
        try:
            line = pt.prompt(f"[{session.model_name}] > ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]BAGO Chat terminado.[/dim]"); break
        if not line: continue
        if line.startswith("/"):
            if not cmd(line, session): break
            continue
        try:
            show_response(chat(session, line), session)
        except RuntimeError as e:
            pe(str(e))
            console.print("[dim]  Prueba /switch <modelo> para cambiar de provider.[/dim]")

if __name__ == "__main__":
    main()
