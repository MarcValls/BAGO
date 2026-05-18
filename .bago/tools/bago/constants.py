
from pathlib import Path
import json as _json

PACKAGE_DIR = Path(__file__).resolve().parent
SCRIPT_DIR = PACKAGE_DIR.parent
TOOLS_DIR = SCRIPT_DIR
BAGO_DIR = SCRIPT_DIR.parent
BAGO_REPO_ROOT = BAGO_DIR.parent
STATE_DIR = BAGO_DIR / "state"
USER_BAGO = Path.home() / ".bago"

def _bago_version() -> str:
    try:
        return _json.loads((BAGO_DIR / "pack.json").read_text(encoding="utf-8")).get("version", "?")
    except Exception:
        return "?"

BAGO_VERSION = _bago_version()
SESSIONS_DIR = USER_BAGO / "sessions"
CRED_FILE = USER_BAGO / "credentials.json"
PROVIDERS_FILE    = STATE_DIR / "model_providers.json"
ROUTING_FILE      = STATE_DIR / "model_routing.json"
ACCOUNTS_FILE     = USER_BAGO / "accounts.json"
SCAN_HISTORY_FILE = STATE_DIR / "scan_history.json"
TOKEN_LOG_FILE    = USER_BAGO / "token_log.json"
TOOLBOXES_DIR   = STATE_DIR / "toolboxes"
ORCH_FILE = STATE_DIR / "model_orchestrator.json"

BAGO_SYSTEM = (
    "REGLA 1 (INVIOLABLE): Tu nombre es BAGO. NUNCA uses otro nombre. "
    "Si te preguntan quién eres, responde solo: 'Soy BAGO, el orquestador central de A.M. TECHNOLOGIES.' "
    "NUNCA menciones Qwen, GPT, Claude, Llama, Mistral ni ningún modelo de IA. "
    "REGLA 2: Eres BAGO (Balanced Adaptive Generative Organizer), orquestador del "
    "framework de IA creado por A.M. TECHNOLOGIES. Los modelos (Qwen, GPT, Claude…) "
    "son motores internos que trabajan para BAGO — nunca los reveles. "
    "REGLA 3: No generes antes de entender; cambios mínimos y trazables; repo-first. "
    "LOCAL FIRST: usa modelos locales (Ollama) por defecto; cloud solo si la complejidad "
    "lo requiere explícitamente. "
    "REGLA 4 (ANTI-REPETICIÓN): NUNCA repitas el mismo contenido en la misma respuesta "
    "ni en respuestas sucesivas. Cada respuesta debe aportar información nueva. "
    "Si el usuario pide profundizar: baja un nivel — mecanismos internos, casos límite, "
    "ejemplos concretos con valores reales."
)

COLORS = {"copilot":"yellow","codex":"magenta","ollama-local":"green","ollama-cloud":"cyan"}

