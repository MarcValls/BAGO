
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
PROVIDERS_FILE  = STATE_DIR / "model_providers.json"
ROUTING_FILE    = STATE_DIR / "model_routing.json"
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

  [bold cyan]Fábrica de artefactos BAGO (asistida por LM):[/bold cyan]
  [yellow]/new[/yellow]  (alias: /wizard, /fabrica)
    Wizard: describes en lenguaje natural, el LM genera la definición completa.
    7 tipos de artefacto organizados en 3 categorías:
      🧠 INTELIGENCIA : Agente · Skill
      ⚡ SPRINT/NEURAL : Nodo Neural (toolbox de sprint)
      🔀 ORQUESTACIÓN : Regla routing · Preferencia tarea · Modo orquestador
      🔧 HERRAMIENTAS : Tool Python (genera script con main() listo)

  [bold cyan]Roles / Modos del orquestador:[/bold cyan]
  [yellow]/roles[/yellow]                            Ver modos (offline/economico/estandar/full)
  [yellow]/roles <modo>[/yellow]                     Detalle de un modo
  [yellow]/roles tasks[/yellow]                      Ver preferencias por tipo de tarea
  [yellow]/roles tasks <tarea>[/yellow]              Ver tarea concreta

  [bold cyan]Sesion, Auth, Auto, Modo, Sync, Memoria, Config:[/bold cyan]
  [yellow]/session[/yellow]    Gestion de sesion (temporal/disco, load, repliegue, letargo)
  [yellow]/auth[/yellow]       Auth + providers (superset de /login)
  [yellow]/auto[/yellow]       Modo autonomo y nivel de confirmaciones
  [yellow]/mode[/yellow]       Cambio rapido del modo del orquestador
  [yellow]/plan[/yellow]       Alterna modo PLAN (proponer plan antes de actuar)
  [yellow]/brainstorm[/yellow] Alterna modo BRAINSTORM (expansion libre de ideas)
  [yellow]/sync[/yellow]       Sincronizar GitHub/USB + post-sync (repliegue/letargo)
  [yellow]/memory[/yellow]     Base de conocimiento + memoria episodica
  [yellow]/config[/yellow]     Configuracion global persistente

  [bold cyan]Framework y Proyectos:[/bold cyan]
  [yellow]/framework[/yellow]  Vista evolutiva del framework BAGO (sprint, health, ideas, componentes)
  [yellow]/workspaces[/yellow] Gestion de workspaces (un workspace contiene muchos proyectos)
  [yellow]/projects[/yellow]   Gestion de proyectos (dentro del workspace activo)

  [bold cyan]Sesion:[/bold cyan]
  [yellow]/status[/yellow]   Estado actual   [yellow]/save[/yellow]  Guardar sesion
  [yellow]/clear[/yellow]    Limpiar historial   [yellow]/exit[/yellow]  Salir

[dim]El orquestador decide automaticamente que modelo/s usar y con que estrategia.[/dim]
"""
