from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from bago_core.launcher._paths import (
    BAGO_ROOT, BAGO_CORE_DIR, TOOLS, CORE,
    GREEN, RED, YELLOW, CYAN, BOLD, DIM, default_user_home,
)
from bago_core.launcher._config import (
    load_bp, load_dispatcher, load_context, load_registry_mod,
    build_commands, build_deprecated_map, get_module_for_cmd,
    COMMANDS, DEPRECATED_MAP,
)


def _resolve_engine_profile() -> str:
    """Return the publication profile to preserve when refreshing the engine."""
    candidates: list[Path] = []
    program_files = os.environ.get("ProgramFiles")
    if program_files:
        candidates.append(Path(program_files) / "BAGO" / "runtime_contract.json")
    candidates.append(BAGO_ROOT.parent / "runtime_contract.json")
    candidates.append(BAGO_ROOT.parent / "docs" / "runtime_contract.json")

    for path in candidates:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        profile = data.get("install_profile")
        if profile:
            return str(profile)
        if "knowledge_included" in data:
            return "with-knowledge" if data["knowledge_included"] else "without-knowledge"
        publication = data.get("publication")
        if isinstance(publication, dict):
            default = publication.get("default_profile")
            if default:
                return str(default)
    return "with-knowledge"


def _cmd_dev(rest: list) -> None:
    """bago dev refresh-engine [--with-knowledge|--without-knowledge]."""
    if not rest or rest[0] != "refresh-engine":
        print("  Uso: bago dev refresh-engine [--with-knowledge|--without-knowledge]")
        return

    if sys.platform != "win32":
        print("  refresh-engine solo está soportado en Windows.")
        return

    profile = _resolve_engine_profile()
    for arg in rest[1:]:
        low = str(arg).lower()
        if low == "--with-knowledge":
            profile = "with-knowledge"
        elif low == "--without-knowledge":
            profile = "without-knowledge"
        elif low in ("-h", "--help"):
            print("  Uso: bago dev refresh-engine [--with-knowledge|--without-knowledge]")
            print("  Reinstala el motor limpio y lo valida al final.")
            return
        else:
            print(f"  Argumento no reconocido: {arg}")
            print("  Uso: bago dev refresh-engine [--with-knowledge|--without-knowledge]")
            return

    installer = BAGO_ROOT.parent / "install.ps1"
    if not installer.exists():
        print(f"  ❌ install.ps1 no encontrado en {installer}")
        return

    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        print("  ❌ No se encontró PowerShell para ejecutar install.ps1")
        return

    install_cmd = [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(installer)]
    if profile == "without-knowledge":
        install_cmd.append("-NoKnowledge")

    print()
    print("  BAGO Dev · Refresh Engine")
    print("  " + "-" * 42)
    print(f"  Perfil: {profile}")
    print(f"  Motor destino: {BAGO_ROOT.parent}")
    print()

    result = subprocess.run(install_cmd, cwd=str(BAGO_ROOT.parent))
    if result.returncode != 0:
        sys.exit(result.returncode)

    installed_launcher = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "BAGO" / "bago.ps1"
    if installed_launcher.exists():
        print()
        print("  Validando motor instalado...")
        validation = subprocess.run(
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(installed_launcher), "validate"],
            cwd=str(BAGO_ROOT.parent),
        )
        if validation.returncode != 0:
            sys.exit(validation.returncode)

    print()
    print("  ✓ Motor refrescado y validado")


# ── Extensiones Copilot CLI ────────────────────────────────────────────────────

def _install_extensions(bago_root=None, silent=False):
    """Copia .bago/extensions/*/extension.mjs → .github/extensions/*/extension.mjs"""
    src_base  = (bago_root or BAGO_ROOT) / "extensions"
    repo_root = (bago_root or BAGO_ROOT).parent
    dest_base = repo_root / ".github" / "extensions"

    if not src_base.exists():
        if not silent:
            print("  ℹ  No hay extensiones en .bago/extensions/")
        return []

    installed = []
    for ext_dir in sorted(src_base.iterdir()):
        src_file = ext_dir / "extension.mjs"
        if not src_file.exists():
            continue
        dest_dir  = dest_base / ext_dir.name
        dest_file = dest_dir / "extension.mjs"
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src_file), str(dest_file))
        installed.append(ext_dir.name)

    if installed and not silent:
        for name in installed:
            print(f"  🔌 Extensión instalada: {name}")
    return installed

def _cmd_extensions():
    """Lista extensiones disponibles e instala si hay cambios."""
    src_base = BAGO_ROOT / "extensions"
    if not src_base.exists() or not any(src_base.iterdir()):
        print("  No hay extensiones BAGO en .bago/extensions/")
        return

    print()
    print("  ┌──────────────────────────────────────────────┐")
    print("  │  BAGO · Extensiones Copilot CLI              │")
    print("  └──────────────────────────────────────────────┘")
    for ext_dir in sorted(src_base.iterdir()):
        if (ext_dir / "extension.mjs").exists():
            dest = BAGO_ROOT.parent / ".github" / "extensions" / ext_dir.name / "extension.mjs"
            status = "✅ instalada" if dest.exists() else "⚠️  pendiente"
            print(f"  🔌 {ext_dir.name:30s} {status}")
    print()
    print("  Reinstalar: bago setup")
    print()

# ── Helpers de estado ──────────────────────────────────────────────────────────

def _read_state(bago_root=None):
    f = (bago_root or BAGO_ROOT) / "state" / "global_state.json"
    if not f.exists():
        return {}
    with open(f) as fh:
        return json.load(fh)

