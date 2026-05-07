#!/usr/bin/env python3
"""
siembra_manager.py — BAGO v3.0 · Gestión de siembras

Una **siembra** es la huella mínima de BAGO en un proyecto externo:
tools de scope=project/both + pack.json + bago.db local.

Comandos:
  bago siembra create <ruta>   → planta una siembra en el repo
  bago siembra list            → lista todas las siembras registradas
  bago siembra update <ruta>   → actualiza herramientas de la siembra
  bago siembra diff <ruta>     → diferencias entre la siembra y el PADRE actual
  bago siembra sync --all      → actualiza todas las siembras registradas
  bago siembra status          → resumen de salud de todas las siembras

Referencia de diseño: .bago/core/architecture/PADRE_SIEMBRA.md
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Rutas ─────────────────────────────────────────────────────────────────────
TOOLS_DIR  = Path(__file__).resolve().parent
BAGO_ROOT  = TOOLS_DIR.parent
STATE_DIR  = BAGO_ROOT / "state"
SIEMBRAS_PATH = STATE_DIR / "siembras.json"
PACK_JSON  = BAGO_ROOT / "pack.json"
DB_PATH    = STATE_DIR / "bago.db"

# Versión de siembra que crea este manager
SIEMBRA_VERSION = "3.0"

# ── Herramientas incluidas en una siembra (scope = project | both) ────────────
# Fuente canónica: PADRE_SIEMBRA.md §"Qué herramientas van en la siembra"
SIEMBRA_TOOLS: list[str] = [
    # scope=project
    "scan.py", "code_review.py", "commit_readiness.py", "pre_push_guard.py",
    "secret_scan.py", "debt_ledger.py", "risk_matrix.py", "naming_check.py",
    "type_check.py", "dep_audit.py", "code_quality_orchestrator.py",
    # scope=both
    "bago_start.py", "bago_next.py", "emit_ideas.py", "ideas_selector.py",
    "bago_session_router.py", "show_task.py", "flow.py",
    "sprint_manager.py", "goals.py", "workflow_selector.py", "bago_reopen.py",
    "cosecha.py", "bago_audit_router.py", "bago_context.py", "insights.py",
    "habit.py", "chronicle_reporter.py", "bago_diff.py", "flow.py",
    "stale_detector.py", "sprint_summary.py", "bago_utils.py",
    "context_detector.py", "context_map.py", "git_context.py",
    "session_logger.py", "session_opener.py", "session_close_generator.py",
    "tool_registry.py", "preflight.py",
]

# Launcher mínimo que genera la siembra (template)
_LAUNCHER_TEMPLATE = '''\
#!/usr/bin/env python3
"""bago — launcher de siembra {name}.
Delega al PADRE para comandos de framework; ejecuta herramientas locales
para comandos de proyecto (scope=project/both).

