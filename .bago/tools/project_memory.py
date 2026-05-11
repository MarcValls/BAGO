#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
project_memory.py — Memoria distribuida por proyecto BAGO.

Arquitectura:
  Framework (bago_core/.bago/)          → tools, knowledge global, health
  Proyecto  (<proyecto>/.bago/)         → sesiones locales, tareas, learnings

Comandos:
  project-init    Inicializa .bago/ en el directorio actual del proyecto
  project-link    Vincula este proyecto al framework (redirige sesiones aquí)
  project-unlink  Desvincula el proyecto (sesiones vuelven al framework)
  project-state   Muestra el estado local del proyecto vinculado
  promote         Promueve un aprendizaje del proyecto al knowledge del framework

Uso:
  python3 project_memory.py project-init
  python3 project_memory.py project-link [--root /path/to/project]
  python3 project_memory.py project-unlink
  python3 project_memory.py project-state
  python3 project_memory.py promote "aprendizaje a promover al framework"
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

FRAMEWORK_ROOT  = Path(__file__).resolve().parents[2]   # bago_core
FRAMEWORK_STATE = FRAMEWORK_ROOT / ".bago" / "state"
FRAMEWORK_KB    = FRAMEWORK_ROOT / ".bago" / "knowledge"
GLOBAL_STATE    = FRAMEWORK_STATE / "global_state.json"
PATTERNS_FILE   = FRAMEWORK_KB / "project_patterns.md"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_global() -> dict:
    try:
        return json.loads(GLOBAL_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_global(data: dict) -> None:
    GLOBAL_STATE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def _load_project_state(project_root: Path) -> dict:
    ctx = project_root / ".bago" / "state" / "context.json"
    try:
        return json.loads(ctx.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_project_state(project_root: Path, data: dict) -> None:
    ctx = project_root / ".bago" / "state" / "context.json"
    ctx.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def _get_user_cwd() -> Path:
    """Return the directory the user was in when they invoked bago."""
    env_cwd = os.environ.get("BAGO_USER_CWD", "")
    if env_cwd:
        try:
            return Path(env_cwd).resolve()
        except Exception:
            pass
    return Path.cwd()


def _current_project_root() -> Path | None:
    state = _load_global()
    root = state.get("current_project", {}).get("root")
    return Path(root) if root else None

def _detect_project_from_cwd() -> Path | None:
    """Sube desde CWD buscando .bago/pack.json."""
    p = _get_user_cwd()
    for _ in range(6):
        if (p / ".bago" / "pack.json").exists():
            return p
        if p.parent == p:
            break
        p = p.parent
    return None

# ── Comandos ──────────────────────────────────────────────────────────────────

def cmd_project_init(args: list[str]) -> None:
    """Inicializa .bago/ en el directorio actual."""
    target = Path(args[0]).resolve() if args else _get_user_cwd()

    bago_dir = target / ".bago"
    if bago_dir.exists():
        print(f"⚠  Ya existe .bago/ en {target}")
        print("   Usa `bago project-link` para vincularlo al framework.")
        return

    # Detectar nombre del proyecto
    name = target.name

    # Crear estructura
    (bago_dir / "state" / "sessions").mkdir(parents=True, exist_ok=True)
    (bago_dir / "knowledge").mkdir(parents=True, exist_ok=True)

    # pack.json — config del proyecto
    pack = {
        "project": name,
        "type": "bago-project",
        "framework_root": str(FRAMEWORK_ROOT),
        "initialized": datetime.now(timezone.utc).isoformat(),
        "version": "1.0"
    }
    (bago_dir / "pack.json").write_text(
        json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # context.json — estado local
    context = {
        "project": name,
        "root": str(target),
        "sessions_count": 0,
        "last_session": None,
        "tasks_count": 0,
        "learnings_count": 0
    }
    _save_project_state(target, context)

    # learnings.md — aprendizajes locales vacío
    learnings_md = bago_dir / "state" / "learnings.md"
    learnings_md.write_text(
        f"# Learnings — {name}\n\n"
        "_Aprendizajes de este proyecto. Usa `bago promote <aprendizaje>` para promoverlos al framework._\n\n",
        encoding="utf-8"
    )

    # tasks.json
    (bago_dir / "state" / "tasks.json").write_text("[]", encoding="utf-8")

    # .gitignore en .bago/state (no commitear estado local)
    gitignore = bago_dir / "state" / ".gitignore"
    gitignore.write_text("sessions/\ntasks.json\ncontext.json\n", encoding="utf-8")

    print(f"✅ Proyecto '{name}' inicializado en {bago_dir}")
    print()
    print("  Estructura creada:")
    print(f"  {target.name}/.bago/")
    print(f"    pack.json          ← config del proyecto")
    print(f"    state/sessions/    ← historial de sesiones (local)")
    print(f"    state/learnings.md ← aprendizajes para promover")
    print(f"    state/tasks.json   ← tareas del proyecto")
    print(f"    knowledge/         ← conocimiento específico del proyecto")
    print()
    print("  Siguiente paso: `bago project-link` para redirigir sesiones aquí.")


def cmd_project_link(args: list[str]) -> None:
    """Vincula un proyecto al framework para guardar sesiones localmente."""
    # Determine project root
    if args and args[0] not in ("--root",):
        project_root = Path(args[0]).resolve()
    elif "--root" in args:
        idx = args.index("--root")
        project_root = Path(args[idx + 1]).resolve()
    else:
        # Try auto-detect from CWD
        detected = _detect_project_from_cwd()
        if detected:
            project_root = detected
        else:
            # Try CWD itself
            project_root = _get_user_cwd()

    pack_file = project_root / ".bago" / "pack.json"
    if not pack_file.exists():
        print(f"❌ No se encontró .bago/pack.json en {project_root}")
        print("   Primero inicializa: `bago project-init`")
        print(f"   O inicializa aquí: `bago project-init {project_root}`")
        sys.exit(1)

    pack = json.loads(pack_file.read_text(encoding="utf-8"))
    name = pack.get("project", project_root.name)

    # Update global_state
    state = _load_global()
    prev = state.get("current_project", {})
    state["current_project"] = {
        "name": name,
        "root": str(project_root),
        "linked_at": datetime.now(timezone.utc).isoformat(),
        "sessions_dir": str(project_root / ".bago" / "state" / "sessions")
    }
    _save_global(state)

    print(f"✅ Proyecto vinculado: '{name}'")
    print(f"   Root: {project_root}")
    print()
    if prev.get("name"):
        print(f"   (Anterior: '{prev['name']}')")
    print("  Las sesiones se guardarán en:")
    print(f"  {project_root}/.bago/state/sessions/")
    print()
    print("  Para desvincular: `bago project-unlink`")


def cmd_project_unlink(args: list[str]) -> None:
    """Desvincula el proyecto actual — sesiones vuelven al framework."""
    state = _load_global()
    prev = state.pop("current_project", None)
    _save_global(state)

    if prev:
        print(f"✅ Proyecto '{prev.get('name','?')}' desvinculado.")
    else:
        print("ℹ  No había proyecto vinculado.")
    print("  Las sesiones volverán al framework (bago_core/.bago/state/sessions/)")


def cmd_project_state(args: list[str]) -> None:
    """Muestra el estado del proyecto actualmente vinculado."""
    state = _load_global()
    cp = state.get("current_project")

    if not cp:
        detected = _detect_project_from_cwd()
        if detected:
            print(f"ℹ  Proyecto detectado en CWD: {detected}")
            print("   No está vinculado. Usa `bago project-link` para activarlo.")
        else:
            print("ℹ  Sin proyecto vinculado. Las sesiones van al framework.")
            print("   Usa `bago project-init` + `bago project-link` para activar memoria local.")
        return

    project_root = Path(cp["root"])
    project_ctx  = _load_project_state(project_root)

    sessions_dir = project_root / ".bago" / "state" / "sessions"
    sessions     = list(sessions_dir.glob("*.md")) if sessions_dir.exists() else []
    learnings_md = project_root / ".bago" / "state" / "learnings.md"
    learnings    = []
    if learnings_md.exists():
        text = learnings_md.read_text(encoding="utf-8")
        learnings = [l for l in text.splitlines() if l.startswith("- ")]

    kb_dir   = project_root / ".bago" / "knowledge"
    kb_files = list(kb_dir.glob("*.md")) if kb_dir.exists() else []

    sep = "─" * 48
    print(f"\n🗂  Proyecto activo: {cp['name']}")
    print(sep)
    print(f"  Root:     {project_root}")
    print(f"  Vinculado: {cp.get('linked_at','?')[:16]}")
    print(sep)
    print(f"  Sesiones locales:    {len(sessions)}")
    print(f"  Learnings pendientes: {len(learnings)}")
    print(f"  Knowledge local:     {len(kb_files)} archivos")
    print(sep)

    if learnings:
        print("\n  💡 Learnings pendientes de promover:")
        for l in learnings[:5]:
            print(f"    {l[:70]}")
        if len(learnings) > 5:
            print(f"    ... y {len(learnings)-5} más")
        print()
        print("  Usa `bago promote \"<texto>\"` para promoverlos al framework.")

    if sessions:
        recent = sorted(sessions)[-3:]
        print("\n  📁 Sesiones recientes:")
        for s in reversed(recent):
            print(f"    {s.name}")

    print()


def cmd_promote(args: list[str]) -> None:
    """Promueve un aprendizaje del proyecto al knowledge del framework."""
    if not args:
        print("❌ Indica qué aprendizaje promover:")
        print("   bago promote \"descripción del aprendizaje\"")
        print()
        print("   O sin argumento para modo interactivo desde learnings.md")
        _show_promote_interactive()
        return

    learning = " ".join(args).strip().strip('"').strip("'")
    if not learning:
        print("❌ El aprendizaje no puede estar vacío.")
        sys.exit(1)

    # Determine project
    state = _load_global()
    cp = state.get("current_project", {})
    project_name = cp.get("name", "unknown")

    # Ensure patterns file exists
    FRAMEWORK_KB.mkdir(parents=True, exist_ok=True)
    if not PATTERNS_FILE.exists():
        PATTERNS_FILE.write_text(
            "# Project Patterns — Cross-project Learnings\n\n"
            "_Aprendizajes promovidos desde proyectos individuales al framework._\n\n",
            encoding="utf-8"
        )

    # Append to framework knowledge
    ts   = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = f"- [{ts}] [{project_name}] {learning}\n"
    with PATTERNS_FILE.open("a", encoding="utf-8") as f:
        f.write(entry)

    # Remove from local learnings.md if it's there
    if cp.get("root"):
        local_md = Path(cp["root"]) / ".bago" / "state" / "learnings.md"
        if local_md.exists():
            text = local_md.read_text(encoding="utf-8")
            # Remove matching line (fuzzy: check if learning text is in any line)
            lines = text.splitlines(keepends=True)
            new_lines = [l for l in lines if learning.lower() not in l.lower()]
            if len(new_lines) < len(lines):
                local_md.write_text("".join(new_lines), encoding="utf-8")

    # Update knowledge_index in global_state
    ki = state.get("knowledge_index", {})
    promoted = ki.get("promoted_count", 0) + 1
    ki["promoted_count"] = promoted
    ki["last_promoted"] = ts
    ki["last_promoted_project"] = project_name
    state["knowledge_index"] = ki
    _save_global(state)

    print(f"✅ Aprendizaje promovido al framework:")
    print(f"   [{ts}] [{project_name}] {learning[:70]}")
    print(f"   → {PATTERNS_FILE}")
    print()
    print(f"   Total promovidos: {promoted}")


def _show_promote_interactive() -> None:
    """Muestra los learnings locales pendientes de promover."""
    cp = _load_global().get("current_project", {})
    if not cp.get("root"):
        print("ℹ  Sin proyecto vinculado.")
        return

    local_md = Path(cp["root"]) / ".bago" / "state" / "learnings.md"
    if not local_md.exists():
        print(f"ℹ  No hay learnings.md en {cp['root']}/.bago/state/")
        return

    text = local_md.read_text(encoding="utf-8")
    learnings = [l.strip() for l in text.splitlines() if l.strip().startswith("- ")]

    if not learnings:
        print(f"ℹ  Sin learnings pendientes en '{cp.get('name','?')}'.")
        return

    print(f"💡 Learnings pendientes en '{cp.get('name','?')}':\n")
    for i, l in enumerate(learnings, 1):
        print(f"  {i}. {l[2:].strip()[:80]}")
    print()
    print("Para promover uno:")
    print('  bago promote "texto del aprendizaje"')


def cmd_learn(args: list[str]) -> None:
    """Guarda un aprendizaje en learnings.md del proyecto actual."""
    if not args:
        print("❌ Indica qué aprender:")
        print('   bago learn "descripción del aprendizaje"')
        sys.exit(1)

    learning = " ".join(args).strip().strip('"').strip("'")
    state = _load_global()
    cp = state.get("current_project", {})

    if not cp.get("root"):
        print("⚠  Sin proyecto vinculado.")
        print("   El aprendizaje se guardará en el framework directamente.")
        cmd_promote(args)
        return

    project_root = Path(cp["root"])
    local_md = project_root / ".bago" / "state" / "learnings.md"
    local_md.parent.mkdir(parents=True, exist_ok=True)

    if not local_md.exists():
        local_md.write_text(
            f"# Learnings — {cp.get('name','?')}\n\n"
            "_Usa `bago promote` para promover al framework._\n\n",
            encoding="utf-8"
        )

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    with local_md.open("a", encoding="utf-8") as f:
        f.write(f"- [{ts}] {learning}\n")

    print(f"✅ Aprendizaje guardado en '{cp.get('name','?')}':")
    print(f"   {learning[:80]}")
    print()
    print("  Para promover al framework: `bago promote \"<texto>\"`")


# ── Entry point ───────────────────────────────────────────────────────────────

COMMAND_MAP = {
    "project-init":   cmd_project_init,
    "init":           cmd_project_init,   # alias: bago project init
    "project-link":   cmd_project_link,
    "link":           cmd_project_link,   # alias: bago project link
    "project-unlink": cmd_project_unlink,
    "unlink":         cmd_project_unlink, # alias: bago project unlink
    "project-state":  cmd_project_state,
    "state":          cmd_project_state,  # alias: bago project state
    "promote":        cmd_promote,
    "learn":          cmd_learn,
}

def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return

    if args[0] == "--test":
        _self_test()
        return

    cmd = args[0]
    rest = args[1:]

    if cmd not in COMMAND_MAP:
        print(f"❌ Comando desconocido: {cmd}")
        print(f"   Disponibles: {', '.join(COMMAND_MAP.keys())}")
        sys.exit(1)

    COMMAND_MAP[cmd](rest)


def _self_test() -> None:
    import tempfile
    fails = 0

    # Test 1: project-init creates structure
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        cmd_project_init([str(p)])
        assert (p / ".bago" / "pack.json").exists(), "pack.json missing"
        assert (p / ".bago" / "state" / "sessions").is_dir(), "sessions/ missing"
        assert (p / ".bago" / "state" / "learnings.md").exists(), "learnings.md missing"

    # Test 2: promote appends to patterns file
    import tempfile as tf
    with tf.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("# Patterns\n\n")
        tmp_path = Path(f.name)
    global PATTERNS_FILE
    orig = PATTERNS_FILE
    PATTERNS_FILE = tmp_path
    cmd_promote(["test learning from project X"])
    text = tmp_path.read_text()
    assert "test learning from project X" in text, "promote failed"
    PATTERNS_FILE = orig
    tmp_path.unlink()

    # Test 3: learn saves to local learnings.md
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        cmd_project_init([str(p)])
        state = _load_global()
        orig_cp = state.get("current_project")
        state["current_project"] = {"name": "test", "root": str(p)}
        _save_global(state)
        cmd_learn(["aprendizaje test 123"])
        lmd = p / ".bago" / "state" / "learnings.md"
        assert "aprendizaje test 123" in lmd.read_text(), "learn failed"
        # Restore
        if orig_cp:
            state["current_project"] = orig_cp
        else:
            state.pop("current_project", None)
        _save_global(state)

    print("  3/3 tests pasaron")


if __name__ == "__main__":
    main()
