#!/usr/bin/env python3
"""
bago flow — visualiza el pipeline de un workflow como flowchart ASCII.
              Gestiona el estado activo del workflow (start/done/status).

Carga los archivos W*.md del pack y extrae la estructura de fases/pasos
para renderizarlos como diagramas de flujo en la terminal.

Uso:
    bago flow                   → listar workflows disponibles
    bago flow W2                → mostrar flowchart de W2
    bago flow all               → mostrar todos los workflows
    bago flow --list            → listar sin renderizar
    bago flow start W2 <titulo> → iniciar workflow activo (escribe en global_state)
    bago flow done              → cerrar workflow activo + generar cierre
    bago flow status            → mostrar workflow activo actual
    bago flow --test            → tests integrados
"""

import argparse
import json
import re
import pathlib
import sys
from datetime import datetime, timezone
from pathlib import Path

BAGO_ROOT   = Path(__file__).parent.parent
STATE_DIR   = BAGO_ROOT / "state"
GLOBAL_FILE = STATE_DIR / "global_state.json"
SPRINT_FILE = STATE_DIR / "sprint.json"


WORKFLOW_COLORS = {
    "W0": "\033[90m",   # gray
    "W1": "\033[36m",   # cyan
    "W2": "\033[32m",   # green
    "W3": "\033[31m",   # red
    "W4": "\033[33m",   # yellow
    "W5": "\033[35m",   # magenta
    "W6": "\033[34m",   # blue
    "W7": "\033[96m",   # bright cyan
    "W8": "\033[93m",   # bright yellow
    "W9": "\033[95m",   # bright magenta
}
RESET = "\033[0m"


def _find_workflow_files() -> dict:
    """Returns {W_CODE: path} mapping."""
    wf_files = {}
    for f in BAGO_ROOT.rglob("W*.md"):
        if f.is_file():
            m = re.match(r"W(\d+)_", f.name)
            if m:
                code = f"W{m.group(1)}"
                if code not in wf_files:
                    wf_files[code] = f
    return dict(sorted(wf_files.items()))


def _extract_phases(content: str) -> list:
    """Extract phase headers and their first bullet from markdown."""
    phases = []
    lines = content.split("\n")
    current_phase = None
    current_bullets = []

    for line in lines:
        # H2/H3 headers as phases
        m2 = re.match(r"^#{2,3}\s+(.+)", line)
        if m2:
            if current_phase:
                phases.append((current_phase, current_bullets[:3]))
            current_phase = m2.group(1).strip()
            current_bullets = []
            continue

        # Bullet points
        if current_phase and re.match(r"^\s*[-*•]\s+(.+)", line):
            text = re.sub(r"^\s*[-*•]\s+", "", line).strip()
            if text and len(text) > 2:
                current_bullets.append(text[:60])

    if current_phase:
        phases.append((current_phase, current_bullets[:3]))

    return phases


def _render_flowchart(wf_code: str, wf_file: Path) -> str:
    content = wf_file.read_text()
    phases = _extract_phases(content)

    color = WORKFLOW_COLORS.get(wf_code, "")

    lines = []
    title = wf_file.stem.replace("_", " ")
    lines.append(f"\n{color}  ╔══ {title} ══╗{RESET}")
    lines.append(f"{color}  ║ {wf_code} Pipeline{RESET}")
    lines.append(f"{color}  ╚{'═' * (len(title) + 6)}╝{RESET}")
    lines.append("")

    if not phases:
        # Try to extract numbered list items as phases
        for line in content.split("\n"):
            m = re.match(r"^\d+\.\s+\*?\*?(.+?)\*?\*?$", line)
            if m:
                phases.append((m.group(1).strip()[:50], []))

    if not phases:
        lines.append("  (sin estructura de fases detectada)")
        lines.append("")
        return "\n".join(lines)

    # Render as vertical flowchart
    for i, (phase, bullets) in enumerate(phases):
        is_last = (i == len(phases) - 1)

        # Phase box
        box_width = min(len(phase) + 4, 50)
        lines.append(f"  {color}┌{'─' * box_width}┐{RESET}")
        lines.append(f"  {color}│ {phase[:box_width-2]:<{box_width-2}} │{RESET}")
        lines.append(f"  {color}└{'─' * box_width}┘{RESET}")

        # Bullets as indented steps
        for b in bullets[:2]:
            lines.append(f"  {color}│{RESET}  · {b[:55]}")

        # Connector
        if not is_last:
            lines.append(f"  {color}│{RESET}")
            lines.append(f"  {color}▼{RESET}")

    lines.append("")
    return "\n".join(lines)


def cmd_list(args):
    wf_files = _find_workflow_files()
    if not wf_files:
        print("  (sin archivos de workflow encontrados)")
        return

    print(f"\n  Workflows BAGO ({len(wf_files)} encontrados)\n")
    for code, path in wf_files.items():
        name = path.stem.replace("_", " ")
        print(f"  {code:4s}  {name}")
    print(f"\n  Usa: bago flow {list(wf_files.keys())[0]} para ver el pipeline\n")


