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
    from prompt_toolkit.shortcuts import (radiolist_dialog, checkboxlist_dialog,
                                          button_dialog, input_dialog, yes_no_dialog)
except ImportError as e:
    print(f"ERROR: {e}\n  Ejecuta: pip install litellm rich prompt_toolkit")
    sys.exit(1)

litellm.suppress_debug_info = True
litellm.set_verbose = False
console = Console(force_terminal=True, highlight=False, markup=True,
                  safe_box=True, emoji=False)

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
                      "desc": "OpenAI / GPT Plus (sin API key si tienes Plus)",
                      "login_type": "openai_cli"},
        "anthropic": {"env": "ANTHROPIC_API_KEY","bago_provider": "anthropic",
                      "desc": "Anthropic / Claude", "login_type": "api_key"},
        "ollama":    {"env": None,              "bago_provider": "ollama-local",
                      "desc": "Ollama local (sin clave)", "login_type": "service"},
    }
    ALIASES = {"gpt":"openai","codex":"openai","claude":"anthropic","claw":"anthropic",
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

    def _codex_authed(self):
        """True si codex CLI tiene sesión activa (GPT Plus sin API key)."""
        # Marcador guardado por /login openai opción 1
        if self._creds.get("openai_via") in ("codex_login", "chatgpt_login"):
            return True
        try:
            codex_state = Path.home() / ".codex"
            for f in codex_state.glob("*.json"):
                try:
                    data = json.loads(f.read_text())
                    if data.get("accessToken") or data.get("token") or data.get("auth"):
                        return True
                except Exception:
                    pass
            return False
        except Exception:
            return False

    def _chatgpt_authed(self):
        """True si chatgpt CLI tiene sesión activa."""
        chatgpt_dir = Path.home() / "AppData" / "Roaming" / "chatgpt"
        for pattern in ["*.json", "config*", "auth*"]:
            for f in chatgpt_dir.glob(pattern) if chatgpt_dir.exists() else []:
                try:
                    data = json.loads(f.read_text())
                    if data.get("accessToken") or data.get("token"):
                        return True
                except Exception:
                    pass
        return False

    def active_bago_providers(self):
        """Devuelve lista de bago_provider strings que tienen credenciales activas."""
        active = []
        for name, info in self.PROVIDERS.items():
            if name == "ollama":
                if self._ollama_ok():
                    active.append("ollama-local")
            elif name == "openai":
                # Activo si: API key en env, O codex CLI autenticado, O chatgpt CLI autenticado
                if (os.environ.get("OPENAI_API_KEY") or
                        self._codex_authed() or self._chatgpt_authed()):
                    active.append("codex")
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
            elif name == "openai":
                if os.environ.get("OPENAI_API_KEY"):
                    k = os.environ["OPENAI_API_KEY"]
                    masked = k[:4] + "…" + k[-4:] if len(k) > 8 else "●●●"
                    status = f"[green]✓ API key {masked}[/green]"
                elif self._codex_authed():
                    status = "[green]✓ codex login (GPT Plus)[/green]"
                elif self._chatgpt_authed():
                    status = "[green]✓ chatgpt login (GPT Plus)[/green]"
                else:
                    status = "[red]✗ sin credencial[/red]"
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

        elif ltype == "openai_cli":
            # GPT Plus: intentar auth via codex CLI o chatgpt CLI (sin API key)
            console.print(
                "[bold]OpenAI / GPT — elige método:[/bold]\n"
                "  [yellow]1[/yellow]  codex login    (GPT Plus — abre navegador, sin API key)\n"
                "  [yellow]2[/yellow]  chatgpt login  (ChatGPT app — abre navegador)\n"
                "  [yellow]3[/yellow]  API key        (pegar clave manual)\n"
            )
            choice = pt_prompt("Opción [1/2/3]: ").strip()

            if choice == "1":
                console.print("[dim]Ejecutando codex login...[/dim]")
                result = subprocess.run(["codex", "login"])
                if result.returncode == 0:
                    # Marcar que codex está autenticado (sin guardar key en credentials.json)
                    self._creds["openai_via"] = "codex_login"
                    self._save()
                    return "[green]✓ Codex CLI autenticado (GPT Plus activo)[/green]"
                return "[red]codex login fallido.[/red]"

            elif choice == "2":
                console.print("[dim]Ejecutando chatgpt...[/dim]")
                result = subprocess.run(["chatgpt"])
                if result.returncode == 0:
                    self._creds["openai_via"] = "chatgpt_login"
                    self._save()
                    return "[green]✓ ChatGPT CLI autenticado (GPT Plus activo)[/green]"
                return "[red]chatgpt login fallido.[/red]"

            else:  # opción 3 o cualquier otra: API key manual
                key = pt_prompt("OpenAI API Key: ", is_password=True).strip()
                if not key:
                    return "Cancelado."
                self.set("openai", key)
                return "[green]✓ OpenAI API key guardada.[/green]"

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
pe = lambda m: console.print(f"[bold red]  X {m}[/bold red]")

def banner(session):
    active = session.creds.active_bago_providers()
    c = COLORS.get(session.provider, "white")
    providers_str = "  ".join(f"[{'green' if p in active else 'red'}]{p}[/{'green' if p in active else 'red'}]"
                              for p in COLORS)
    try:
        console.print(Panel(
            f"[bold {c}]BAGO Orchestrator HUB[/bold {c}]  >>  [{c}]{session.model_name}[/{c}] ({session.provider})\n"
            f"Providers: {providers_str}\n"
            "[dim]Modo automatico activo | /help para comandos   /login para registrar providers[/dim]",
            box=box.ASCII, border_style=c))
    except Exception:
        print(f"\n=== BAGO Orchestrator HUB === [{session.model_name}] ({session.provider})")
        print(f"Providers: {', '.join(COLORS.keys())}")
        print("Modo automatico activo | /help para comandos\n")

HELP = """[bold]BAGO Orchestrator HUB — Comandos:[/bold]

  [bold cyan]Providers y credenciales:[/bold cyan]
  [yellow]/login[/yellow]              Ver estado de todos los providers
  [yellow]/login github[/yellow]       Login con GitHub (usa gh CLI) -> activa Copilot
  [yellow]/login gpt[/yellow]          Login GPT Plus (codex login / chatgpt / API key)
  [yellow]/login openai[/yellow]       Alias de /login gpt
  [yellow]/login codex[/yellow]        Alias de /login gpt
  [yellow]/login anthropic[/yellow]    Añadir API Key de Anthropic -> activa Claude
  [yellow]/login ollama[/yellow]       Verificar Ollama local

  [bold cyan]Control de modelo:[/bold cyan]
  [yellow]/switch <modelo>[/yellow]    Forzar modelo manualmente (sin perder historial)
  [yellow]/autoroute on|off[/yellow]   Routing+estrategia automaticos (default: on)
  [yellow]/models[/yellow]             Lista todos los modelos disponibles

  [bold cyan]Estrategias multi-modelo (normalmente auto):[/bold cyan]
  [yellow]/chain m1->m2: prompt[/yellow]    Pipeline: m1 genera, m2 refina
  [yellow]/ensemble m1 m2: prompt[/yellow]  Paralelo + sintesis automatica

  [bold cyan]Agentes:[/bold cyan]
  [yellow]/agents[/yellow]                           Listar todos los agentes
  [yellow]/agents <nombre>[/yellow]                  Ver detalle de un agente
  [yellow]/agents add <nombre>[/yellow]              Crear agente nuevo
  [yellow]/agents toggle <nombre>[/yellow]           Activar / desactivar agente
  [yellow]/agents set <nombre> <campo> <val>[/yellow]   Editar campo
  [yellow]/agents del <nombre>[/yellow]              Eliminar agente

  [bold cyan]Skills:[/bold cyan]
  [yellow]/skills[/yellow]                           Listar todas las skills
  [yellow]/skills <nombre>[/yellow]                  Ver detalle de una skill
  [yellow]/skills add <nombre>[/yellow]              Crear skill nueva
  [yellow]/skills set <nombre> <campo> <val>[/yellow]   Editar campo
  [yellow]/skills del <nombre>[/yellow]              Eliminar skill

  [bold cyan]Routing (matriz de enrutamiento):[/bold cyan]
  [yellow]/routing[/yellow]                          Ver matriz completa
  [yellow]/routing <id>[/yellow]                     Ver regla concreta
  [yellow]/routing add <id> provider=X model=Y keywords=K reason=R[/yellow]
  [yellow]/routing del <id>[/yellow]                 Eliminar regla
  [yellow]/routing fallback <provider> <model>[/yellow]  Cambiar fallback
  [yellow]/routing move <id> up|down[/yellow]        Reordenar prioridad

  [bold cyan]Fabrica de piezas BAGO (asistida por LM):[/bold cyan]
  [yellow]/new[/yellow]  (alias: /wizard, /fabrica)
    Abre el wizard: describes en lenguaje natural lo que necesitas,
    el LM genera la definicion completa, tu la revisas campo a campo y guardas.
    Tipos de pieza: Agente | Skill | Modo/Rol | Regla routing | Preferencia tarea

  [bold cyan]Roles / Modos del orquestador:[/bold cyan]
  [yellow]/roles[/yellow]                            Ver modos (offline/economico/estandar/full)
  [yellow]/roles <modo>[/yellow]                     Detalle de un modo
  [yellow]/roles tasks[/yellow]                      Ver preferencias por tipo de tarea
  [yellow]/roles tasks <tarea>[/yellow]              Ver tarea concreta

  [bold cyan]Sesion:[/bold cyan]
  [yellow]/status[/yellow]   Estado actual   [yellow]/save[/yellow]  Guardar sesion
  [yellow]/clear[/yellow]    Limpiar historial   [yellow]/exit[/yellow]  Salir

[dim]El orquestador decide automaticamente que modelo/s usar y con que estrategia.[/dim]
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

    # ── Agentes ────────────────────────────────────────────────────────────────
    elif v == "/agents":
        _cmd_agents(a)

    # ── Roles / modos del orquestador ─────────────────────────────────────────
    elif v == "/roles":
        _cmd_roles(a)

    # ── Skills ────────────────────────────────────────────────────────────────
    elif v == "/skills":
        _cmd_skills(a)

    # ── Matriz de routing ─────────────────────────────────────────────────────
    elif v == "/routing":
        _cmd_routing(a)

    # ── Fabrica / Wizard LM ───────────────────────────────────────────────────
    elif v in ("/new", "/fabrica", "/wizard"):
        _cmd_wizard(session)

    else:
        pe(f"Desconocido: {v}  —  /help")
    return True


# ── Helpers de lectura/escritura de archivos de estado ────────────────────────
AGENTS_FILE    = Path(__file__).parent.parent / "state" / "agents_registry.json"
SKILLS_FILE    = Path(__file__).parent.parent / "state" / "skill_registry.json"
ROUTING_FILE_P = Path(__file__).parent.parent / "state" / "model_routing.json"
ORCH_FILE      = Path(__file__).parent.parent / "state" / "model_orchestrator.json"

def _load_json(p):
    try:
        # utf-8-sig handles BOM produced by some Windows editors
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as e:
        pe(f"Error leyendo {p.name}: {e}"); return {}

def _save_json(p, data):
    try:
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception as e:
        pe(f"Error guardando {p.name}: {e}"); return False

# ── Menús navegables — helpers ─────────────────────────────────────────────────
_MENU_STYLE = Style.from_dict({
    "dialog":            "bg:#1e1e2e",
    "dialog.body":       "bg:#1e1e2e fg:#cdd6f4",
    "dialog frame.label":"fg:#89b4fa bold",
    "button":            "bg:#313244 fg:#cdd6f4",
    "button.focused":    "bg:#89b4fa fg:#1e1e2e bold",
    "radio-list":        "bg:#1e1e2e fg:#cdd6f4",
    "radio-selected":    "fg:#a6e3a1 bold",
})

def _menu_select(title, text, values, cancel_label="Cancelar"):
    try:
        return radiolist_dialog(title=title, text=text,
                                values=values, cancel_text=cancel_label,
                                style=_MENU_STYLE).run()
    except Exception:
        return None

def _menu_action(title, text, buttons):
    try:
        return button_dialog(title=title, text=text,
                             buttons=buttons, style=_MENU_STYLE).run()
    except Exception:
        return None

def _menu_input(title, text, default=""):
    try:
        return input_dialog(title=title, text=text,
                            default=default, style=_MENU_STYLE).run()
    except Exception:
        return None

def _menu_confirm(title, text):
    try:
        return yes_no_dialog(title=title, text=text, style=_MENU_STYLE).run()
    except Exception:
        return False

# ── /agents ───────────────────────────────────────────────────────────────────
def _cmd_agents(arg):
    data = _load_json(AGENTS_FILE)
    agents = {k: v for k, v in data.items() if not k.startswith("_")}
    parts = arg.split(None, 1)
    direct = parts[0] if parts and parts[0] in agents else None

    while True:
        if not direct:
            choices = [(name,
                        f"{'[ON]' if ag.get('active') else '[--]'} {name}  |  "
                        f"{ag.get('model','?')}  |  {', '.join(ag.get('skills',[]))}")
                       for name, ag in agents.items()]
            choices += [("__add__", "+ Crear nuevo agente"), ("__exit__", "Salir")]
            sel = _menu_select("BAGO / Agentes", "Selecciona un agente:", choices)
            if sel is None or sel == "__exit__": break
            if sel == "__add__":
                _agents_create(data, agents)
                data = _load_json(AGENTS_FILE)
                agents = {k: v for k, v in data.items() if not k.startswith("_")}
                continue
            direct = sel

        ag = agents.get(direct, {})
        activo = ag.get("active", True)
        info = (f"Modelo:    {ag.get('model','?')}\n"
                f"Skills:    {', '.join(ag.get('skills',[]))}\n"
                f"Fase:      {ag.get('phase','?')}\n"
                f"Categoria: {ag.get('category','?')}\n"
                f"Desc:      {ag.get('description','')}\n"
                f"Activo:    {'SI' if activo else 'NO'}")
        action = _menu_action(f"Agente: {direct}", info,
                              [("Editar", "edit"), ("Activar/Desactivar", "toggle"),
                               ("Eliminar", "delete"), ("Volver", "back")])
        if action == "back" or action is None:
            direct = None; continue
        if action == "toggle":
            agents[direct]["active"] = not activo
            data.update(agents)
            _save_json(AGENTS_FILE, data)
            pi(f"Agente '{direct}': {'ACTIVO' if agents[direct]['active'] else 'INACTIVO'}")
            direct = None; continue
        if action == "delete":
            if _menu_confirm("Eliminar agente", f"Eliminar '{direct}'?"):
                del data[direct]
                _save_json(AGENTS_FILE, data)
                pi(f"Agente '{direct}' eliminado.")
                agents = {k: v for k, v in data.items() if not k.startswith("_")}
            direct = None; continue
        if action == "edit":
            _agents_edit(data, agents, direct)
            data = _load_json(AGENTS_FILE)
            agents = {k: v for k, v in data.items() if not k.startswith("_")}
            direct = None; continue
        direct = None

def _agents_create(data, agents):
    name = _menu_input("Nuevo agente", "Nombre del agente:")
    if not name or name in agents: pe("Nombre vacio o ya existe."); return
    model = _menu_input("Modelo", "Modelo LLM:", default="qwen2.5:0.5b") or "qwen2.5:0.5b"
    skills_raw = _menu_input("Skills", "Skills (separadas por coma):") or ""
    desc = _menu_input("Descripcion", "Descripcion breve:") or f"Agente {name}"
    agents[name] = {"phase": 0, "skills": [s.strip() for s in skills_raw.split(",") if s.strip()],
                    "category": "general", "description": desc, "active": True, "model": model}
    data.update(agents)
    if _save_json(AGENTS_FILE, data): pi(f"Agente '{name}' creado.")

def _agents_edit(data, agents, name):
    ag = agents[name]
    fields = [
        ("model",       f"model       = {ag.get('model','?')}"),
        ("skills",      f"skills      = {', '.join(ag.get('skills',[]))}"),
        ("description", f"description = {ag.get('description','')}"),
        ("category",    f"category    = {ag.get('category','?')}"),
        ("phase",       f"phase       = {ag.get('phase','?')}"),
    ]
    field = _menu_select(f"Editar: {name}", "Campo a editar:", fields)
    if not field: return
    new_val = _menu_input(f"Editar {field}", f"Nuevo valor para '{field}':",
                          default=str(ag.get(field, "")))
    if new_val is None: return
    if field == "skills":   new_val = [s.strip() for s in new_val.split(",") if s.strip()]
    elif field == "phase":
        try: new_val = int(new_val)
        except: pass
    agents[name][field] = new_val
    data.update(agents)
    if _save_json(AGENTS_FILE, data): pi(f"Agente '{name}': {field} actualizado.")

# ── /skills ───────────────────────────────────────────────────────────────────
def _cmd_skills(arg):
    data = _load_json(SKILLS_FILE)
    parts = arg.split(None, 1)
    direct = parts[0] if parts and parts[0] in data else None

    while True:
        if not direct:
            choices = [(name,
                        f"{name}  |  cat:{sk.get('category','?')}  |  {sk.get('description','')[:50]}")
                       for name, sk in data.items()]
            choices += [("__add__", "+ Crear nueva skill"), ("__exit__", "Salir")]
            sel = _menu_select("BAGO / Skills", "Selecciona una skill:", choices)
            if sel is None or sel == "__exit__": break
            if sel == "__add__":
                _skills_create(data); data = _load_json(SKILLS_FILE); continue
            direct = sel

        sk = data.get(direct, {})
        info = (f"Categoria: {sk.get('category','?')}\n"
                f"Fase:      {sk.get('phase','?')}\n"
                f"Steps:     {sk.get('steps',[])}\n"
                f"Desc:      {sk.get('description','')}")
        action = _menu_action(f"Skill: {direct}", info,
                              [("Editar", "edit"), ("Eliminar", "delete"), ("Volver", "back")])
        if action == "back" or action is None: direct = None; continue
        if action == "delete":
            if _menu_confirm("Eliminar skill", f"Eliminar '{direct}'?"):
                del data[direct]; _save_json(SKILLS_FILE, data); pi(f"Skill '{direct}' eliminada.")
            direct = None; continue
        if action == "edit":
            _skills_edit(data, direct); data = _load_json(SKILLS_FILE); direct = None; continue
        direct = None

def _skills_create(data):
    name = _menu_input("Nueva skill", "Nombre de la skill:")
    if not name or name in data: pe("Nombre vacio o ya existe."); return
    cat  = _menu_input("Categoria", "Categoria:", default="general") or "general"
    desc = _menu_input("Descripcion", "Descripcion:") or f"Skill {name}"
    data[name] = {"steps": [], "phase": 0, "category": cat, "description": desc}
    if _save_json(SKILLS_FILE, data): pi(f"Skill '{name}' creada.")

def _skills_edit(data, name):
    sk = data[name]
    fields = [
        ("description", f"description = {sk.get('description','')}"),
        ("category",    f"category    = {sk.get('category','?')}"),
        ("phase",       f"phase       = {sk.get('phase','?')}"),
        ("steps",       f"steps       = {sk.get('steps',[])}"),
    ]
    field = _menu_select(f"Editar skill: {name}", "Campo a editar:", fields)
    if not field: return
    new_val = _menu_input(f"Editar {field}", "Nuevo valor:", default=str(sk.get(field, "")))
    if new_val is None: return
    if field == "steps":
        try: new_val = [int(x.strip()) for x in new_val.split(",") if x.strip()]
        except: pass
    elif field == "phase":
        try: new_val = int(new_val)
        except: pass
    data[name][field] = new_val
    if _save_json(SKILLS_FILE, data): pi(f"Skill '{name}': {field} actualizado.")

# ── /routing ──────────────────────────────────────────────────────────────────
def _cmd_routing(arg):
    data = _load_json(ROUTING_FILE_P)

    while True:
        rules = data.get("rules", [])
        fb    = data.get("fallback", {})
        choices = [(r["id"],
                    f"#{i+1:02d}  {r['id']:<22}  {r.get('provider','?')}/{r.get('model','?')}")
                   for i, r in enumerate(rules)]
        choices += [
            ("__add__",      "+ Aniadir regla"),
            ("__fallback__", f"* Fallback: {fb.get('provider','?')} / {fb.get('model','?')}"),
            ("__exit__",     "Salir"),
        ]
        sel = _menu_select("BAGO / Routing Matrix",
                           "Selecciona una regla (flechas + Enter):", choices)
        if sel is None or sel == "__exit__": break

        if sel == "__add__":
            _routing_add(data); continue

        if sel == "__fallback__":
            prov  = _menu_input("Fallback provider", "Provider:", default=fb.get("provider","codex"))
            if prov is None: continue
            model = _menu_input("Fallback model", "Modelo:", default=fb.get("model","gpt-5.4"))
            if model is None: continue
            data["fallback"] = {"provider": prov, "model": model}
            _save_json(ROUTING_FILE_P, data); pi(f"Fallback: {prov} / {model}"); continue

        rule = next((r for r in rules if r["id"] == sel), None)
        if not rule: continue
        idx  = next(i for i, r in enumerate(rules) if r["id"] == sel)
        info = (f"Keywords:  {rule.get('keywords','')}\n"
                f"Provider:  {rule.get('provider','?')}\n"
                f"Modelo:    {rule.get('model','?')}\n"
                f"Razon:     {rule.get('reason','')}")
        action = _menu_action(f"Regla: {sel}", info,
                              [("Editar", "edit"), ("Subir", "up"),
                               ("Bajar", "down"), ("Eliminar", "delete"), ("Volver", "back")])
        if action == "back" or action is None: continue
        if action == "delete":
            if _menu_confirm("Eliminar regla", f"Eliminar '{sel}'?"):
                data["rules"] = [r for r in rules if r["id"] != sel]
                _save_json(ROUTING_FILE_P, data); pi(f"Regla '{sel}' eliminada.")
            continue
        if action == "up" and idx > 0:
            rules[idx], rules[idx-1] = rules[idx-1], rules[idx]
            data["rules"] = rules; _save_json(ROUTING_FILE_P, data)
            pi(f"Regla '{sel}' -> posicion {idx}"); continue
        if action == "down" and idx < len(rules)-1:
            rules[idx], rules[idx+1] = rules[idx+1], rules[idx]
            data["rules"] = rules; _save_json(ROUTING_FILE_P, data)
            pi(f"Regla '{sel}' -> posicion {idx+2}"); continue
        if action == "edit":
            _routing_edit(data, sel); data = _load_json(ROUTING_FILE_P)

def _routing_add(data):
    rid = _menu_input("Nueva regla", "ID de la regla (slug):")
    if not rid: return
    if any(r.get("id") == rid for r in data.get("rules", [])):
        pe(f"Regla '{rid}' ya existe."); return
    keywords = _menu_input("Keywords", "Palabras clave (separadas por espacio):") or ""
    provider = _menu_select("Provider", "Provider:", [
        ("codex","codex - GPT/OpenAI"),
        ("copilot","copilot - GitHub Copilot"),
        ("ollama-local","ollama-local - Local"),
        ("ollama-cloud","ollama-cloud - Nube"),
        ("anthropic","anthropic - Claude"),
    ]) or "codex"
    model  = _menu_input("Modelo", "Nombre del modelo:", default="gpt-5.4") or "gpt-5.4"
    reason = _menu_input("Razon", "Razon/descripcion:") or "Regla personalizada"
    data.setdefault("rules", []).append(
        {"id": rid, "keywords": keywords, "provider": provider, "model": model, "reason": reason})
    if _save_json(ROUTING_FILE_P, data): pi(f"Regla '{rid}' aniadida.")

def _routing_edit(data, rid):
    rule = next((r for r in data.get("rules", []) if r["id"] == rid), None)
    if not rule: return
    fields = [
        ("keywords", f"keywords = {rule.get('keywords','')}"),
        ("provider", f"provider = {rule.get('provider','?')}"),
        ("model",    f"model    = {rule.get('model','?')}"),
        ("reason",   f"reason   = {rule.get('reason','')}"),
    ]
    field = _menu_select(f"Editar regla: {rid}", "Campo a editar:", fields)
    if not field: return
    new_val = _menu_input(f"Editar {field}", "Nuevo valor:", default=str(rule.get(field, "")))
    if new_val is None: return
    rule[field] = new_val
    if _save_json(ROUTING_FILE_P, data): pi(f"Regla '{rid}': {field} actualizado.")

# ── /roles ────────────────────────────────────────────────────────────────────
def _cmd_roles(arg):
    data  = _load_json(ORCH_FILE)
    modes = data.get("modes", {})
    tasks = data.get("task_preference", {})

    root_choices = [
        ("modes", "Modos del orquestador  (offline / economico / estandar / full)"),
        ("tasks", "Preferencias por tipo de tarea"),
    ]
    section = _menu_select("BAGO / Roles", "Que seccion quieres ver?", root_choices)
    if not section: return

    if section == "modes":
        while True:
            choices = [(name,
                        f"{name:<12}  providers: {', '.join(m.get('allowed_providers',[]))}")
                       for name, m in modes.items()]
            choices.append(("__exit__", "Volver"))
            sel = _menu_select("Modos del orquestador", "Selecciona un modo:", choices)
            if sel is None or sel == "__exit__": break
            m = modes[sel]
            info = (f"Descripcion:    {m.get('description','')}\n"
                    f"Providers:      {', '.join(m.get('allowed_providers',[]))}\n"
                    f"Modelo default: {m.get('default_model','?')}\n"
                    f"Fallback chain: {' -> '.join(m.get('fallback_chain',[]))}")
            _menu_action(f"Modo: {sel}", info, [("OK", "ok")])

    elif section == "tasks":
        while True:
            choices = [(name,
                        f"{name:<20}  {', '.join(tk.get('models',[]))}")
                       for name, tk in tasks.items()]
            choices.append(("__exit__", "Volver"))
            sel = _menu_select("Preferencias por tarea", "Selecciona una tarea:", choices)
            if sel is None or sel == "__exit__": break
            tk = tasks[sel]
            info = (f"Modelos:  {', '.join(tk.get('models',[]))}\n"
                    f"Razon:    {tk.get('reason','')}")
            _menu_action(f"Tarea: {sel}", info, [("OK", "ok")])

# ── Fabrica de piezas BAGO — Wizard con LM ────────────────────────────────────
# Prompts de sistema para generar cada tipo de pieza
_WIZARD_PROMPTS = {
    "agent": """\
Eres el constructor de agentes BAGO. El usuario describe un agente y tu generas
el JSON de definicion exacto para agents_registry.json.
Responde SOLO con JSON valido, sin explicacion, sin markdown, sin bloques de codigo.
Esquema requerido:
{
  "name": "agent_<slug>",
  "phase": <0-11>,
  "skills": ["<skill_id>", ...],
  "category": "<tools|tests|docs|ops|music|general>",
  "description": "<descripcion breve>",
  "active": true,
  "model": "<nombre_modelo>"
}
Modelos disponibles: qwen2.5:0.5b, claude-sonnet-4.6, claude-haiku-4.5,
claude-opus-4.7, gpt-5.4, gpt-5.4-mini, gpt-5.5, gpt-5.3-codex.
Elige el modelo mas adecuado para el rol descrito.
Skills existentes: code_review, test_runner, doc_writer.
Si necesitas una skill nueva, incluye su id en la lista igualmente.""",

    "skill": """\
Eres el constructor de skills BAGO. El usuario describe una skill y tu generas
el JSON de definicion exacto para skill_registry.json.
Responde SOLO con JSON valido, sin explicacion, sin markdown, sin bloques de codigo.
Esquema requerido:
{
  "name": "<skill_slug>",
  "steps": [<lista de indices enteros 0-11>],
  "phase": <0-11>,
  "category": "<tools|tests|docs|ops|music|general>",
  "description": "<descripcion de lo que hace la skill>"
}
Los steps son indices de pasos del ciclo espiral BAGO (0=SENSE, 1=FILTER, 2=PLAN,
3=SELECT, 4=ACT, 5=GENERATE, 6=REVIEW, 7=VALIDATE, 8=OBSERVE, 9=RECORD,
10=LEARN, 11=DECIDE). Incluye los steps relevantes para esta skill.""",

    "role": """\
Eres el constructor de roles/modos del orquestador BAGO. El usuario describe
un modo de operacion y tu generas el JSON para model_orchestrator.json -> modes.
Responde SOLO con JSON valido, sin explicacion, sin markdown, sin bloques de codigo.
Esquema requerido:
{
  "name": "<nombre_modo>",
  "description": "<descripcion del modo>",
  "allowed_providers": ["<provider1>", ...],
  "default_model": "<modelo>",
  "fallback_chain": ["<modelo1>", "<modelo2>", ...]
}
Providers disponibles: ollama-local, ollama-cloud, copilot, codex, anthropic.
Modelos: qwen2.5:0.5b, claude-sonnet-4.6, claude-opus-4.7, gpt-5.4, gpt-5.5,
         gpt-5.3-codex, gpt-5.4-mini, kimi-k2-1t.""",

    "routing": """\
Eres el constructor de reglas de routing BAGO. El usuario describe una regla
y tu generas el JSON para model_routing.json -> rules[].
Responde SOLO con JSON valido, sin explicacion, sin markdown, sin bloques de codigo.
Esquema requerido:
{
  "id": "<slug_unico>",
  "keywords": "<palabras clave separadas por espacio>",
  "provider": "<copilot|codex|ollama-local|ollama-cloud|anthropic>",
  "model": "<nombre_modelo>",
  "reason": "<por que este modelo para estas keywords>"
}
Elige el provider y modelo mas adecuado para las tareas descritas.""",

    "task_pref": """\
Eres el constructor de preferencias de tarea BAGO. El usuario describe un tipo
de tarea y tu generas el JSON para model_orchestrator.json -> task_preference.
Responde SOLO con JSON valido, sin explicacion, sin markdown, sin bloques de codigo.
Esquema requerido:
{
  "name": "<task_slug>",
  "models": ["<modelo1>", "<modelo2>"],
  "reason": "<por que estos modelos para este tipo de tarea>"
}
Modelos disponibles: qwen2.5:0.5b, claude-sonnet-4.6, claude-opus-4.7, gpt-5.4,
gpt-5.5, gpt-5.3-codex, gpt-5.4-mini, kimi-k2-1t.""",
}

def _wizard_call_lm(session, kind, description):
    """Llama al LM con el prompt de fabrica y devuelve el dict generado o None."""
    sys_prompt = _WIZARD_PROMPTS[kind]
    lm, kw = session.litellm_info
    messages = [
        {"role": "system",  "content": sys_prompt},
        {"role": "user",    "content": description},
    ]
    with console.status(f"  [dim cyan]Generando {kind}...[/dim cyan]", spinner="dots"):
        try:
            raw = _llm_call(lm, kw, messages)
        except Exception as e:
            pe(f"LM error: {e}"); return None

    # Extraer JSON — el LM puede envolver en ``` a veces
    text = raw.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
        if text.endswith("```"):
            text = text[:-3].strip()
    try:
        return json.loads(text)
    except Exception:
        # Intentar buscar primer { ... }
        try:
            start = text.index("{"); end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except Exception:
            pe(f"LM devolvio JSON invalido:\n{raw[:300]}")
            return None

def _wizard_review_dict(title, d):
    """Muestra los campos generados por LM y permite editar campo a campo."""
    while True:
        # Muestra campos editables (excluye 'name' de la lista — se edita aparte)
        editable = [(k, f"{k} = {v}") for k, v in d.items() if k != "name"]
        editable += [("__confirm__", "✓ Confirmar y guardar"),
                     ("__cancel__", "✗ Cancelar")]

        field = _menu_select(
            title,
            f"Revisa los campos generados por el LM.\nSelecciona uno para editar o confirma:",
            editable)

        if field is None or field == "__cancel__":
            return None
        if field == "__confirm__":
            return d

        current = str(d.get(field, ""))
        new_val = _menu_input(f"Editar: {field}", f"Valor actual:", default=current)
        if new_val is None:
            continue
        # Conversiones de tipo
        if field in ("skills", "models", "fallback_chain", "allowed_providers", "steps"):
            try:
                parsed = json.loads(new_val)
                if isinstance(parsed, list):
                    new_val = parsed
                else:
                    new_val = [x.strip() for x in new_val.split(",") if x.strip()]
            except Exception:
                new_val = [x.strip() for x in new_val.split(",") if x.strip()]
        elif field == "phase":
            try: new_val = int(new_val)
            except: pass
        elif field == "active":
            new_val = new_val.lower() in ("true", "si", "yes", "1")
        d[field] = new_val

def _cmd_wizard(session):
    """Fabrica de piezas BAGO asistida por LM. /new | /wizard | /fabrica"""
    kind_choices = [
        ("agent",    "Agente BAGO  — define rol, modelo, skills, fase"),
        ("skill",    "Skill BAGO   — define capacidad reutilizable con steps espirales"),
        ("role",     "Modo/Rol del orquestador  — offline / economico / custom"),
        ("routing",  "Regla de routing  — keywords → provider/modelo"),
        ("task_pref","Preferencia de tarea  — tipo de tarea → modelos recomendados"),
    ]
    kind = _menu_select("BAGO / Fabrica de Piezas",
                        "Que tipo de pieza quieres construir?", kind_choices)
    if not kind: return

    desc = _menu_input(
        f"Describe tu {kind}",
        f"Describe en lenguaje natural lo que necesitas.\n"
        f"El LM generara la definicion completa:",
        default="")
    if not desc or not desc.strip(): return

    result = _wizard_call_lm(session, kind, desc)
    if not result:
        pe("El LM no pudo generar una definicion valida."); return

    # Pedir nombre si no viene en el resultado
    name_field = {"agent": "name", "skill": "name", "role": "name",
                  "routing": "id", "task_pref": "name"}.get(kind, "name")
    if name_field not in result or not result.get(name_field):
        suggested = desc.lower().replace(" ", "_")[:20]
        name_val = _menu_input("Nombre / ID",
                               f"El LM no propuso un nombre. Introduce el {name_field}:",
                               default=suggested)
        if not name_val: return
        result[name_field] = name_val

    # Revisión interactiva campo a campo
    title = f"Fabrica > {kind}: {result.get(name_field, '?')}"
    confirmed = _wizard_review_dict(title, result)
    if confirmed is None:
        pi("Wizard cancelado."); return

    # Guardar en el archivo correspondiente
    _wizard_save(kind, confirmed)

def _wizard_save(kind, d):
    """Persiste la pieza generada en el JSON de estado correspondiente."""
    if kind == "agent":
        data = _load_json(AGENTS_FILE)
        name = d.pop("name", None) or d.get("name", "agent_nuevo")
        # Asegurarse de que empieza por "agent_"
        if not name.startswith("agent_"):
            name = "agent_" + name
        data[name] = d
        if _save_json(AGENTS_FILE, data):
            pi(f"Agente '{name}' guardado en agents_registry.json")

    elif kind == "skill":
        data = _load_json(SKILLS_FILE)
        name = d.pop("name", None) or "skill_nueva"
        data[name] = d
        if _save_json(SKILLS_FILE, data):
            pi(f"Skill '{name}' guardada en skill_registry.json")

    elif kind == "role":
        data = _load_json(ORCH_FILE)
        name = d.pop("name", None) or "modo_nuevo"
        data.setdefault("modes", {})[name] = d
        if _save_json(ORCH_FILE, data):
            pi(f"Modo '{name}' guardado en model_orchestrator.json")

    elif kind == "routing":
        data = _load_json(ROUTING_FILE_P)
        rid = d.get("id", "regla_nueva")
        # Evitar duplicados
        data["rules"] = [r for r in data.get("rules", []) if r.get("id") != rid]
        data["rules"].append(d)
        if _save_json(ROUTING_FILE_P, data):
            pi(f"Regla '{rid}' guardada en model_routing.json (posicion {len(data['rules'])})")

    elif kind == "task_pref":
        data = _load_json(ORCH_FILE)
        name = d.pop("name", None) or "tarea_nueva"
        data.setdefault("task_preference", {})[name] = d
        if _save_json(ORCH_FILE, data):
            pi(f"Preferencia de tarea '{name}' guardada en model_orchestrator.json")
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
