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
    """Devuelve (model, wire, provider) para la tarea dada según las reglas de routing."""
    tl = task.lower()
    for rule in routing.get("rules", []):
        for kw in rule.get("keywords", []):
            if kw.lower() in tl:
                prov  = rule["provider"]
                model = rule["model"]
                wire  = providers.get(prov,{}).get("models",{}).get(model,{}).get("wire_name", model)
                matched_kw = kw
                return model, wire, prov, matched_kw
    fb = routing.get("fallback", {})
    return fb.get("model","gpt-5.4"), fb.get("model","gpt-5.4"), fb.get("provider","codex"), None

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
        self.autoroute  = True   # routing automatico por mensaje activo por defecto

    @property
    def litellm_info(self): return resolve_litellm(self.provider, self.wire_name)

    def switch_model(self, target, silent=False):
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
        if silent: return None
        return f"Cambiado: {old} -> {name} ({prov}) | {len(self.history)-1} msgs mantenidos"

    def auto_route(self, user_input):
        """Analiza el mensaje y cambia al modelo mas adecuado si difiere del actual.
        Devuelve (switched: bool, reason: str|None)."""
        name, wire, prov, kw = route_by_task(user_input, self.routing, self.providers)
        if name and name != self.model_name:
            old = self.model_name
            self.provider, self.model_name, self.wire_name = prov, name, wire
            self.switches += 1
            return True, f"→ auto-route [{kw}] : {old} → {name} ({prov})"
        return False, None

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

  [bold cyan]Multi-modelo:[/bold cyan]
  [yellow]/chain modelo1->modelo2: prompt[/yellow]
    Pipeline secuencial — cada modelo refina la respuesta del anterior
    Ej: /chain codex->copilot: escribe y explica un algoritmo de búsqueda binaria

  [yellow]/ensemble modelo1 modelo2: prompt[/yellow]
    Paralelo — todos responden a la vez, el activo sintetiza lo mejor
    Ej: /ensemble codex copilot: cuál es la mejor forma de manejar errores en Python

  [yellow]/autoroute on|off[/yellow]  Routing automático por mensaje (default: on)
  [yellow]/models[/yellow]    Lista todos los modelos del registry BAGO
  [yellow]/status[/yellow]    Estado: modelo, provider, msgs, tiempo, auto-route
  [yellow]/save[/yellow]      Guarda la sesion en ~/.bago/sessions/
  [yellow]/clear[/yellow]     Limpia historial (mantiene sistema BAGO)
  [yellow]/help[/yellow]      Esta ayuda
  [yellow]/exit[/yellow]      Salir (tambien Ctrl+D)

[dim]Auto-routing: el orquestador analiza cada mensaje y usa el modelo óptimo para esa tarea.[/dim]
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
            f"Switches:  {session.switches}\nTiempo:    {elapsed}\n"
            f"Auto-route: {'ON' if session.autoroute else 'OFF'}",
            title="[bold]Estado[/bold]", box=box.ROUNDED))
    elif v == "/chain":
        # /chain model1->model2->model3: prompt
        if ":" not in a:
            pe("Uso: /chain modelo1->modelo2: tu pregunta aquí")
            pe("  Ej: /chain codex->copilot: escribe y explica este algoritmo")
        else:
            chain_part, prompt_part = a.split(":", 1)
            models = [m.strip() for m in chain_part.split("->") if m.strip()]
            prompt_part = prompt_part.strip()
            if len(models) < 2 or not prompt_part:
                pe("Necesitas al menos 2 modelos y un prompt. Ej: /chain codex->copilot: explica X")
            else:
                pi(f"Chain: {' → '.join(models)}")
                chain_models(session, models, prompt_part)
    elif v == "/ensemble":
        # /ensemble model1 model2 model3: prompt
        if ":" not in a:
            pe("Uso: /ensemble modelo1 modelo2: tu pregunta aquí")
        else:
            models_part, prompt_part = a.split(":", 1)
            models = [m.strip() for m in models_part.split() if m.strip()]
            prompt_part = prompt_part.strip()
            if len(models) < 2 or not prompt_part:
                pe("Necesitas al menos 2 modelos y un prompt.")
            else:
                pi(f"Ensemble: {', '.join(models)}")
                ensemble_models(session, models, prompt_part)
    elif v == "/autoroute":
        state = a.lower() if a else ""
        if state == "off":
            session.autoroute = False
            pi("Auto-routing DESACTIVADO — el modelo no cambiará automáticamente.")
        else:
            session.autoroute = True
            pi("Auto-routing ACTIVADO — el orquestador elegirá el modelo por tarea.")
    elif v == "/save":
        pi(f"Guardado: {session.save()}")
    elif v == "/clear":
        session.history = [{"role":"system","content":BAGO_SYSTEM}]
        pi("Historial limpiado. Sistema BAGO mantenido.")
    else:
        pe(f"Comando desconocido: {v}  —  /help")
    return True

# ── Multi-model strategies ────────────────────────────────────────────────────
def _call_model(session, target, messages):
    """Llama a un modelo específico sin modificar el historial principal."""
    old_p, old_m, old_w = session.provider, session.model_name, session.wire_name
    session.switch_model(target, silent=True)
    lm, kw = session.litellm_info
    try:
        r = litellm.completion(model=lm, messages=messages, **kw)
        return r.choices[0].message.content, session.model_name, session.provider
    finally:
        # Restaurar modelo original (el switch en chain/ensemble es temporal por paso)
        session.provider, session.model_name, session.wire_name = old_p, old_m, old_w