BAGO_PADRE_PATH configurado en pack.json → padre_path.
"""
import os, sys, subprocess
from pathlib import Path

LOCAL_BAGO = Path(__file__).resolve().parent / ".bago"
PACK       = LOCAL_BAGO / "pack.json"

def _read_padre_path() -> str | None:
    try:
        return json.loads(PACK.read_text(encoding="utf-8")).get("padre_path")
    except Exception:
        return None

import json
PADRE_PATH = os.environ.get("BAGO_PADRE_PATH") or _read_padre_path()
PADRE_LAUNCHER = Path(PADRE_PATH) / "bago" if PADRE_PATH else None

FRAMEWORK_CMDS = {{
    "health", "validate", "sync", "auto", "heal", "doctor",
    "scope", "cabinet", "install", "rules", "report", "banner",
    "db", "hello", "check", "consistency", "stability", "efficiency",
}}

cmd = sys.argv[1] if len(sys.argv) > 1 else "start"

if cmd in FRAMEWORK_CMDS:
    if not PADRE_LAUNCHER or not PADRE_LAUNCHER.exists():
        print("⚠️  Comando de framework. Configura BAGO_PADRE_PATH en .bago/pack.json o env.")
        sys.exit(1)
    sys.exit(subprocess.run([sys.executable, str(PADRE_LAUNCHER)] + sys.argv[1:]).returncode)
else:
    tool_map = {{}}
    for f in (LOCAL_BAGO / "tools").glob("*.py"):
        tool_map[f.stem] = f
    # Buscar módulo del comando en tool_registry local
    tr_path = LOCAL_BAGO / "tools" / "tool_registry.py"
    if tr_path.exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location("tool_registry", tr_path)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        entry = mod.REGISTRY.get(cmd)
        if entry:
            module_path = LOCAL_BAGO / "tools" / (entry.module + ".py")
            if module_path.exists():
                sys.exit(subprocess.run([sys.executable, str(module_path)] + sys.argv[2:]).returncode)
    print(f"[bago siembra] Comando desconocido: {{cmd}}")
    sys.exit(1)
'''


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_siembras() -> dict:
    """Carga siembras.json; devuelve estructura vacía si no existe."""
    if SIEMBRAS_PATH.exists():
        try:
            return json.loads(SIEMBRAS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"_meta": "Siembras registradas en el PADRE.", "siembras": []}


def _save_siembras(data: dict) -> None:
    SIEMBRAS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _find_siembra(data: dict, path_or_name: str) -> dict | None:
    for s in data.get("siembras", []):
        if s.get("name") == path_or_name or s.get("path") == path_or_name:
            return s
    return None


def _padre_version() -> str:
    try:
        return json.loads(PACK_JSON.read_text(encoding="utf-8")).get("version", "?")
    except Exception:
        return "?"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _init_siembra_db(db_path: Path) -> None:
    """Crea un bago.db mínimo en la siembra si no existe."""
    if db_path.exists():
        return
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            slot INTEGER,
            generation INTEGER,
            priority INTEGER DEFAULT 50,
            requires TEXT DEFAULT '[]',
            blocks TEXT DEFAULT '[]',
            extra_cond TEXT DEFAULT 'always',
            summary TEXT,
            w2 TEXT,
            metric TEXT,
            done INTEGER DEFAULT 0,
            done_at TEXT
        );
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            task_type TEXT,
            workflow TEXT,
            roles TEXT,
            user_goal TEXT,
            status TEXT,
            escenario TEXT,
            created_at TEXT,
            updated_at TEXT,
            summary TEXT,
            next_step TEXT,
            linked_commits TEXT,
            source_file TEXT
        );
    """)
    conn.commit()
    conn.close()


# ── Comandos ──────────────────────────────────────────────────────────────────

def cmd_create(target_path: str) -> int:
    """Planta una siembra mínima en el directorio especificado."""
    target = Path(target_path).resolve()
    if not target.exists():
        print(f"  ❌ Directorio no encontrado: {target}")
        return 1

    name  = target.name
    bago  = target / ".bago"
    tools = bago / "tools"
    state = bago / "state"

    print(f"\n  🌱 Creando siembra en: {target}")
    print(f"     Nombre: {name}")

    # Crear estructura de directorios
    for d in [bago, tools, state]:
        d.mkdir(parents=True, exist_ok=True)

    # Copiar herramientas de la siembra
    copied = 0
    skipped = 0
    for tool_name in SIEMBRA_TOOLS:
        src = TOOLS_DIR / tool_name
        dst = tools / tool_name
        if not src.exists():
            skipped += 1
            continue
        if dst.exists():
            skipped += 1
            continue
        shutil.copy2(src, dst)
        copied += 1

    print(f"     Tools copiadas: {copied}  (omitidas/inexistentes: {skipped})")

    # pack.json de la siembra
    pack = {
        "name": name,
        "type": "siembra",
        "padre_path": str(BAGO_ROOT.parent),
        "bago_version": SIEMBRA_VERSION,
        "seeded_at": _now_iso(),
        "seeded_from": _padre_version(),
        "tools_included": [t.replace(".py", "") for t in SIEMBRA_TOOLS if (TOOLS_DIR / t).exists()],
    }
    (bago / "pack.json").write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")

    # bago.db vacío
    _init_siembra_db(state / "bago.db")

    # Launcher mínimo
    launcher = target / "bago"
    if not launcher.exists():
        launcher.write_text(_LAUNCHER_TEMPLATE.format(name=name), encoding="utf-8")
        print(f"     Launcher:  bago  ✅")
    else:
        print(f"     Launcher:  bago  (ya existía, no modificado)")

    # Registrar en siembras.json del PADRE
    data = _load_siembras()
    existing = _find_siembra(data, str(target))
    if existing:
        existing.update({
            "seeded_from": _padre_version(),
            "last_sync": _now_iso(),
            "estado": "activa",
        })
        print(f"     Registro:  actualizado en siembras.json")
    else:
        data.setdefault("siembras", []).append({
            "name": name,
            "path": str(target),
            "tipo": "siembra_v3",
            "seeded_at": _now_iso(),
            "seeded_from": _padre_version(),
            "last_sync": _now_iso(),
            "estado": "activa",
        })
        print(f"     Registro:  añadida a siembras.json ✅")
    _save_siembras(data)

    print(f"\n  ✅ Siembra creada en {target}")
    print(f"     Conectar al PADRE: export BAGO_PADRE_PATH={BAGO_ROOT.parent}")
    print(f"     O editar: {bago / 'pack.json'}\n")
    return 0


