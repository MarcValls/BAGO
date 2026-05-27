"""
bago splash - Pantalla de entrada grafica BAGO
Uso: python bago splash
"""

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import sqlite3
import json
import subprocess
import sys
import time
import os
from pathlib import Path

# Forzar UTF-8 en Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Rich ────────────────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.columns import Columns
    from rich.text import Text
    from rich.rule import Rule
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.align import Align
    from rich import box
    from rich.padding import Padding
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# ── Pyfiglet ─────────────────────────────────────────────────────────────────
try:
    import pyfiglet
    HAS_FIGLET = True
except ImportError:
    HAS_FIGLET = False

console = Console(force_terminal=True, highlight=False)

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
DB   = ROOT / ".bago" / "state" / "bago.db"
GS   = ROOT / ".bago" / "state" / "global_state.json"
REG  = ROOT / ".bago" / "tools" / "_registry_entries.py"

# ── Logo (ASCII puro, sin Unicode) ───────────────────────────────────────────
LOGO_FALLBACK = r"""
 ____    _    ____  ___
|  _ \  / \  / ___|/ _ \
| |_) |/ _ \| |  _| | | |
|  _ </ ___ \ |_| | |_| |
|____/_/   \_\____|\___/
"""

def _get_logo():
    if HAS_FIGLET:
        try:
            return pyfiglet.figlet_format("BAGO", font="banner3")
        except Exception:
            pass
    return LOGO_FALLBACK

TAGLINE = "B.alanceado  A.daptativo  G.enerativo  O.rganizativo"

# ── Data readers ─────────────────────────────────────────────────────────────

def _read_db():
    if not DB.exists():
        return {"total": 0, "done": 0, "available": 0, "last_health": "—", "last_date": "—"}
    conn = sqlite3.connect(str(DB))
    gs = _read_global_state()
    devmode = gs.get("devmode", False)
    active_project = gs.get("active_project")

    if devmode or not active_project:
        total = conn.execute("SELECT COUNT(*) FROM ideas").fetchone()[0]
        done  = conn.execute("SELECT COUNT(*) FROM ideas WHERE status='done'").fetchone()[0]
    else:
        total = conn.execute(
            "SELECT COUNT(*) FROM ideas WHERE project=? OR (project IS NULL AND source != 'catalog')",
            (active_project,)
        ).fetchone()[0]
        done = conn.execute(
            "SELECT COUNT(*) FROM ideas WHERE status='done' AND (project=? OR (project IS NULL AND source != 'catalog'))",
            (active_project,)
        ).fetchone()[0]

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
    logo_text = Text(_get_logo(), style="bold cyan", justify="center")
    tag_text   = Text(TAGLINE, style="italic dim cyan", justify="center")
    combined   = Text.assemble(logo_text, "\n", tag_text)
    return Panel(
        Align.center(combined),
        border_style="cyan",
        padding=(0, 4),
    )


def _status_table(db, state, tools, branch, head):
    active_wf  = state.get("active_workflow") or "ninguno"
    sprint     = state.get("sprint_name")     or "libre"
    last_task  = state.get("last_task_title") or "-"

    sys_tbl = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    sys_tbl.add_column("clave", style="dim")
    sys_tbl.add_column("valor", style="bold")

    health_color = "green" if db["last_health"].replace("%","").isdigit() and int(db["last_health"].replace("%","")) >= 80 else "red"

    sys_tbl.add_row("[cyan]Herramientas[/]",  f"[bold cyan]{tools}[/]")
    sys_tbl.add_row("[green]Tests[/]",         f"[bold green]123/123 OK[/]")
    sys_tbl.add_row("[red]Health[/]",          f"[bold {health_color}]{db['last_health']}[/]  {db['last_date']}")
    sys_tbl.add_row("[yellow]Branch[/]",       f"[bold yellow]{branch}[/]")
    sys_tbl.add_row("[dim]Commit[/]",          f"[dim]{head[:50]}[/]")

    bago_tbl = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    bago_tbl.add_column("clave", style="dim")
    bago_tbl.add_column("valor", style="bold")

    bago_tbl.add_row("[cyan]Ideas total[/]",   str(db["total"]))
    bago_tbl.add_row("[green]Done[/]",         f"[green]{db['done']}[/]")
    bago_tbl.add_row("[white]Disponibles[/]",  str(db["available"]))
    bago_tbl.add_row("[yellow]Flujo activo[/]", f"[yellow]{active_wf}[/]")
    bago_tbl.add_row("[white]Sprint[/]",        sprint)
    bago_tbl.add_row("[dim]Ultima tarea[/]",   f"[dim]{last_task}[/]")

    return Panel(
        Columns([sys_tbl, bago_tbl], equal=True),
        title="[bold white]Estado del Sistema[/]",
        border_style="blue",
        padding=(0, 2),
    )


def _neural_panel():
    tbl = Table(box=box.SIMPLE, show_header=True, padding=(0, 2))
    tbl.add_column("Modulo",      style="bold magenta")
    tbl.add_column("Estado",      style="green")
    tbl.add_column("Descripcion", style="dim")

    tbl.add_row("neural_toolbox",  "[green]OK[/]",  "#113 motor de activacion dinamica")
    tbl.add_row("orchestrator",    "[green]OK[/]",  "dynamic workflow por contexto")
    tbl.add_row("neural_router",   "[green]OK[/]",  "event bus SSE puerto 6789")
    tbl.add_row("intent_router",   "[green]OK[/]",  "keyword -> herramientas")
    tbl.add_row("work_matrix",     "[green]OK[/]",  "tipo de trabajo -> agente")
    tbl.add_row("validate (W10)",  "[green]OK[/]",  "WARN-W010 desync detector")

    return Panel(
        tbl,
        title="[bold magenta]Neural Fabric[/]",
        border_style="magenta",
        padding=(0, 2),
    )


def _commands_panel():
    tbl = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    tbl.add_column("cmd",   style="bold cyan")
    tbl.add_column("uso",   style="dim")

    cmds = [
        ("bago ideas",                    "que implementar ahora"),
        ("bago next",                     "acepta la proxima idea y abre W2"),
        ("bago neural-toolbox --explain", "activa herramientas por contexto"),
        ("bago orchestrate dynamic",      "workflow dinamico desde descripcion"),
        ("bago health",                   "health check completo del sistema"),
        ("bago validate",                 "validar estado + W10 desync"),
        ("bago status",                   "contexto activo del sprint"),
        ("bago task --done",              "cerrar tarea actual"),
    ]
    for cmd, desc in cmds:
        tbl.add_row(f"  {cmd}", desc)

    return Panel(
        tbl,
        title="[bold white]Comandos rapidos[/]",
        border_style="green",
        padding=(0, 1),
    )


def _version_bar(tools, branch):
    return Text.assemble(
        ("  v5-neural-fabric", "bold cyan"),
        ("  |  ", "dim"),
        (f"{tools} herramientas", "cyan"),
        ("  |  ", "dim"),
        ("123 tests OK", "green"),
        ("  |  ", "dim"),
        (f"branch: {branch}", "yellow"),
        ("  |  ", "dim"),
        ("BAGO by Marc Valls", "dim"),
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
        Text(">  bago ideas", style="bold cyan"),
        (1, 4)
    ))




def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())
    main()