def chain_models(session, model_sequence, prompt):
    """Pipeline secuencial: cada modelo ve la respuesta del anterior y la refina.
    Al final añade la respuesta definitiva al historial compartido."""
    context = list(session.history)  # copia del historial actual
    draft = prompt
    steps = []

    for i, target in enumerate(model_sequence):
        step_num = i + 1
        is_last  = (i == len(model_sequence) - 1)

        if i == 0:
            msgs = context + [{"role":"user","content": draft}]
            role_hint = "Responde con detalle."
        else:
            prev_text = steps[-1]["text"]
            role_hint = (
                "A continuación tienes una respuesta preliminar de otro modelo. "
                "Revisala, corrige errores y mejórala. Mantén lo que esté bien.\n\n"
                f"RESPUESTA ANTERIOR:\n{prev_text}\n\n"
                f"PREGUNTA ORIGINAL: {prompt}"
            )
            msgs = [{"role":"system","content": BAGO_SYSTEM},
                    {"role":"user","content": role_hint}]

        old_m = session.model_name
        session.switch_model(target, silent=True)
        lm, kw = session.litellm_info
        c = COLORS.get(session.provider, "white")
        label = f"paso {step_num}/{len(model_sequence)}: {session.model_name}"

        with console.status(f"[dim {c}]{label} ...[/dim {c}]", spinner="dots"):
            try:
                r = litellm.completion(model=lm, messages=msgs, **kw)
                text = r.choices[0].message.content
            except Exception as e:
                text = f"[ERROR en {session.model_name}: {e}]"

        steps.append({"model": session.model_name, "provider": session.provider, "text": text})

        if not is_last:
            # Mostrar borrador intermedio (colapsado)
            console.print(f"  [{c}]✓ {session.model_name}[/{c}] [dim]({len(text)} chars) → siguiente modelo...[/dim]")
        else:
            # Respuesta final completa
            try:    content = Markdown(text)
            except: content = text
            title = f"[bold]CHAIN final[/bold] [{c}]{session.model_name}[/{c}]"
            console.print(Panel(content, title=title, border_style=c, box=box.ROUNDED))
            # Añadir al historial compartido
            session.history.append({"role":"user","content": prompt})
            session.history.append({"role":"assistant","content": text})

    # Dejar el modelo en el último de la cadena
    return steps

def ensemble_models(session, model_list, prompt):
    """Paralelo: varios modelos responden al mismo prompt. El usuario ve todas las respuestas.
    Se añade al historial solo la síntesis (o la mejor si no hay modelo de síntesis)."""
    import concurrent.futures

    context = list(session.history) + [{"role":"user","content": prompt}]
    results = {}

    def call_one(target):
        old_p, old_m, old_w = session.provider, session.model_name, session.wire_name
        session.switch_model(target, silent=True)
        lm, kw = session.litellm_info
        mn, pv = session.model_name, session.provider
        session.provider, session.model_name, session.wire_name = old_p, old_m, old_w
        try:
            r = litellm.completion(model=lm, messages=context, **kw)
            return mn, pv, r.choices[0].message.content
        except Exception as e:
            return mn, pv, f"[ERROR: {e}]"

    console.print(f"  [dim]Consultando {len(model_list)} modelos en paralelo...[/dim]")
    with concurrent.futures.ThreadPoolExecutor() as ex:
        futures = {ex.submit(call_one, t): t for t in model_list}
        for f in concurrent.futures.as_completed(futures):
            mn, pv, text = f.result()
            results[mn] = {"provider": pv, "text": text}
            c = COLORS.get(pv, "white")
            try:    content = Markdown(text)
            except: content = text
            console.print(Panel(content, title=f"[{c}]{mn}[/{c}]", border_style=c, box=box.ROUNDED))

    # Si hay 2+ resultados, ofrecer síntesis con el modelo activo
    if len(results) >= 2:
        pi(f"Sintetizando con {session.model_name}...")
        drafts = "\n\n".join(
            f"[{mn}]:\n{d['text']}" for mn, d in results.items()
        )
        synth_prompt = (
            f"Tienes las siguientes respuestas de distintos modelos para: '{prompt}'\n\n"
            f"{drafts}\n\n"
            "Sintetiza lo mejor de cada una en una respuesta única, coherente y completa."
        )
        lm, kw = session.litellm_info
        with console.status(f"[dim]{session.model_name} sintetizando...[/dim]", spinner="dots"):
            try:
                r = litellm.completion(model=lm, messages=[
                    {"role":"system","content": BAGO_SYSTEM},
                    {"role":"user","content": synth_prompt}
                ], **kw)
                final = r.choices[0].message.content
            except Exception as e:
                final = list(results.values())[0]["text"]  # fallback: primera respuesta
        c = COLORS.get(session.provider, "white")
        try:    content = Markdown(final)
        except: content = final
        console.print(Panel(content, title=f"[bold]SÍNTESIS[/bold] [{c}]{session.model_name}[/{c}]",
                            border_style="bold white", box=box.DOUBLE))
        session.history.append({"role":"user","content": prompt})
        session.history.append({"role":"assistant","content": final})
    else:
        mn, d = next(iter(results.items()))
        session.history.append({"role":"user","content": prompt})
        session.history.append({"role":"assistant","content": d["text"]})

    return results

# ── Chat ──────────────────────────────────────────────────────────────────────
def chat(session, user_input):
    """Envía mensaje al modelo activo. Si auto-routing está activo, puede cambiar modelo antes."""
    # Auto-routing: analizar tarea y cambiar modelo si hay uno mejor
    if session.autoroute:
        switched, reason = session.auto_route(user_input)
        if switched:
            c = COLORS.get(session.provider, "white")
            console.print(f"  [dim {c}]{reason}[/dim {c}]")

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
