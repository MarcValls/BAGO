#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
toolsmith.py — Agente dinámico de cajas de herramientas BAGO.

Asigna, crea y organiza toolboxes para cada agente en cada sprint/tarea.
Si un agente está bloqueado por falta de herramienta, Toolsmith la localiza
o la crea desde una plantilla.

Uso:
    bago toolsmith catalog                          → catálogo completo de grupos
    bago toolsmith assign --task "fix bug en auth"  → toolbox para esta tarea
    bago toolsmith assign --task "..." --agent ANALISTA → toolbox para agente+tarea
    bago toolsmith sprint <sprint_id>               → asigna toolboxes a todos los agentes
    bago toolsmith missing                          → detecta tools registradas pero faltantes
    bago toolsmith create --tool nombre --desc "..." → scaffoldea nueva herramienta
    bago toolsmith listen                           → escucha el Neural Bus (tool:blocked)
    bago toolsmith --json                           → output JSON

Fuente canónica: .bago/mcp/toolbox_catalog.json
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import json
import os
import re
import sys
import textwrap
import time
import subprocess
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator


TOOLS_DIR   = Path(__file__).resolve().parent
BAGO_ROOT   = TOOLS_DIR.parent
CATALOG_PATH = BAGO_ROOT / "mcp" / "toolbox_catalog.json"
TOOLBOXES_DIR = BAGO_ROOT / "state" / "toolboxes"
REGISTRY_PATH = TOOLS_DIR / "tool_registry.py"
NEURAL_URL    = "http://localhost:7331"

# ── ANSI ─────────────────────────────────────────────────────────────────────

BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"
CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
BLUE   = "\033[34m"
RED    = "\033[31m"
WHITE  = "\033[97m"


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class AssignedTool:
    cmd: str
    purpose: str
    group: str = ""


@dataclass
class Toolbox:
    agent: str
    task: str
    sprint: str
    tools: list[AssignedTool] = field(default_factory=list)
    composite: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat(timespec="seconds")


# ── Catalog loader ────────────────────────────────────────────────────────────

def _load_catalog() -> dict:
    if not CATALOG_PATH.exists():
        print(f"{RED}[toolsmith] ERROR: Catálogo no encontrado: {CATALOG_PATH}{RESET}", file=sys.stderr)
        sys.exit(1)
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


# ── Keyword matching ──────────────────────────────────────────────────────────

def _score_routing(task_desc: str, routing: dict) -> list[tuple[int, str, dict]]:
    """
    Devuelve lista de (score, task_type, route_entry) ordenada desc.
    Score = número de keywords coincidentes.
    """
    words = set(re.findall(r"[a-záéíóúüñA-ZÁÉÍÓÚÜÑ]+", task_desc.lower()))
    scored = []
    for task_type, route in routing.items():
        kws = set(k.lower() for k in route.get("keywords", []))
        # Tokenize multi-word keywords too
        kw_words: set[str] = set()
        for kw in kws:
            kw_words.update(kw.split())
        score = len(words & kw_words)
        if score > 0:
            scored.append((score, task_type, route))
    return sorted(scored, key=lambda x: x[0], reverse=True)


# ── assign ────────────────────────────────────────────────────────────────────

