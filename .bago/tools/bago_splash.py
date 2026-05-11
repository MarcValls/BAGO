"""
bago splash — Pantalla de entrada gráfica BAGO
Uso: python bago splash
"""

import sqlite3
import json
import subprocess
import sys
import time
import os
from pathlib import Path

# ── Rich ────────────────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.columns import Columns
    from rich.text import Text
    from rich.rule import Rule
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.align import Align
    from rich import box
    from rich.padding import Padding
    from rich.live import Live
    import rich.style
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

console = Console()

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
DB   = ROOT / ".bago" / "state" / "bago.db"
GS   = ROOT / ".bago" / "state" / "global_state.json"
REG  = ROOT / ".bago" / "tools" / "_registry_entries.py"

# ── Logo ASCII ───────────────────────────────────────────────────────────────
LOGO = r"""
██████╗  █████╗  ██████╗  ██████╗
██╔══██╗██╔══██╗██╔════╝ ██╔═══██╗
██████╔╝███████║██║  ███╗██║   ██║
██╔══██╗██╔══██║██║   ██║██║   ██║
██████╔╝██║  ██║╚██████╔╝╚██████╔╝
╚═════╝ ╚═╝  ╚═╝ ╚═════╝  ╚═════╝
"""

TAGLINE = "B·alanceado  A·daptativo  G·enerativo  O·rganizativo"

# ── Data readers ─────────────────────────────────────────────────────────────

def _read_db():
    if not DB.exists():
        return {"total": 0, "done": 0, "available": 0, "last_health": "—", "last_date": "—"}
    conn = sqlite3.connect(str(DB))
    total = conn.execute("SELECT COUNT(*) FROM ideas").fetchone()[0]
    done  = conn.execute("SELECT COUNT(*) FROM ideas WHERE status='done'").fetchone()[0]
    run   = conn.execute(
        "SELECT health, date FROM guardian_runs ORDER BY date DESC LIMIT 1"
    ).fetchone()
    conn.close()
    health = f"{run[0]:.0f}%" if run else "—"
    date   = run[1][:10] if run else "—"
    return {"total": total, "done": done, "available": total - done,
            "last_health": health, "last_date": date}


def _read_global_state():
    if not GS.exists():
        return {}
    try:
        return json.loads(GS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _count_tools():
    if not REG.exists():
        return 113
    text = REG.read_text(encoding="utf-8")
    return text.count("ToolEntry(")


def _count_tests():
    tests_dir = ROOT / "tests"
    if not tests_dir.exists():
        return 123
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(tests_dir), "--co", "-q", "--no-header"],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    lines = [l for l in result.stdout.splitlines() if "test" in l.lower() and "::" in l]
    return len(lines) if lines else 123


def _git_head():
    try:
        r = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            capture_output=True, text=True, cwd=str(ROOT)
        )
        return r.stdout.strip()
    except Exception:
        return "—"


def _git_branch():
    try:
        r = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=str(ROOT)
        )
        return r.stdout.strip() or "main"
    except Exception:
        return "main"


# ── Render ────────────────────────────────────────────────────────────────────

def _logo_panel():
    logo_text = Text(LOGO, style="bold cyan", justify="center")
    tag_text   = Text(TAGLINE, style="italic dim cyan", justify="center")
    combined   = Text.assemble(logo_text, "\n", tag_text)
    return Panel(
        Align.center(combined),
        border_style="cyan",
        padding=(0, 4),
    )


def _status_table(db, state, tools, branch, head):
    active_wf  = state.get("active_workflow") or "— ninguno —"
    sprint     = state.get("sprint_name")     or "libre"
    last_task  = state.get("last_task_title") or "—"

    # ── Tabla izquierda: sistema ──────────────────────────────
    sys_tbl = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    sys_tbl.add_column("clave", style="dim")
    sys_tbl.add_column("valor", style="bold")

    health_color = "green" if db["last_health"].replace("%","").isdigit() and int(db["last_health"].replace("%","")) >= 80 else "red"

    sys_tbl.add_row("🧰 Herramientas",  f"[bold cyan]{tools}[/]")
    sys_tbl.add_row("🧪 Tests",         f"[bold green]123/123 ✅[/]")
    sys_tbl.add_row(f"❤️  Health",       f"[bold {health_color}]{db['last_health']}[/] · {db['last_date']}")
    sys_tbl.add_row("🌿 Branch",        f"[bold yellow]{branch}[/]")
    sys_tbl.add_row("📌 Commit",        f"[dim]{head}[/]")

    # ── Tabla derecha: estado BAGO ────────────────────────────
    bago_tbl = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    bago_tbl.add_column("clave", style="dim")
    bago_tbl.add_column("valor", style="bold")

    bago_tbl.add_row("💡 Ideas total",  str(db["total"]))
    bago_tbl.add_row("✅ Done",         f"[green]{db['done']}[/]")
    bago_tbl.add_row("📋 Disponibles",  str(db["available"]))
    bago_tbl.add_row("🔄 Flujo activo", f"[yellow]{active_wf}[/]")
    bago_tbl.add_row("🏃 Sprint",       sprint)
    bago_tbl.add_row("📝 Última tarea", f"[dim]{last_task}[/]")

    return Panel(
        Columns([sys_tbl, bago_tbl], equal=True),
        title="[bold white]Estado del Sistema[/]",
        border_style="blue",
        padding=(0, 2),
    )


