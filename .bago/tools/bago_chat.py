#!/usr/bin/env python3
"""
bago_chat.py — BAGO Orchestrator HUB v2
Uso: python bago_chat.py [--provider copilot|codex|ollama]

Todo es automatico. El orquestador:
  - Detecta credenciales disponibles al arrancar
  - Elige el modelo optimo para cada peticion
  - Decide automaticamente si usar single / chain / ensemble
  - Mantiene historial unificado aunque cambien los modelos
  /login para registrar proveedores  
"""
import argparse, json, os, sys, datetime, concurrent.futures, subprocess, getpass
from pathlib import Path

try:
    import litellm
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.table import Table
    from rich import box
    from prompt_toolkit import PromptSession, prompt as pt_prompt
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.styles import Style
except ImportError as e:
    print(f"ERROR: {e}\n  Ejecuta: pip install litellm rich prompt_toolkit")
    sys.exit(1)

litellm.suppress_debug_info = True
litellm.set_verbose = False
console = Console()

# ── Rutas ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR     = Path(__file__).parent
BAGO_DIR       = SCRIPT_DIR.parent
STATE_DIR      = BAGO_DIR / "state"
USER_BAGO      = Path.home() / ".bago"
SESSIONS_DIR   = USER_BAGO / "sessions"
CRED_FILE      = USER_BAGO / "credentials.json"
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

COLORS = {"copilot":"yellow","codex":"magenta","ollama-local":"green","ollama-cloud":"cyan"}

# ── Credential Manager ─────────────────────────────────────────────────────────
class CredentialManager:
    """Gestiona credenciales de todos los proveedores. /login para registrar."""
    PROVIDERS = {
        "github":    {"env": "GITHUB_TOKEN",    "bago_provider": "copilot",
                      "desc": "GitHub Copilot", "login_type": "gh_cli"},
        "openai":    {"env": "OPENAI_API_KEY",  "bago_provider": "codex",
                      "desc": "OpenAI / Codex", "login_type": "api_key"},
        "anthropic": {"env": "ANTHROPIC_API_KEY","bago_provider": "anthropic",
                      "desc": "Anthropic / Claude", "login_type": "api_key"},
        "ollama":    {"env": None,              "bago_provider": "ollama-local",
                      "desc": "Ollama local (sin clave)", "login_type": "service"},
    }
    ALIASES = {"gpt":"openai","claude":"anthropic","claw":"anthropic",
               "copilot":"github","gh":"github","local":"ollama"}

    def __init__(self):
        self._creds = {}
        self._load()
        self._apply_env()

    def _load(self):
        if CRED_FILE.exists():
            try:
                self._creds = json.loads(CRED_FILE.read_text(encoding="utf-8"))
            except Exception:
                self._creds = {}

    def _save(self):
        CRED_FILE.parent.mkdir(parents=True, exist_ok=True)
        CRED_FILE.write_text(json.dumps(self._creds, indent=2), encoding="utf-8")
        try:
            import stat
            CRED_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass

    def _apply_env(self):
        for name, info in self.PROVIDERS.items():
            env_key = info.get("env")
            if env_key and not os.environ.get(env_key):
                saved = self._creds.get(name)
                if saved:
                    os.environ[env_key] = saved

    def set(self, provider_name, key):
        self._creds[provider_name] = key
        env_key = self.PROVIDERS.get(provider_name, {}).get("env")
        if env_key:
            os.environ[env_key] = key
        self._save()

    def _ollama_ok(self):
        try:
            subprocess.check_output(["ollama", "list"], stderr=subprocess.DEVNULL, timeout=4)
            return True
        except Exception:
            return False

    def active_bago_providers(self):
        """Devuelve lista de bago_provider strings que tienen credenciales activas."""
        active = []
        for name, info in self.PROVIDERS.items():
            if name == "ollama":
                if self._ollama_ok():
                    active.append("ollama-local")
            else:
                env_key = info.get("env")
                if env_key and os.environ.get(env_key):
                    active.append(info["bago_provider"])
        return active

    def status_table(self):
        t = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        t.add_column("Provider"); t.add_column("Estado"); t.add_column("Descripcion")
        for name, info in self.PROVIDERS.items():
            if name == "ollama":
                ok = self._ollama_ok()
                status = "[green]✓ activo[/green]" if ok else "[red]✗ no disponible[/red]"
            else:
                env_key = info.get("env")
                val = os.environ.get(env_key, "") if env_key else ""
                if val:
                    masked = val[:4] + "…" + val[-4:] if len(val) > 8 else "●●●"
                    status = f"[green]✓ {masked}[/green]"
                else:
                    status = "[red]✗ sin credencial[/red]"
            t.add_row(name, status, info["desc"])
        t.add_row("[dim]/login <provider>[/dim]","","[dim]para registrar[/dim]")
        return t

    def do_login(self, alias):
        name = self.ALIASES.get(alias.lower(), alias.lower())
        info = self.PROVIDERS.get(name)
        if not info:
            return f"Provider '{alias}' desconocido. Opciones: {', '.join(self.PROVIDERS)}"

        ltype = info["login_type"]
        if ltype == "gh_cli":
            console.print(f"[dim]Ejecutando gh auth login...[/dim]")
            result = subprocess.run(["gh", "auth", "login"])
            if result.returncode != 0:
                return "Login GitHub fallido."
            try:
                token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
                self.set("github", token)
                return f"[green]✓ GitHub token guardado ({token[:4]}…{token[-4:]})[/green]"
            except Exception as e:
                return f"Token obtenido pero no guardado: {e}"

        elif ltype == "api_key":
            key = pt_prompt(f"{info['desc']} API Key: ", is_password=True).strip()
            if not key:
                return "Cancelado."
            self.set(name, key)
            return f"[green]✓ {info['desc']} API key guardada.[/green]"

        elif ltype == "service":
            if self._ollama_ok():
                try:
                    out = subprocess.check_output(["ollama", "list"], text=True,
                                                  stderr=subprocess.DEVNULL)
                    console.print(out)
                    return "[green]✓ Ollama activo y disponible.[/green]"
                except Exception:
                    pass
            return "[red]Ollama no disponible. Instala desde https://ollama.com[/red]"