def assign(task_description: str, agent: str | None = None, sprint: str = "") -> Toolbox:
    """Analiza la descripción de tarea y devuelve la toolbox óptima."""
    catalog = _load_catalog()
    routing = catalog.get("task_routing", {})
    groups  = catalog.get("tool_groups", {})
    agent_defaults = catalog.get("agent_defaults", {})

    hits = _score_routing(task_description, routing)

    if not hits:
        # Fallback: usar herramientas always_available del agente (si se conoce)
        if agent and agent in agent_defaults:
            cmds = agent_defaults[agent].get("always_available", [])
            tools = [AssignedTool(cmd=c, purpose="always_available", group="default") for c in cmds]
            return Toolbox(agent=agent or "UNKNOWN", task=task_description, sprint=sprint, tools=tools)
        # Último recurso
        return Toolbox(
            agent=agent or "UNKNOWN",
            task=task_description,
            sprint=sprint,
            tools=[AssignedTool(cmd="find-tool", purpose="No se pudo determinar toolbox — usar find-tool", group="search_discovery")],
        )

    best_score, best_type, best_route = hits[0]

    inferred_agent = agent or best_route.get("agent", "MAESTRO_BAGO")
    group_id  = best_route.get("toolbox_group", "")
    composite = best_route.get("composite", "")
    tool_cmds = best_route.get("tools", [])

    # Añadir always_available del agente
    if inferred_agent in agent_defaults:
        always = agent_defaults[inferred_agent].get("always_available", [])
        for cmd in always:
            if cmd not in tool_cmds:
                tool_cmds = list(tool_cmds) + [cmd]

    tools = [AssignedTool(cmd=c, purpose=best_route["label"], group=group_id) for c in tool_cmds]

    # Si hay múltiples matches, añadir herramientas secundarias
    if len(hits) > 1 and hits[1][0] >= 1:
        secondary_cmds = hits[1][2].get("tools", [])
        existing = {t.cmd for t in tools}
        for cmd in secondary_cmds:
            if cmd not in existing:
                tools.append(AssignedTool(cmd=cmd, purpose=f"secundario: {hits[1][2]['label']}", group=hits[1][2].get("toolbox_group", "")))

    return Toolbox(
        agent=inferred_agent,
        task=task_description,
        sprint=sprint,
        tools=tools,
        composite=composite or "",
    )


# ── sprint toolboxes ──────────────────────────────────────────────────────────

def assign_sprint(sprint_id: str, tasks: list[str] | None = None) -> dict[str, Toolbox]:
    """Asigna toolboxes a todos los agentes para un sprint."""
    catalog = _load_catalog()
    agent_defaults = catalog.get("agent_defaults", {})

    sprint_toolboxes: dict[str, Toolbox] = {}

    if tasks:
        # Asignar por tareas individuales
        for task in tasks:
            tb = assign(task, sprint=sprint_id)
            agent = tb.agent
            if agent not in sprint_toolboxes:
                sprint_toolboxes[agent] = tb
            else:
                # Merge tools
                existing_cmds = {t.cmd for t in sprint_toolboxes[agent].tools}
                for t in tb.tools:
                    if t.cmd not in existing_cmds:
                        sprint_toolboxes[agent].tools.append(t)
    else:
        # Toolboxes por defecto de cada agente
        for agent, defaults in agent_defaults.items():
            always = defaults.get("always_available", [])
            on_start = defaults.get("on_sprint_start", [])
            tools = [AssignedTool(cmd=c, purpose="always_available", group="default") for c in always]
            tools += [AssignedTool(cmd=c, purpose="sprint_start", group="default") for c in on_start]
            sprint_toolboxes[agent] = Toolbox(agent=agent, task="sprint", sprint=sprint_id, tools=tools)

    return sprint_toolboxes


# ── missing tools ─────────────────────────────────────────────────────────────

def find_missing() -> list[dict]:
    """Detecta herramientas registradas en tool_registry cuyo archivo no existe."""
    missing = []
    if not REGISTRY_PATH.exists():
        return missing

    src = REGISTRY_PATH.read_text(encoding="utf-8")

    # Extrae expresiones de path de PreflightCheck("file", str(...))
    pattern = re.compile(r'PreflightCheck\("file",\s*str\(([^)]+)\)\)', re.MULTILINE)
    seen: set[str] = set()
    for match in pattern.finditer(src):
        expr = match.group(1).strip()

        # Extrae todos los segmentos de string: TOOLS_DIR / "a" / "b.py" → [a, b.py]
        segments = re.findall(r'"([^"]+)"', expr)
        if not segments:
            continue

        # Determina la raíz (TOOLS_DIR o BAGO_ROOT)
        if expr.startswith("BAGO_ROOT"):
            root = BAGO_ROOT
        else:
            root = TOOLS_DIR

        fpath = root.joinpath(*segments)
        key = str(fpath)
        if key in seen:
            continue
        seen.add(key)

        if not fpath.exists():
            missing.append({
                "file": "/".join(segments),
                "path": str(fpath),
                "exists": False,
            })

    return missing


# ── create tool scaffold ──────────────────────────────────────────────────────