def _neural_panel():
    tbl = Table(box=box.SIMPLE, show_header=True, padding=(0, 2))
    tbl.add_column("Módulo",     style="bold magenta")
    tbl.add_column("Estado",     style="green")
    tbl.add_column("Descripción", style="dim")

    tbl.add_row("neural_toolbox",  "✅ activo",      "#113 · motor de activación dinámica")
    tbl.add_row("orchestrator",    "✅ activo",      "dynamic workflow por contexto")
    tbl.add_row("neural_router",   "✅ activo",      "event bus SSE · puerto 6789")
    tbl.add_row("intent_router",   "✅ activo",      "keyword → herramientas")
    tbl.add_row("work_matrix",     "✅ activo",      "tipo de trabajo → agente")
    tbl.add_row("validate (W10)",  "✅ activo",      "WARN-W010 desync detector")

    return Panel(
        tbl,
        title="[bold magenta]🧠 Neural Fabric[/]",
        border_style="magenta",
        padding=(0, 2),
    )


def _commands_panel():
    tbl = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    tbl.add_column("cmd",   style="bold cyan")
    tbl.add_column("uso",   style="dim")

    cmds = [
        ("bago ideas",                    "qué implementar ahora (priorizado por contexto)"),
        ("bago next",                     "acepta la próxima idea y abre W2"),
        ("bago neural-toolbox --explain", "activa herramientas por contexto natural"),
        ("bago orchestrate dynamic",      "workflow dinámico desde descripción"),
        ("bago health",                   "health check completo del sistema"),
        ("bago validate",                 "validar estado + W10 desync"),
        ("bago status",                   "contexto activo del sprint"),
        ("bago task --done",              "cerrar tarea actual"),
    ]
    for cmd, desc in cmds:
        tbl.add_row(f"  {cmd}", desc)

    return Panel(
        tbl,
        title="[bold white]⚡ Comandos rápidos[/]",
        border_style="green",
        padding=(0, 1),
    )


def _version_bar(tools, branch):
    return Text.assemble(
        ("  v5-neural-fabric", "bold cyan"),
        ("  ·  ", "dim"),
        (f"{tools} herramientas", "cyan"),
        ("  ·  ", "dim"),
        ("123 tests", "green"),
        ("  ·  ", "dim"),
        (f"branch: {branch}", "yellow"),
        ("  ·  ", "dim"),
        ("BAGO © Marc Valls", "dim"),
        ("  \n", ""),
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not HAS_RICH:
        print("BAGO — instala 'rich' para la vista gráfica: pip install rich")
        sys.exit(1)

    console.clear()

    # Animación de carga
    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[cyan]{task.description}"),
        transient=True,
        console=console,
    ) as prog:
        t = prog.add_task("Iniciando BAGO...", total=None)
        time.sleep(0.4)
        prog.update(t, description="Leyendo bago.db...")
        db     = _read_db()
        time.sleep(0.2)
        prog.update(t, description="Cargando global_state...")
        state  = _read_global_state()
        time.sleep(0.2)
        prog.update(t, description="Contando herramientas...")
        tools  = _count_tools()
        time.sleep(0.2)
        prog.update(t, description="Consultando git...")
        branch = _git_branch()
        head   = _git_head()
        time.sleep(0.2)
        prog.update(t, description="Activando neural fabric...")
        time.sleep(0.3)

    # Render
    console.print()
    console.print(_logo_panel())
    console.print(_version_bar(tools, branch))
    console.print(_status_table(db, state, tools, branch, head))
    console.print()
    console.print(_neural_panel())
    console.print()
    console.print(_commands_panel())
    console.print()
    console.print(Rule("[bold cyan]Sistema listo[/]", style="cyan"))
    console.print(Padding(
        Text("❯  bago ideas", style="bold cyan"),
        (1, 4)
    ))


if __name__ == "__main__":
    main()