# ── Config ─────────────────────────────────────────────────────────────────────
def load_providers():
    try:   return json.loads(PROVIDERS_FILE.read_text(encoding="utf-8"))["providers"]
    except: return {}

def load_routing():
    try:   return json.loads(ROUTING_FILE.read_text(encoding="utf-8"))
    except: return {"rules": [], "fallback": {"provider": "codex", "model": "gpt-5.4"}}

# ── Routing & strategy ─────────────────────────────────────────────────────────
def route_by_task(task, routing, providers):
    tl = task.lower()
    for rule in routing.get("rules", []):
        for kw in rule.get("keywords", []):
            if kw.lower() in tl:
                prov  = rule["provider"]
                model = rule["model"]
                wire  = providers.get(prov,{}).get("models",{}).get(model,{}).get("wire_name", model)
                return model, wire, prov, kw
    fb = routing.get("fallback", {})
    return fb.get("model","gpt-5.4"), fb.get("model","gpt-5.4"), fb.get("provider","codex"), None

def detect_strategy(text, active_providers):
    """
    Decide automaticamente la estrategia optima para una peticion.
    Retorna: ("single"|"chain"|"ensemble", [provider_list])
    single    — una sola llamada al mejor modelo
    chain     — pipeline: primer modelo genera, siguiente refina/revisa
    ensemble  — paralelo: varios modelos responden, el activo sintetiza
    """
    if len(active_providers) < 2:
        return "single", []

    tl = text.lower()

    # Senales de cadena: creacion + revision en la misma peticion
    creates  = any(w in tl for w in ["escrib","crea","genera","implementa","construye",
                                      "diseña","haz ","build","write","create","code","codigo"])
    reviews  = any(w in tl for w in ["explica","comenta","documenta","revisa","mejora",
                                      "optimiza","explain","review","improve","refactor",
                                      "y luego","despues","tras","then"])
    code_ctx = any(w in tl for w in ["codigo","code","funcion","function","clase","class",
                                      "script","api","test","algoritmo","algorithm"])

    # Senales de ensemble: opinion, comparacion, perspectivas multiples
    opinions = any(w in tl for w in ["mejor forma","mejor manera","best way","recomiend",
                                      "que opinas","opinion","pros y contras","ventajas",
                                      "desventajas","compara","versus"," vs ","alternativa",
                                      "cual es mejor","debate","perspectiva","enfoque"])

    if creates and (reviews or (code_ctx and reviews)):
        return "chain", active_providers[:2]

    if opinions:
        return "ensemble", active_providers[:min(3, len(active_providers))]

    # Peticion larga y compleja: chain por defecto
    if len(text) > 300 and creates:
        return "chain", active_providers[:2]

    return "single", []