_TOOL_TEMPLATE = """\
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
\"\"\"
{name}.py — {description}

Generado por: bago toolsmith create
Uso:
    bago {cmd}                  → comportamiento por defecto
    bago {cmd} --json           → output JSON
    bago {cmd} --help           → ayuda
\"\"\"
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
BAGO_ROOT = TOOLS_DIR.parent
STATE_DIR = BAGO_ROOT / "state"


def run(args: list[str] | None = None) -> int:
    \"\"\"Punto de entrada principal. Devuelve 0 si OK, 1 si error.\"\"\"
    if args is None:
        args = sys.argv[1:]

    as_json = "--json" in args

    # TODO: implementar lógica de {name}
    result = {{
        "tool": "{name}",
        "status": "ok",
        "message": "{description}",
    }}

    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"[{name}] {description}")

    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
"""


def create_tool(name: str, description: str, category: str = "labs") -> Path:
    """
    Crea un scaffold de nueva herramienta en TOOLS_DIR.
    Devuelve la ruta del archivo creado.
    """
    safe_name = re.sub(r"[^a-z0-9_]", "_", name.lower())
    out_path = TOOLS_DIR / f"{safe_name}.py"
    if out_path.exists():
        print(f"{YELLOW}[toolsmith] Ya existe: {out_path}{RESET}")
        return out_path

    code = _TOOL_TEMPLATE.format(
        name=safe_name,
        cmd=safe_name.replace("_", "-"),
        description=description,
    )
    out_path.write_text(code, encoding="utf-8")
    print(f"{GREEN}[toolsmith] Creada: {out_path}{RESET}")

    # Auto rubber duck en background (best-effort, no bloquea)
    _auto_rubber_duck(out_path)

    # Emitir evento en el neural bus si está disponible
    _emit_event("tool:created", {
        "name": safe_name,
        "path": str(out_path),
        "description": description,
        "category": category,
    })

    return out_path


# ── Auto rubber duck (after tool creation) ───────────────────────────────────