def _write_state(state, bago_root=None):
    f = (bago_root or BAGO_ROOT) / "state" / "global_state.json"
    with open(f, "w") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

def _set_mode(mode, bago_root=None):
    s = _read_state(bago_root)
    s["distribution_mode"] = mode
    _write_state(s, bago_root)

def _is_template_seed():
    return _read_state().get("distribution_mode") == "template_seed"

# ── Scaffold de proyecto nuevo ─────────────────────────────────────────────────

def _scaffold_project(dest_input):
    src = BAGO_ROOT.parent
    dest = Path(dest_input.strip()).expanduser().resolve() if dest_input.strip() else src

    if dest == src:
        _set_mode("project_active")
        _auto_sync(src)
        _install_extensions(silent=True)
        print(f"\n  ✅ Proyecto inicializado en: {dest}\n")
        return True

    try:
        dest.relative_to(src)
        print("  ⚠  El destino no puede estar dentro del directorio fuente.")
        return False
    except ValueError:
        pass

    if dest.exists() and any(dest.iterdir()):
        print(f"  ⚠  El directorio ya existe y no está vacío:\n     {dest}")
        return False

    print(f"\n  📦 Copiando pack a: {dest}")
    dest.mkdir(parents=True, exist_ok=True)

    shutil.copytree(str(BAGO_ROOT), str(dest / ".bago"))
    shutil.copy2(str(src / "bago"), str(dest / "bago"))
    if sys.platform != "win32":
        os.chmod(str(dest / "bago"), 0o755)
    # Windows: copiar bago.cmd para que `bago` sea invocable desde CMD/PowerShell
    if sys.platform == "win32" and (src / "bago.cmd").exists():
        shutil.copy2(str(src / "bago.cmd"), str(dest / "bago.cmd"))
    if (src / "Makefile").exists():
        shutil.copy2(str(src / "Makefile"), str(dest / "Makefile"))

    _set_mode("project_active", dest / ".bago")

    subprocess.run(
        [sys.executable, str(dest / "bago"), "setup"],
        cwd=str(dest)
    )

    print(f"\n  ✅ Proyecto listo en: {dest}")
    print(f"  ▶  cd \"{dest}\" && bago\n")
    return True

# ── Prompt de arranque ─────────────────────────────────────────────────────────

def _prompt_mode():
    """Mostrado la primera vez que se ejecuta una cleanversion."""
    print()
    print("  ┌─────────────────────────────────────────────┐")
    print("  │  BAGO · Primera ejecución                   │")
    print("  ├─────────────────────────────────────────────┤")
    print("  │  [1] Evolucionar el framework BAGO          │")
    print("  │  [2] Iniciar un proyecto nuevo              │")
    print("  └─────────────────────────────────────────────┘")
    print()

    try:
        choice = input("  Elige [1/2]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)

    if choice == "1":
        _set_mode("framework_host")
        print("\n  ✅ Modo framework activado.\n")
        return "banner"

    elif choice == "2":
        default = str(BAGO_ROOT.parent)
        print(f"\n  Ruta del proyecto nuevo")
        print(f"  (Enter = directorio actual: {default})")
        try:
            dest_input = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        return "done" if _scaffold_project(dest_input) else "error"

    else:
        print("\n  Opción no válida. Usa 1 o 2.\n")
        return "invalid"

# ── bago versions ─────────────────────────────────────────────────────────────

def _cmd_versions():
    """Lista todas las cleanversions encontradas junto al script."""
    cv_dir = Path(__file__).resolve().parent.parent / "cleanversion"
    if not cv_dir.exists():
        cv_dir = Path(__file__).resolve().parent / "cleanversion"
    if not cv_dir.exists():
        print("  No se encontró directorio cleanversion/")
        return

    entries = sorted(d for d in cv_dir.iterdir() if d.is_dir() and not d.name.startswith('.'))
    if not entries:
        print("  No hay cleanversions.")
        return

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Cleanversions disponibles                          │")
    print("  └─────────────────────────────────────────────────────────────┘")

    for d in entries:
        info_file  = d / "VERSION_INFO.json"
        state_file = d / ".bago" / "state" / "global_state.json"

        info  = json.loads(info_file.read_text())  if info_file.exists()  else {}
        state = json.loads(state_file.read_text()) if state_file.exists() else {}

        chg_dir   = d / ".bago" / "state" / "changes"
        chg_count = len(list(chg_dir.glob("BAGO-CHG-*.json"))) if chg_dir.exists() else 0

        slug   = info.get("slug", d.name)
        name   = info.get("display_name", "—")
        desc   = info.get("description", "")
        mode   = state.get("distribution_mode") or "—"
        script = info.get("bago_script", "—")
        notes  = info.get("notes", "")

        print()
        print(f"  📦 {slug}")
        print(f"     {name}")
        print(f"     {desc}")
        print(f"     mode={mode} | CHG={chg_count} | bago={script}")
        if notes:
            print(f"     💡 {notes}")

    print()

# ── Auto-sync silencioso ───────────────────────────────────────────────────────

# Commands that need fresh repo context — only these trigger _auto_sync().
# Read-only / diagnostic commands must NOT write repo_context.json on every run
# (it is a git-tracked generated_artifact and causes permanent git status noise).
_SYNC_CMDS = frozenset({
    "setup", "session", "cosecha", "audit", "dashboard", "detector", "task",
})

def _auto_sync(cwd=None):
    try:
        subprocess.run(
            [sys.executable, str(TOOLS / "repo_context_guard.py"), "sync"],
            cwd=str(cwd or BAGO_ROOT.parent),
            capture_output=True,
            timeout=5
        )
    except Exception:
        pass

# ── Main ───────────────────────────────────────────────────────────────────────