def cmd_list() -> int:
    """Lista todas las siembras registradas."""
    data = _load_siembras()
    siembras = data.get("siembras", [])
    if not siembras:
        print("  (sin siembras registradas — usa: bago siembra create <ruta>)")
        return 0

    print(f"\n  PADRE: {BAGO_ROOT.parent}  (v{_padre_version()})")
    print(f"  Siembras registradas: {len(siembras)}\n")
    print(f"  {'Nombre':<20} {'Estado':<12} {'Tipo':<20} {'Último sync':<12}  Ruta")
    print("  " + "-" * 90)
    for s in siembras:
        name      = s.get("name", "?")[:19]
        estado    = s.get("estado", "?")[:11]
        tipo      = s.get("tipo", "?")[:19]
        last_sync = s.get("last_sync") or s.get("seeded_at") or "—"
        path      = s.get("path", "?")
        exists    = "✅" if Path(path).exists() else "❌"
        print(f"  {name:<20} {estado:<12} {tipo:<20} {last_sync:<12}  {exists} {path}")
    print()
    return 0


def cmd_update(target_path: str) -> int:
    """Actualiza las herramientas de una siembra existente."""
    data = _load_siembras()
    target = Path(target_path).resolve()

    # Buscar por ruta o nombre
    siembra = _find_siembra(data, str(target)) or _find_siembra(data, target_path)
    if not siembra:
        print(f"  ⚠️  Siembra no registrada: {target_path}")
        print(f"     Usa: bago siembra create {target_path}")
        return 1

    real_path = Path(siembra["path"])
    if not real_path.exists():
        print(f"  ❌ Ruta no encontrada: {real_path}")
        return 1

    tools = real_path / ".bago" / "tools"
    tools.mkdir(parents=True, exist_ok=True)

    updated = 0
    for tool_name in SIEMBRA_TOOLS:
        src = TOOLS_DIR / tool_name
        dst = tools / tool_name
        if not src.exists():
            continue
        shutil.copy2(src, dst)
        updated += 1

    siembra["last_sync"] = _now_iso()
    siembra["seeded_from"] = _padre_version()
    _save_siembras(data)

    print(f"  ✅ Siembra actualizada: {siembra['name']}")
    print(f"     Tools actualizadas: {updated}")
    print(f"     Versión PADRE: {_padre_version()}")
    return 0