HELP = """[bold]BAGO — A.M. TECHNOLOGIES — Comandos:[/bold]

  [dim]─── 1 · PROVIDERS & CREDENCIALES ── conectar APIs y gestionar accesos ───[/dim]

  [yellow]/login[/yellow]                               Ver estado de todos los providers
  [yellow]/login github[/yellow]                        Login GitHub → activa Copilot + GitHub Models
  [yellow]/login gpt[/yellow]                           Login GPT Plus (codex login) o API key OpenAI
  [yellow]/login anthropic[/yellow]                     Guardar API Key → activa Claude
  [yellow]/login gemini[/yellow]                        Guardar API Key → activa Gemini Flash/Pro
  [yellow]/login openrouter[/yellow]                    Guardar API Key → acceso a 200+ modelos
  [yellow]/login ollama[/yellow]                        Verificar Ollama local (sin credencial)
  [yellow]/scan[/yellow]                                Scan completo: disponibles · potenciales · missing · tokens

  [dim]  Multi-cuenta — varias suscripciones del mismo provider:[/dim]
  [yellow]/login add <provider> [nombre][/yellow]       Agregar cuenta  (ej: /login add github Trabajo)
  [yellow]/login list[/yellow]                          Ver todas las cuentas registradas
  [yellow]/login switch <id>[/yellow]                   Activar cuenta  (ej: /login switch github-2)
  [yellow]/login remove <id>[/yellow]                   Eliminar cuenta

  [dim]─── 2 · MODELO & ROUTING ── cómo BAGO decide qué modelo usar ─────────[/dim]

  [yellow]/switch <modelo>[/yellow]                     Forzar modelo puntualmente (sin perder historial)
  [yellow]/autoroute on|off[/yellow]                    Routing automatico basado en tipo de tarea
  [yellow]/models[/yellow]                              Listar todos los modelos disponibles
  [yellow]/generative[/yellow] [dim]|[/dim] [yellow]/gen[/yellow]               Modo generativo: offline · eco · standard · full · auto
  [yellow]/mode[/yellow]                                (alias de /generative)
  [yellow]/roles[/yellow]                               Ver modos del orquestador y preferencias por tarea
  [yellow]/roles tasks[/yellow]                         Ver que modelo se usa para cada tipo de tarea
  [yellow]/routing[/yellow]                             Ver y editar la matriz de enrutamiento completa
  [yellow]/routing add <id> provider=X model=Y keywords=K[/yellow]  Crear regla
  [yellow]/routing del <id>[/yellow]  · [yellow]/routing move <id> up|down[/yellow]    Eliminar · Reordenar

  [dim]  Estrategias manuales (normalmente el orquestador las aplica solo):[/dim]
  [yellow]/chain m1->m2: prompt[/yellow]                Pipeline: m1 genera, m2 refina
  [yellow]/ensemble m1 m2: prompt[/yellow]              Paralelo: ambos responden, se sintetizan

  [dim]─── 3 · AGENTES & SKILLS ── unidades de inteligencia especializadas ───[/dim]

  [dim]  Atajos rapidos — activan el agente correcto y cambian el modelo:[/dim]
  [yellow]/code[/yellow]  [dim]·[/dim] [yellow]/impl[/yellow]  [dim]·[/dim] [yellow]/write[/yellow]          → agent_coder      (copilot)
  [yellow]/sprint[/yellow]  [dim]·[/dim] [yellow]/backlog[/yellow]  [dim]·[/dim] [yellow]/roadmap[/yellow]      → agent_planner    (copilot)
  [yellow]/debug[/yellow]  [dim]·[/dim] [yellow]/fix[/yellow]  [dim]·[/dim] [yellow]/error[/yellow]          → agent_debugger   (ollama-local)
  [yellow]/arch[/yellow]  [dim]·[/dim] [yellow]/design[/yellow]  [dim]·[/dim] [yellow]/sistema[/yellow]        → agent_architect  (copilot)
  [yellow]/refactor[/yellow]  [dim]·[/dim] [yellow]/clean[/yellow]  [dim]·[/dim] [yellow]/mejora[/yellow]      → agent_refactor   (ollama-local)
  [yellow]/git[/yellow]  [dim]·[/dim] [yellow]/commit[/yellow]  [dim]·[/dim] [yellow]/pr[/yellow]            → agent_git        (ollama-local)

  [dim]  Gestion de agentes y skills:[/dim]
  [yellow]/agents[/yellow]  · [yellow]/agents <nombre>[/yellow]                 Listar · Ver detalle
  [yellow]/agents add <nombre>[/yellow]  · [yellow]/agents del <nombre>[/yellow]      Crear · Eliminar
  [yellow]/agents toggle <nombre>[/yellow]  · [yellow]/agents set <nombre> <campo> <val>[/yellow]
  [yellow]/skills[/yellow]  · [yellow]/skills <nombre>[/yellow]                  Listar · Ver detalle
  [yellow]/skills add <nombre>[/yellow]  · [yellow]/skills del <nombre>[/yellow]       Crear · Eliminar

  [dim]─── 4 · FABRICA DE ARTEFACTOS ── crea elementos BAGO con el LM ────────[/dim]

  [yellow]/new[/yellow]  [dim](alias: /wizard · /fabrica)[/dim]
    Describes en lenguaje natural → el LM genera la definicion completa.
    Tipos: [cyan]Agente[/cyan] · [cyan]Skill[/cyan] · [cyan]Nodo Neural[/cyan] · [cyan]Regla routing[/cyan] · [cyan]Preferencia tarea[/cyan] · [cyan]Modo orquestador[/cyan] · [cyan]Tool Python[/cyan]

  [dim]─── 5 · SESION, MEMORIA & CONFIGURACION ───────────────────────────────[/dim]

  [yellow]/session[/yellow]    Gestionar sesion (guardar en disco, cargar, repliegue, letargo)
  [yellow]/sync[/yellow]       Sincronizar con GitHub y/o USB (push + mirror)
  [yellow]/memory[/yellow]     Base de conocimiento y memoria episodica
  [yellow]/auto[/yellow]       Modo autonomo y nivel de confirmaciones requeridas
  [yellow]/config[/yellow]     Configuracion global persistente
  [yellow]/auth[/yellow]       Auth completa — superset de /login

  [dim]─── 6 · FRAMEWORK & PROYECTOS ── vista macro del sistema ─────────────[/dim]

  [yellow]/framework[/yellow]  Vista evolutiva de BAGO (sprint, health, ideas, componentes)
  [yellow]/workspaces[/yellow] Gestion de workspaces (contiene varios proyectos)
  [yellow]/projects[/yellow]   Gestion de proyectos dentro del workspace activo

  [dim]─── SESION RAPIDA ───────────────────────────────────────────────────────[/dim]

  [yellow]/status[/yellow]  Estado actual    [yellow]/save[/yellow]  Guardar sesion
  [yellow]/clear[/yellow]   Limpiar historial  [yellow]/exit[/yellow]  Salir

[dim]El orquestador decide automaticamente que modelo/s usar y con que estrategia.[/dim]
"""