def get_default_model(provider_name, providers):
    prov   = providers.get(provider_name, {})
    models = prov.get("models", {})
    if not models: return "", "", provider_name
    k = next(iter(models))
    return k, models[k].get("wire_name", k), provider_name

def best_model_for_provider(prov_name, providers):
    """Primer modelo del provider o None."""
    name, wire, prov = get_default_model(prov_name, providers)
    return (name, wire, prov) if name else None

# ── LiteLLM resolver ───────────────────────────────────────────────────────────
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
    return wire_name, {}

# ── Session ────────────────────────────────────────────────────────────────────
class BagoSession:
    def __init__(self, provider, model_name, wire_name, creds):
        self.provider   = provider
        self.model_name = model_name
        self.wire_name  = wire_name
        self.history    = [{"role": "system", "content": BAGO_SYSTEM}]
        self.switches   = 0
        self.started_at = datetime.datetime.now()
        self.providers  = load_providers()
        self.routing    = load_routing()
        self.creds      = creds
        self.autoroute  = True   # routing + estrategia automaticos por defecto

    @property
    def litellm_info(self): return resolve_litellm(self.provider, self.wire_name)

    def _find_model(self, name):
        shortcuts = {"copilot":"copilot","codex":"codex","ollama":"ollama-local",
                     "ollama-local":"ollama-local","ollama-cloud":"ollama-cloud","anthropic":"anthropic"}
        if name in shortcuts:
            r = best_model_for_provider(shortcuts[name], self.providers)
            if r: return r
        for pn, pd in self.providers.items():
            if name in pd.get("models", {}):
                return name, pd["models"][name].get("wire_name", name), pn
        return None, None, None

    def switch_model(self, target, silent=False):
        name, wire, prov = self._find_model(target)
        if not name: return f"'{target}' no encontrado. Usa /models."
        old = self.model_name
        self.provider, self.model_name, self.wire_name = prov, name, wire
        self.switches += 1
        if silent: return None
        return f"Cambiado: {old} → {name} ({prov}) | {len(self.history)-1} msgs mantenidos"

    def auto_route(self, user_input):
        """Routing por keyword: cambia al modelo mas adecuado para esta tarea."""
        name, wire, prov, kw = route_by_task(user_input, self.routing, self.providers)
        if name and name != self.model_name:
            # Verificar que el provider tiene credenciales
            active = self.creds.active_bago_providers()
            if prov in active or any(prov in a for a in active):
                old = self.model_name
                self.provider, self.model_name, self.wire_name = prov, name, wire
                self.switches += 1
                return True, f"auto-route [{kw}]: {old} → {name}"
        return False, None

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
        active = self.creds.active_bago_providers()
        lines = []
        for pn, pd in self.providers.items():
            avail = "✓" if pn in active else "○"
            lines.append(f"\n[{avail}] [{pn}]")
            for mn, md in pd.get("models", {}).items():
                act = " ← ACTIVO" if mn == self.model_name else ""
                lines.append(f"    {mn:<30} {md.get('best_for',''):<25} {md.get('cost','')}{act}")
        return "\n".join(lines)

# ── UI helpers ─────────────────────────────────────────────────────────────────
def show_response(text, model_name, provider, label=None):
    c = COLORS.get(provider, "white")
    try:    content = Markdown(text)
    except: content = text
    title = label or f"[{c}]{model_name}[/{c}]"
    console.print(Panel(content, title=title, border_style=c, box=box.ROUNDED))

pi = lambda m: console.print(f"[dim cyan]  {m}[/dim cyan]")
pe = lambda m: console.print(f"[bold red]  ✗ {m}[/bold red]")

def banner(session):
    active = session.creds.active_bago_providers()
    c = COLORS.get(session.provider, "white")
    providers_str = "  ".join(f"[{'green' if p in active else 'red'}]{p}[/{'green' if p in active else 'red'}]"
                              for p in COLORS)
    console.print(Panel(
        f"[bold {c}]BAGO Orchestrator HUB[/bold {c}]  →  [{c}]{session.model_name}[/{c}] ({session.provider})\n"
        f"Providers: {providers_str}\n"
        "[dim]Modo automático activo — /help para comandos   /login para registrar providers[/dim]",
        box=box.DOUBLE, border_style=c))