def cmd_flow(wf_code: str):
    wf_files = _find_workflow_files()

    if wf_code.upper() == "ALL":
        for code, path in wf_files.items():
            print(_render_flowchart(code, path))
        return

    # Find by code
    code = wf_code.upper()
    if code not in wf_files:
        # Try partial match
        matches = [k for k in wf_files if wf_code.upper() in k]
        if matches:
            code = matches[0]
        else:
            print(f"  Workflow '{wf_code}' no encontrado. Disponibles: {', '.join(wf_files.keys())}")
            return

    print(_render_flowchart(code, wf_files[code]))


def run_tests():
    print("Ejecutando tests de flow.py...")
    errors = 0

    def ok(name):
        print(f"  OK: {name}")

    def fail(name, msg):
        nonlocal errors
        errors += 1
        print(f"  FAIL: {name} — {msg}")

    # Test 1: find workflow files
    wf_files = _find_workflow_files()
    if len(wf_files) > 0:
        ok("flow:find_workflow_files")
    else:
        fail("flow:find_workflow_files", "no files found")

    # Test 2: extract phases from mock content
    mock_md = """
## Fase 1 — Inicio
- Leer pack.json
- Cargar estado

## Fase 2 — Ejecución
- Ejecutar tarea
- Registrar resultados

## Fase 3 — Cierre
- Generar CHG
- Actualizar estado
"""
    phases = _extract_phases(mock_md)
    if len(phases) == 3:
        ok("flow:extract_phases")
    else:
        fail("flow:extract_phases", f"expected 3 got {len(phases)}: {phases}")

    # Test 3: render flowchart from mock
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tf:
        tf.write(mock_md)
        tf_path = pathlib.Path(tf.name)
    chart = _render_flowchart("W9", tf_path)
    if "W9" in chart and "Fase 1" in chart:
        ok("flow:render_chart")
    else:
        fail("flow:render_chart", chart[:200])
    tf_path.unlink()

    # Test 4: render a real workflow
    if wf_files:
        code, path = next(iter(wf_files.items()))
        try:
            chart = _render_flowchart(code, path)
            if code in chart:
                ok("flow:render_real_workflow")
            else:
                fail("flow:render_real_workflow", f"code not in chart: {chart[:100]}")
        except Exception as e:
            fail("flow:render_real_workflow", str(e))

    # Test 5: WORKFLOW_COLORS has entries
    if len(WORKFLOW_COLORS) >= 5:
        ok("flow:colors_defined")
    else:
        fail("flow:colors_defined", f"only {len(WORKFLOW_COLORS)} colors")

    total = 5
    passed = total - errors
    print(f"\n  {passed}/{total} tests pasaron")
    if errors:
        raise SystemExit(1)

import pathlib

# ─── Workflow state machine ───────────────────────────────────────────────────

def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _active_workflow() -> dict | None:
    gs = _load_json(GLOBAL_FILE)
    sp = gs.get("sprint_status", {})
    wf = sp.get("active_workflow")
    if not wf or wf in (None, "null", "none"):
        return None
    if isinstance(wf, dict):
        return wf
    return None


def cmd_start(argv: list) -> int:
    """flow start W2 [título...] — o modo interactivo sin args."""
    if not argv:
        # Modo interactivo: listar workflows disponibles y pedir título
        wf_files = _find_workflow_files()
        codes = list(wf_files.keys()) if wf_files else ["W2", "W3", "W4"]
        print(f"\n  Workflows disponibles: {', '.join(codes)}")
        try:
            wf_code = input("  Código de workflow [W2]: ").strip().upper() or "W2"
            title   = input(f"  Título de la tarea: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Cancelado.")
            return 0
        if not title:
            title = f"Trabajo en {wf_code}"
        argv = [wf_code, title]

    wf_code = argv[0].upper()
    title   = " ".join(argv[1:]) if len(argv) > 1 else f"Trabajo en {wf_code}"
    started = datetime.now(timezone.utc).isoformat()

    # Check if already active
    current = _active_workflow()
    if current:
        print(f"  ⚠️  Ya hay un workflow activo: {current.get('code')} — {current.get('title')}")
        print(f"  Cierra primero con: bago flow done")
        return 1

    wf_entry = {"code": wf_code, "title": title, "started": started}

    # Update global_state.json
    gs = _load_json(GLOBAL_FILE)
    if "sprint_status" not in gs:
        gs["sprint_status"] = {}
    gs["sprint_status"]["active_workflow"] = wf_entry
    _save_json(GLOBAL_FILE, gs)

    # Update sprint.json
    sp = _load_json(SPRINT_FILE)
    if "sprint_status" not in sp:
        sp["sprint_status"] = {}
    sp["sprint_status"]["active_workflow"] = wf_entry
    _save_json(SPRINT_FILE, sp)

    print(f"\n  ▶  Workflow iniciado: {wf_code}")
    print(f"  Título: {title}")
    print(f"  Inicio: {started[:19].replace('T', ' ')}")
    print(f"\n  Cierra con: bago flow done\n")
    return 0