def _auto_rubber_duck(file_path: Path) -> None:
    """
    Launch rubber duck analysis in a background subprocess after tool creation.
    Output goes to .bago/state/findings/rd_auto_<name>_<ts>.log — does not block.
    Skipped if --no-rubber-duck in sys.argv or BAGO_SKIP_RD env var is set.
    """
    if "--no-rubber-duck" in sys.argv or os.getenv("BAGO_SKIP_RD"):
        return
    try:
        rd_script = TOOLS_DIR / "bago_rubber_duck.py"
        if not rd_script.exists():
            return
        findings_dir = BAGO_ROOT / "state" / "findings"
        findings_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        log_path = findings_dir / f"rd_auto_{file_path.stem}_{ts}.log"

        kwargs: dict = {
            "stdout": log_path.open("w", encoding="utf-8"),
            "stderr": subprocess.STDOUT,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

        subprocess.Popen([sys.executable, str(rd_script), str(file_path)], **kwargs)
        print(f"{DIM}[toolsmith] Rubber duck análisis iniciado → {log_path.name}{RESET}")
    except Exception:
        pass  # auto-trigger is best-effort


# ── Neural Bus integration ────────────────────────────────────────────────────

def _emit_event(event_type: str, data: dict) -> bool:
    """Emite un evento al Neural Bus. Silencioso si el bus no está disponible."""
    try:
        payload = json.dumps({"type": event_type, "source": "toolsmith", "data": data}).encode()
        req = urllib.request.Request(
            f"{NEURAL_URL}/emit",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def _listen_neural_bus() -> Iterator[dict]:
    """Generador que consume el SSE stream del Neural Bus."""
    try:
        req = urllib.request.Request(f"{NEURAL_URL}/events", headers={"Accept": "text/event-stream"})
        with urllib.request.urlopen(req, timeout=None) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if line.startswith("data:"):
                    try:
                        yield json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        pass
    except Exception:
        return


def listen() -> None:
    """
    Escucha el Neural Bus en busca de eventos tool:blocked.
    Cuando un agente emite tool:blocked, responde con la toolbox adecuada.
    """
    print(f"{CYAN}[toolsmith] Escuchando Neural Bus en {NEURAL_URL}/events...{RESET}")
    print(f"{DIM}  Ctrl+C para detener{RESET}\n")

    try:
        for event in _listen_neural_bus():
            etype = event.get("type", "")
            if etype not in ("tool:blocked", "toolbox:request"):
                continue

            agent_id = event.get("agent") or event.get("source", "UNKNOWN")
            task_desc = event.get("task") or event.get("data", {}).get("task", "")

            print(f"\n{YELLOW}▸ [{etype}]{RESET} agente={agent_id}  tarea={task_desc[:60]}")

            if etype == "tool:blocked":
                missing_tool = event.get("data", {}).get("tool", "")
                print(f"  Herramienta bloqueante: {missing_tool}")
                # Buscar si existe en el catálogo
                catalog = _load_catalog()
                groups = catalog.get("tool_groups", {})
                found_in = []
                for gid, grp in groups.items():
                    if missing_tool in grp.get("cli_cmds", []) or missing_tool in grp.get("scripts", []):
                        found_in.append(gid)
                if found_in:
                    print(f"  {GREEN}✓ Encontrada en grupos: {found_in}{RESET}")
                else:
                    print(f"  {RED}✗ No encontrada — scaffoldeando...{RESET}")
                    create_tool(missing_tool, f"Tool auto-creada para resolver bloqueo de {agent_id}")

            tb = assign(task_desc, agent=agent_id)
            _emit_event("toolbox:assigned", {
                "agent": agent_id,
                "task": task_desc,
                "tools": [t.cmd for t in tb.tools],
                "composite": tb.composite,
            })
            print(f"  {GREEN}→ Toolbox asignada: {[t.cmd for t in tb.tools[:5]]}...{RESET}")

    except KeyboardInterrupt:
        print(f"\n{DIM}[toolsmith] Detenido.{RESET}")


# ── Persist toolbox ───────────────────────────────────────────────────────────

def save_toolbox(tb: Toolbox) -> Path:
    """Persiste una toolbox en state/toolboxes/<agent>_<sprint>.json."""
    TOOLBOXES_DIR.mkdir(parents=True, exist_ok=True)
    safe_sprint = re.sub(r"[^a-z0-9_-]", "_", (tb.sprint or "default").lower())
    safe_agent  = re.sub(r"[^a-z0-9_-]", "_", tb.agent.lower())
    out = TOOLBOXES_DIR / f"{safe_agent}_{safe_sprint}.json"
    out.write_text(json.dumps(asdict(tb), ensure_ascii=False, indent=2), encoding="utf-8")
    return out


# ── Display ───────────────────────────────────────────────────────────────────

def _print_toolbox(tb: Toolbox) -> None:
    print(f"\n{BOLD}{CYAN}╔══ TOOLBOX ═══════════════════════════════════════╗{RESET}")
    print(f"{BOLD}  Agente  :{RESET} {MAGENTA}{tb.agent}{RESET}")
    print(f"{BOLD}  Tarea   :{RESET} {tb.task[:70]}")
    if tb.sprint:
        print(f"{BOLD}  Sprint  :{RESET} {tb.sprint}")
    if tb.composite:
        print(f"{BOLD}  Pipeline:{RESET} {GREEN}{tb.composite}{RESET}")
    print(f"{BOLD}  Tools   :{RESET}")
    for t in tb.tools:
        purpose_tag = f"  {DIM}← {t.purpose}{RESET}" if t.purpose and t.purpose != "always_available" else ""
        print(f"    {CYAN}bago {t.cmd:<28}{RESET}{purpose_tag}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════╝{RESET}")


def _print_catalog(catalog: dict) -> None:
    groups    = catalog.get("tool_groups", {})
    composites = catalog.get("composite_tools", {})
    routing   = catalog.get("task_routing", {})

    print(f"\n{BOLD}{CYAN}══ TOOL GROUPS ({len(groups)}) ══════════════════════════════════{RESET}")
    for gid, grp in groups.items():
        cmds = " | ".join(grp.get("cli_cmds", [])[:5])
        print(f"  {BOLD}{gid:<25}{RESET} {grp['label']}")
        print(f"  {DIM}  cmds: {cmds}{RESET}")
        print(f"  {DIM}  uso:  {grp.get('when_to_use', '')[:65]}...{RESET}")
        print()

    print(f"\n{BOLD}{YELLOW}══ COMPOSITE TOOLS ({len(composites)}) ══════════════════════════════{RESET}")
    for cid, comp in composites.items():
        pipeline = " → ".join(comp.get("pipeline", [])[:4]) + ("..." if len(comp.get("pipeline", [])) > 4 else "")
        print(f"  {BOLD}{cid:<25}{RESET} {comp['label']}")
        print(f"  {DIM}  pipeline: {pipeline}{RESET}")
        print(f"  {DIM}  trigger:  {comp.get('trigger', '')}  agente: {comp.get('agent', '')}{RESET}")
        print()

    print(f"\n{BOLD}{GREEN}══ TASK ROUTING ({len(routing)}) ══════════════════════════════════{RESET}")
    for tid, route in routing.items():
        kws = ", ".join(route.get("keywords", [])[:4])
        print(f"  {BOLD}{tid:<25}{RESET} → {MAGENTA}{route.get('agent', ''):<30}{RESET}")
        print(f"  {DIM}  keywords: {kws}{RESET}")
        print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        _usage()
        return

    subcommand = args[0]
    rest = args[1:]
    as_json = "--json" in rest

    # ── catalog ────────────────────────────────────────────────────────────────
    if subcommand == "catalog":
        catalog = _load_catalog()
        if as_json:
            print(json.dumps(catalog, ensure_ascii=False, indent=2))
        else:
            _print_catalog(catalog)
        return

    # ── assign ─────────────────────────────────────────────────────────────────
    if subcommand == "assign":
        task = None
        agent = None
        sprint = ""
        i = 0
        while i < len(rest):
            if rest[i] == "--task" and i + 1 < len(rest):
                task = rest[i + 1]; i += 2
            elif rest[i] == "--agent" and i + 1 < len(rest):
                agent = rest[i + 1]; i += 2
            elif rest[i] == "--sprint" and i + 1 < len(rest):
                sprint = rest[i + 1]; i += 2
            else:
                if not rest[i].startswith("--"):
                    task = rest[i]
                i += 1

        if not task:
            print(f"{RED}[toolsmith] ERROR: --task <descripción> es requerido{RESET}", file=sys.stderr)
            sys.exit(1)

        tb = assign(task, agent=agent, sprint=sprint)
        if as_json:
            print(json.dumps(asdict(tb), ensure_ascii=False, indent=2))
        else:
            _print_toolbox(tb)

        if sprint:
            saved = save_toolbox(tb)
            if not as_json:
                print(f"\n  {DIM}Toolbox guardada en: {saved}{RESET}")
        return

    # ── sprint ─────────────────────────────────────────────────────────────────
    if subcommand == "sprint":
        sprint_id = rest[0] if rest and not rest[0].startswith("--") else "current"
        tasks = []
        i = 0
        while i < len(rest):
            if rest[i] == "--tasks" and i + 1 < len(rest):
                tasks = rest[i + 1].split(","); i += 2
            else:
                i += 1

        sprint_tbs = assign_sprint(sprint_id, tasks or None)
        if as_json:
            print(json.dumps({a: asdict(tb) for a, tb in sprint_tbs.items()}, ensure_ascii=False, indent=2))
        else:
            print(f"\n{BOLD}{CYAN}══ SPRINT {sprint_id} — TOOLBOXES ═══════════════════════════{RESET}")
            for agent_name, tb in sorted(sprint_tbs.items()):
                cmds = ", ".join(t.cmd for t in tb.tools[:6])
                print(f"  {MAGENTA}{agent_name:<32}{RESET} {cmds}")

        # Persistir toolboxes
        for tb in sprint_tbs.values():
            save_toolbox(tb)

        if not as_json:
            print(f"\n{DIM}  Toolboxes guardadas en: {TOOLBOXES_DIR}{RESET}")
        return

    # ── missing ────────────────────────────────────────────────────────────────
    if subcommand == "missing":
        missing = find_missing()
        if as_json:
            print(json.dumps(missing, ensure_ascii=False, indent=2))
        else:
            if not missing:
                print(f"{GREEN}[toolsmith] ✅ Todas las herramientas registradas existen.{RESET}")
            else:
                print(f"{YELLOW}[toolsmith] ⚠️  Herramientas registradas pero faltantes:{RESET}")
                for m in missing:
                    print(f"  {RED}✗{RESET} {m['file']}")
                    print(f"    {DIM}→ {m['path']}{RESET}")
        return

    # ── create ─────────────────────────────────────────────────────────────────
    if subcommand == "create":
        name = ""
        desc = "Herramienta BAGO auto-generada"
        cat  = "labs"
        i = 0
        while i < len(rest):
            if rest[i] == "--tool" and i + 1 < len(rest):
                name = rest[i + 1]; i += 2
            elif rest[i] in ("--desc", "--description") and i + 1 < len(rest):
                desc = rest[i + 1]; i += 2
            elif rest[i] == "--category" and i + 1 < len(rest):
                cat = rest[i + 1]; i += 2
            elif not rest[i].startswith("--") and not name:
                name = rest[i]; i += 1
            else:
                i += 1

        if not name:
            print(f"{RED}[toolsmith] ERROR: --tool <nombre> es requerido{RESET}", file=sys.stderr)
            sys.exit(1)

        path = create_tool(name, desc, cat)
        if as_json:
            print(json.dumps({"created": str(path), "name": name}, ensure_ascii=False))
        return

    # ── listen ─────────────────────────────────────────────────────────────────
    if subcommand == "listen":
        listen()
        return

    # ── toolbox list for an agent ──────────────────────────────────────────────
    if subcommand == "agent":
        agent_id = rest[0] if rest and not rest[0].startswith("--") else None
        if not agent_id:
            print(f"{RED}[toolsmith] ERROR: indicar nombre del agente{RESET}", file=sys.stderr)
            sys.exit(1)

        catalog = _load_catalog()
        agent_defaults = catalog.get("agent_defaults", {})
        if agent_id not in agent_defaults:
            # Buscar case-insensitive
            matches = [k for k in agent_defaults if agent_id.upper() in k.upper()]
            if matches:
                agent_id = matches[0]
            else:
                print(f"{RED}[toolsmith] Agente no encontrado: {agent_id}{RESET}", file=sys.stderr)
                print(f"  Disponibles: {', '.join(agent_defaults.keys())}")
                sys.exit(1)

        info = agent_defaults[agent_id]
        if as_json:
            print(json.dumps({agent_id: info}, ensure_ascii=False, indent=2))
        else:
            print(f"\n{BOLD}{MAGENTA}══ {agent_id} ══{RESET}")
            print(f"  {CYAN}Siempre disponibles:{RESET} {', '.join(info.get('always_available', []))}")
            if "on_sprint_start" in info:
                print(f"  {GREEN}Al iniciar sprint:{RESET}  {', '.join(info['on_sprint_start'])}")
            if "on_sprint_end" in info:
                print(f"  {YELLOW}Al cerrar sprint:{RESET}   {', '.join(info['on_sprint_end'])}")
            if "on_blocked" in info:
                print(f"  {RED}Si bloqueado:{RESET}       {', '.join(info['on_blocked'])}")
            print(f"  {BLUE}Grupos de tools:{RESET}    {', '.join(info.get('toolbox_group', []))}")
        return

    print(f"{RED}[toolsmith] Subcomando desconocido: {subcommand}{RESET}", file=sys.stderr)
    _usage()
    sys.exit(1)


def _usage() -> None:
    print(f"""
{BOLD}{CYAN}toolsmith{RESET} — Agente dinámico de cajas de herramientas BAGO

{BOLD}SUBCOMANDOS:{RESET}
  {GREEN}catalog{RESET}                              Muestra el catálogo completo de groups, composites y routing
  {GREEN}assign{RESET} --task <desc>                 Infiere toolbox óptima para la tarea descrita
          [--agent NOMBRE]             Fija el agente (si no, se infiere)
          [--sprint <id>]              Guarda la toolbox en state/toolboxes/
  {GREEN}sprint{RESET} <id>                          Asigna toolboxes a todos los agentes para el sprint
          [--tasks "t1,t2,t3"]        Toolboxes basadas en tareas específicas
  {GREEN}agent{RESET} <NOMBRE>                       Muestra la toolbox por defecto de un agente
  {GREEN}missing{RESET}                              Detecta tools registradas pero faltantes en disco
  {GREEN}create{RESET} --tool <nombre>               Scaffoldea una nueva herramienta
          [--desc "descripción"]
          [--category labs|core|...]
  {GREEN}listen{RESET}                               Escucha el Neural Bus (tool:blocked → asignar/crear)

{BOLD}FLAGS:{RESET}
  --json                               Output JSON máquina-legible

{BOLD}EJEMPLOS:{RESET}
  bago toolsmith assign --task "fix bug en auth module"
  bago toolsmith assign --task "preparar release v2.0" --agent CENTINELA_SINCERIDAD
  bago toolsmith sprint sprint-42
  bago toolsmith agent ANALISTA_Contexto
  bago toolsmith create --tool "jwt_validator" --desc "Valida tokens JWT"
  bago toolsmith missing
  bago toolsmith listen
""")


if __name__ == "__main__":
    main()