HELP = """[bold]BAGO Orchestrator HUB — Comandos:[/bold]

  [bold cyan]Providers y credenciales:[/bold cyan]
  [yellow]/login[/yellow]              Ver estado de todos los providers
  [yellow]/login github[/yellow]       Login con GitHub (usa gh CLI) → activa Copilot
  [yellow]/login openai[/yellow]       Añadir API Key de OpenAI → activa Codex/GPT
  [yellow]/login anthropic[/yellow]    Añadir API Key de Anthropic → activa Claude
  [yellow]/login ollama[/yellow]       Verificar Ollama local
  (aliases: gpt, claude, claw, copilot, gh, local)

  [bold cyan]Control de modelo:[/bold cyan]
  [yellow]/switch <modelo>[/yellow]    Forzar modelo manualmente (sin perder historial)
  [yellow]/autoroute on|off[/yellow]   Routing+estrategia automáticos (default: on)
  [yellow]/models[/yellow]             Lista todos los modelos disponibles

  [bold cyan]Estrategias multi-modelo (normalmente auto):[/bold cyan]
  [yellow]/chain m1->m2: prompt[/yellow]    Pipeline: m1 genera, m2 refina
  [yellow]/ensemble m1 m2: prompt[/yellow]  Paralelo + síntesis automática

  [bold cyan]Sesión:[/bold cyan]
  [yellow]/status[/yellow]   Estado actual   [yellow]/save[/yellow]  Guardar sesión
  [yellow]/clear[/yellow]    Limpiar historial   [yellow]/exit[/yellow]  Salir

[dim]El orquestador decide automáticamente qué modelo/s usar y con qué estrategia.[/dim]
"""

# ── Multi-model execution ──────────────────────────────────────────────────────
def _llm_call(lm, kw, messages):
    r = litellm.completion(model=lm, messages=messages, **kw)
    return r.choices[0].message.content

def run_chain(session, model_sequence, prompt, silent_route=True):
    """Pipeline secuencial. Solo la respuesta final va al historial compartido."""
    context = list(session.history)
    prev_text = None

    for i, target in enumerate(model_sequence):
        is_last = (i == len(model_sequence) - 1)
        name, wire, prov = session._find_model(target)
        if not name:
            pe(f"Modelo '{target}' no disponible, saltando.")
            continue

        lm, kw = resolve_litellm(prov, wire)
        c = COLORS.get(prov, "white")

        if i == 0:
            msgs = context + [{"role":"user","content": prompt}]
        else:
            msgs = [
                {"role":"system","content": BAGO_SYSTEM},
                {"role":"user","content":
                    f"Revisa y mejora esta respuesta. Corrige errores, completa huecos, mejora claridad.\n\n"
                    f"PREGUNTA ORIGINAL: {prompt}\n\nRESPUESTA PREVIA:\n{prev_text}"}
            ]

        step_label = f"paso {i+1}/{len(model_sequence)}: {name}"
        with console.status(f"[dim {c}]{step_label}...[/dim {c}]", spinner="dots"):
            try:
                text = _llm_call(lm, kw, msgs)
            except Exception as e:
                text = f"[ERROR {name}: {e}]"

        prev_text = text

        if is_last:
            show_response(text, name, prov, label=f"[bold]✓ CHAIN FINAL[/bold] [{c}]{name}[/{c}]")
            session.history.append({"role":"user","content": prompt})
            session.history.append({"role":"assistant","content": text})
            # Dejar el modelo en el ultimo de la cadena
            session.provider, session.model_name, session.wire_name = prov, name, wire
        else:
            console.print(f"  [{c}]✓ {name}[/{c}] [dim]→ refinando con siguiente modelo...[/dim]")

def run_ensemble(session, model_list, prompt):
    """Paralelo: todos responden, el modelo activo sintetiza."""
    context = list(session.history) + [{"role":"user","content": prompt}]
    results = {}

    def call_one(target):
        name, wire, prov = session._find_model(target)
        if not name: return None, None, f"'{target}' no encontrado"
        lm, kw = resolve_litellm(prov, wire)
        try:
            text = _llm_call(lm, kw, context)
            return name, prov, text
        except Exception as e:
            return name, prov, f"[ERROR: {e}]"

    console.print(f"  [dim]Consultando {len(model_list)} modelos...[/dim]")
    with concurrent.futures.ThreadPoolExecutor() as ex:
        futures = [ex.submit(call_one, t) for t in model_list]
        for f in concurrent.futures.as_completed(futures):
            name, prov, text = f.result()
            if name:
                results[name] = {"provider": prov or "codex", "text": text}
                show_response(text, name, prov or "codex")

    if len(results) >= 2:
        pi(f"Sintetizando con {session.model_name}...")
        drafts = "\n\n".join(f"[{mn}]:\n{d['text']}" for mn, d in results.items())
        synth = (f"Combina lo mejor de estas respuestas en una sola, coherente y completa.\n"
                 f"PREGUNTA: {prompt}\n\n{drafts}")
        lm, kw = session.litellm_info
        with console.status(f"[dim]{session.model_name} sintetizando...[/dim]", spinner="dots"):
            try:
                final = _llm_call(lm, kw, [{"role":"system","content":BAGO_SYSTEM},
                                            {"role":"user","content":synth}])
            except Exception as e:
                final = next(iter(results.values()))["text"]
        show_response(final, session.model_name, session.provider,
                      label=f"[bold]✦ SÍNTESIS[/bold] [{COLORS.get(session.provider,'white')}]{session.model_name}[/{COLORS.get(session.provider,'white')}]")
        session.history.append({"role":"user","content": prompt})
        session.history.append({"role":"assistant","content": final})
    elif results:
        mn, d = next(iter(results.items()))
        session.history.append({"role":"user","content": prompt})
        session.history.append({"role":"assistant","content": d["text"]})