def cmd_diff(target_path: str) -> int:
    """Muestra diferencias entre herramientas de la siembra y el PADRE."""
    data = _load_siembras()
    target = Path(target_path).resolve()
    siembra = _find_siembra(data, str(target)) or _find_siembra(data, target_path)

    if not siembra:
        print(f"  ⚠️  Siembra no registrada: {target_path}")
        return 1

    real_path = Path(siembra["path"])
    tools     = real_path / ".bago" / "tools"

    print(f"\n  Diff: {siembra['name']}  ←→  PADRE v{_padre_version()}")
    print(f"  {'Herramienta':<35} {'PADRE':<12} {'Siembra':<12} Estado")
    print("  " + "-" * 75)

    diffs = 0
    for tool_name in SIEMBRA_TOOLS:
        src = TOOLS_DIR / tool_name
        dst = tools / tool_name
        if not src.exists():
            continue
        if not dst.exists():
            print(f"  {tool_name:<35} {'presente':<12} {'ausente':<12} ⚠️  falta en siembra")
            diffs += 1
            continue
        src_size = src.stat().st_size
        dst_size = dst.stat().st_size
        src_mtime = src.stat().st_mtime
        dst_mtime = dst.stat().st_mtime
        if src_size != dst_size or src_mtime > dst_mtime:
            print(f"  {tool_name:<35} {src_size:<12} {dst_size:<12} 🔄 desactualizada")
            diffs += 1
        else:
            print(f"  {tool_name:<35} {src_size:<12} {dst_size:<12} ✅ al día")

    print()
    if diffs == 0:
        print(f"  ✅ Siembra al día — 0 diferencias")
    else:
        print(f"  ⚠️  {diffs} herramienta(s) desactualizadas → usa: bago siembra update {real_path}")
    print()
    return 0


def cmd_sync_all() -> int:
    """Actualiza todas las siembras activas registradas."""
    data  = _load_siembras()
    activas = [s for s in data.get("siembras", []) if s.get("estado") == "activa"]
    if not activas:
        print("  (sin siembras activas)")
        return 0
    print(f"  Sincronizando {len(activas)} siembra(s)...")
    errors = 0
    for s in activas:
        rc = cmd_update(s["path"])
        if rc != 0:
            errors += 1
    print(f"\n  ✅ Sync completado — errores: {errors}/{len(activas)}")
    return 0 if errors == 0 else 1


def cmd_status() -> int:
    """Resumen de estado de todas las siembras."""
    data = _load_siembras()
    siembras = data.get("siembras", [])
    activas  = sum(1 for s in siembras if s.get("estado") == "activa")
    archivadas = sum(1 for s in siembras if s.get("estado") == "archivada")
    print(f"\n  Siembras PADRE v{_padre_version()}")
    print(f"  Total: {len(siembras)}  |  Activas: {activas}  |  Archivadas: {archivadas}")
    outdated = 0
    for s in siembras:
        if s.get("estado") != "activa":
            continue
        real = Path(s.get("path", ""))
        if not real.exists():
            print(f"  ❌ {s['name']} — ruta no encontrada: {real}")
            outdated += 1
            continue
        last_sync = s.get("last_sync") or "?"
        print(f"  ✅ {s['name']:<20}  sync: {last_sync}  ({real})")
    print()
    return 0


def _self_test() -> None:
    """Autotest mínimo."""
    assert SIEMBRAS_PATH.parent.exists(), "state/ no encontrado"
    data = _load_siembras()
    assert isinstance(data, dict)
    assert isinstance(data.get("siembras", []), list)
    print("  1/1 tests pasaron")


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = sys.argv[1:]

    if not args or args[0] in ("--help", "-h"):
        print(__doc__)
        return

    if "--test" in args:
        _self_test()
        return

    subcmd = args[0]

    if subcmd == "create":
        if len(args) < 2:
            print("  Uso: bago siembra create <ruta>")
            sys.exit(1)
        sys.exit(cmd_create(args[1]))

    elif subcmd == "list":
        sys.exit(cmd_list())

    elif subcmd == "update":
        if len(args) < 2:
            print("  Uso: bago siembra update <ruta-o-nombre>")
            sys.exit(1)
        sys.exit(cmd_update(args[1]))

    elif subcmd == "diff":
        if len(args) < 2:
            print("  Uso: bago siembra diff <ruta-o-nombre>")
            sys.exit(1)
        sys.exit(cmd_diff(args[1]))

    elif subcmd in ("sync", "sync-all"):
        sys.exit(cmd_sync_all())

    elif subcmd == "status":
        sys.exit(cmd_status())

    else:
        print(f"  ❌ Subcomando desconocido: {subcmd}")
        print("     Usa: create | list | update | diff | sync | status")
        sys.exit(1)


if __name__ == "__main__":
    main()