def cmd_done(argv: list) -> int:
    """flow done — cierra el workflow activo."""
    current = _active_workflow()
    if not current:
        print("  No hay workflow activo. Inicia uno con: bago flow start <W2>")
        return 1

    wf_code = current.get("code", "?")
    title   = current.get("title", "—")
    started = current.get("started", "?")
    ended   = datetime.now(timezone.utc).isoformat()

    # Calculate duration
    try:
        s = datetime.fromisoformat(started)
        e = datetime.fromisoformat(ended)
        mins = int((e - s).total_seconds() / 60)
        duration = f"{mins // 60}h{mins % 60:02d}m" if mins >= 60 else f"{mins}m"
    except Exception:
        duration = "?"

    # Clear active_workflow from both files
    for path in (GLOBAL_FILE, SPRINT_FILE):
        data = _load_json(path)
        sp = data.get("sprint_status", {})
        sp["active_workflow"] = None
        sp["last_completed_workflow"] = {
            "code": wf_code, "title": title,
            "started": started, "ended": ended, "duration": duration,
        }
        data["sprint_status"] = sp
        _save_json(path, data)

    print(f"\n  ■  Workflow cerrado: {wf_code}")
    print(f"  Título:   {title}")
    print(f"  Duración: {duration}")
    print(f"  Fin:      {ended[:19].replace('T', ' ')}")

    # Optionally trigger session close
    close_tool = Path(__file__).parent / "session_close_generator.py"
    if close_tool.exists():
        import subprocess
        result = subprocess.run(
            [sys.executable, str(close_tool)],
            capture_output=True, text=True
        )
        if result.stdout.strip():
            print(f"\n  {result.stdout.strip()}")
    print()
    return 0


def cmd_status(argv: list) -> int:
    """flow status — muestra el workflow activo y alerta de tasks obsoletas."""
    current = _active_workflow()

    # ── Stale task alert ──────────────────────────────────────────────────────
    task_file = STATE_DIR / "pending_w2_task.json"
    if task_file.exists():
        try:
            task = json.loads(task_file.read_text(encoding="utf-8"))
            tstatus = task.get("status", "pending")
            if tstatus != "done":
                mtime = datetime.fromtimestamp(task_file.stat().st_mtime, tz=timezone.utc)
                days  = (datetime.now(timezone.utc) - mtime).total_seconds() / 86400
                if days >= 3:
                    title = task.get("idea_title", "—")
                    print(f"\n  ⚠️  TASK OBSOLETA: '{title}' lleva {int(days)}d sin cerrarse.")
                    print(f"  → Ciérrala con `bago flow done` o elimina pending_w2_task.json")
        except Exception:
            pass

    if not current:
        gs = _load_json(GLOBAL_FILE)
        last = gs.get("sprint_status", {}).get("last_completed_workflow")
        if last:
            print(f"\n  (sin workflow activo)")
            print(f"  Último: {last.get('code')} — {last.get('title')} [{last.get('duration')}]")
        else:
            print(f"  No hay workflow activo. Inicia con: bago flow start <W2> <título>")
        print()
        return 0

    wf_code = current.get("code", "?")
    title   = current.get("title", "—")
    started = current.get("started", "?")
    try:
        s = datetime.fromisoformat(started)
        now = datetime.now(timezone.utc)
        mins = int((now - s).total_seconds() / 60)
        elapsed = f"{mins // 60}h{mins % 60:02d}m" if mins >= 60 else f"{mins}m"
    except Exception:
        elapsed = "?"

    color = WORKFLOW_COLORS.get(wf_code, "")
    print(f"\n  {color}▶  {wf_code} — {title}{RESET}")
    print(f"  Iniciado: {started[:19].replace('T', ' ')}  (hace {elapsed})")
    print()
    return 0


def main():
    argv = sys.argv[1:]

    if not argv or argv == ["--list"]:
        cmd_list(None)
        return

    if argv[0] == "--test":
        run_tests()
        return

    if argv[0] in ("--help", "-h"):
        print(__doc__)
        return

    # State-machine subcommands
    if argv[0] == "start":
        raise SystemExit(cmd_start(argv[1:]))

    if argv[0] == "done":
        raise SystemExit(cmd_done(argv[1:]))

    if argv[0] == "status":
        raise SystemExit(cmd_status(argv[1:]))

    # Flowchart visualization (legacy / default)
    cmd_flow(argv[0])


if __name__ == "__main__":
    main()