# ── Chat (orquestador principal) ───────────────────────────────────────────────
def chat(session, user_input):
    """
    Punto de entrada principal. El orquestador decide automaticamente:
      1. Que modelo usar (auto-route por keywords)
      2. Que estrategia usar (single / chain / ensemble)
    El usuario no necesita hacer nada, todo es transparente.
    """
    if session.autoroute:
        # Paso 1: routing por keyword → mejor modelo para esta tarea
        switched, reason = session.auto_route(user_input)
        if switched:
            c = COLORS.get(session.provider, "white")
            console.print(f"  [dim {c}]{reason}[/dim {c}]")

        # Paso 2: detectar estrategia optima
        active = session.creds.active_bago_providers()
        strategy, providers_for_strategy = detect_strategy(user_input, active)

        if strategy == "chain" and len(providers_for_strategy) >= 2:
            console.print(f"  [dim]⛓ chain auto: {' → '.join(providers_for_strategy)}[/dim]")
            run_chain(session, providers_for_strategy, user_input)
            return None  # ya mostrado y añadido al historial dentro de run_chain

        if strategy == "ensemble" and len(providers_for_strategy) >= 2:
            console.print(f"  [dim]◈ ensemble auto: {', '.join(providers_for_strategy)}[/dim]")
            run_ensemble(session, providers_for_strategy, user_input)
            return None

    # Estrategia single (o autoroute desactivado)
    session.history.append({"role":"user","content":user_input})
    lm, kw = session.litellm_info
    try:
        with console.status(f"[dim]{session.model_name}...[/dim]", spinner="dots"):
            text = _llm_call(lm, kw, session.history)
        session.history.append({"role":"assistant","content": text})
        return text
    except Exception as e:
        session.history.pop()
        raise RuntimeError(str(e))

# ── Comando handler ────────────────────────────────────────────────────────────
def cmd(line, session):
    parts = line.strip().split(None, 1)
    v = parts[0].lower(); a = parts[1].strip() if len(parts) > 1 else ""

    if v == "/exit":
        console.print("[dim]BAGO Chat terminado.[/dim]"); return False
    elif v == "/help":
        console.print(HELP)
    elif v == "/login":
        if not a:
            console.print(Panel(session.creds.status_table(),
                                title="[bold]Providers BAGO[/bold]", box=box.ROUNDED))
        else:
            result = session.creds.do_login(a)
            console.print(f"  {result}")
    elif v == "/switch":
        if not a: pe("Uso: /switch <modelo|provider>")
        else:
            msg = session.switch_model(a)
            pi(msg)
    elif v == "/chain":
        if ":" not in a:
            pe("Uso: /chain modelo1->modelo2: prompt")
        else:
            chain_part, prompt_part = a.split(":", 1)
            models = [m.strip() for m in chain_part.split("->") if m.strip()]
            if len(models) < 2 or not prompt_part.strip():
                pe("Necesitas al menos 2 modelos y un prompt.")
            else:
                run_chain(session, models, prompt_part.strip())
    elif v == "/ensemble":
        if ":" not in a:
            pe("Uso: /ensemble modelo1 modelo2: prompt")
        else:
            mp, pp = a.split(":", 1)
            models = [m.strip() for m in mp.split() if m.strip()]
            if len(models) < 2 or not pp.strip():
                pe("Necesitas al menos 2 modelos y un prompt.")
            else:
                run_ensemble(session, models, pp.strip())
    elif v == "/autoroute":
        session.autoroute = a.lower() != "off"
        state = "ACTIVADO (auto single/chain/ensemble)" if session.autoroute else "DESACTIVADO"
        pi(f"Auto-routing: {state}")
    elif v == "/models":
        console.print(Panel(session.models_table(), title="[bold]Registry BAGO[/bold]", box=box.SIMPLE))
    elif v == "/status":
        elapsed = str(datetime.datetime.now()-session.started_at).split(".")[0]
        active = ", ".join(session.creds.active_bago_providers()) or "ninguno"
        console.print(Panel(
            f"Modelo:      {session.model_name} ({session.provider})\n"
            f"Wire:        {session.wire_name}\n"
            f"Historial:   {len(session.history)-1} mensajes\n"
            f"Switches:    {session.switches}\n"
            f"Tiempo:      {elapsed}\n"
            f"Auto-route:  {'ON' if session.autoroute else 'OFF'}\n"
            f"Providers:   {active}",
            title="[bold]Estado BAGO[/bold]", box=box.ROUNDED))
    elif v == "/save":
        pi(f"Guardado: {session.save()}")
    elif v == "/clear":
        session.history = [{"role":"system","content":BAGO_SYSTEM}]
        pi("Historial limpiado.")
    else:
        pe(f"Desconocido: {v}  —  /help")
    return True

# ── Auth auto-detect ───────────────────────────────────────────────────────────
def auto_detect_provider(creds, providers):
    active = creds.active_bago_providers()
    for preferred in ("copilot", "codex", "anthropic", "ollama-local"):
        if preferred in active:
            return preferred
    return "codex"

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="BAGO Orchestrator HUB")
    p.add_argument("--provider", default="")
    p.add_argument("--model", default="")
    p.add_argument("--task",  default="")
    args = p.parse_args()

    creds     = CredentialManager()
    providers = load_providers()
    routing   = load_routing()

    if args.model:
        # Modelo explicito
        name, wire, prov = None, None, args.provider or "codex"
        for pn, pd in providers.items():
            if args.model in pd.get("models", {}):
                name, wire, prov = args.model, pd["models"][args.model].get("wire_name", args.model), pn
                break
        if not name:
            console.print(f"[red]Modelo '{args.model}' no encontrado.[/red]"); sys.exit(1)
    elif args.task:
        name, wire, prov, _ = route_by_task(args.task, routing, providers)
        pi(f"Router BAGO → {name} ({prov}) para: {args.task}")
    else:
        pm = {"copilot":"copilot","codex":"codex","ollama":"ollama-local",
              "ollama-local":"ollama-local","ollama-cloud":"ollama-cloud","anthropic":"anthropic"}
        chosen = pm.get(args.provider, "") or auto_detect_provider(creds, providers)
        if not args.provider:
            pi(f"Provider detectado: {chosen}")
        name, wire, prov = get_default_model(chosen, providers)
        if not name:
            # Ningun provider activo — pedir login
            console.print(Panel(
                "[bold yellow]No hay providers activos.[/bold yellow]\n"
                "Usa [yellow]/login github[/yellow] para Copilot, "
                "[yellow]/login openai[/yellow] para GPT, "
                "[yellow]/login anthropic[/yellow] para Claude, "
                "[yellow]/login ollama[/yellow] para local.",
                title="BAGO — Login requerido", box=box.ROUNDED, border_style="yellow"))
            # Abrir el chat igualmente para que puedan hacer /login
            name, wire, prov = "sin-modelo", "sin-modelo", "none"

    session = BagoSession(prov, name, wire, creds)
    banner(session)

    hist_file = USER_BAGO / "state" / "chat_input_history.txt"
    hist_file.parent.mkdir(parents=True, exist_ok=True)
    pt = PromptSession(history=FileHistory(str(hist_file)),
                       auto_suggest=AutoSuggestFromHistory(),
                       style=Style.from_dict({"prompt":"bold cyan"}))

    while True:
        try:
            line = pt.prompt(f"[{session.model_name}] > ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]BAGO terminado.[/dim]"); break
        if not line: continue
        if line.startswith("/"):
            if not cmd(line, session): break
            continue
        try:
            result = chat(session, line)
            if result:   # None = ya mostrado por chain/ensemble
                show_response(result, session.model_name, session.provider)
        except RuntimeError as e:
            pe(str(e))
            console.print("[dim]  Prueba /login para registrar providers o /switch para cambiar modelo.[/dim]")

if __name__ == "__main__":
    main()
