"""
orphan_detector.py — BAGO daemon vigilante de módulos huérfanos.

Detecta archivos .py en .bago/tools/ que NO están registrados en _registry_entries.py.
Un módulo huérfano es invisible para el sistema BAGO (no aparece en bago --help,
no tiene tests automáticos, no se audita).

Modos de uso:
    bago orphans                # Listar huérfanos
    bago orphans --fix          # Auto-registrar como LEGACY (interactivo)
    bago orphans --strict       # Salir con código 1 si hay huérfanos nuevos
    bago orphans --baseline     # Guardar baseline actual (suprimir alertas de los existentes)
    python3 orphan_detector.py  # Direct execution
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ── paths ─────────────────────────────────────────────────────────────────────
_TOOLS = Path(__file__).resolve().parent
_STATE = _TOOLS.parent / "state"
_REGISTRY = _TOOLS / "_registry_entries.py"
_BASELINE = _STATE / "orphan_baseline.json"

# Modules that are infrastructure (not commands) — intentionally not in registry
_INFRA_MODULES: set[str] = {
    "_registry_entries",
    "_registry_models",
    "_registry_paths",
    "_registry_taxonomy",
    "_bago_paths",
    "__init__",
}


# ── core logic ────────────────────────────────────────────────────────────────

def get_registered_modules() -> set[str]:
    """Return set of module names referenced in _registry_entries.py."""
    if not _REGISTRY.exists():
        return set()
    text = _REGISTRY.read_text(encoding="utf-8")
    return set(re.findall(r'module=["\']([^"\']+)["\']', text))


def get_tool_modules() -> set[str]:
    """Return set of module names (without .py) in .bago/tools/."""
    return {
        p.stem
        for p in _TOOLS.glob("*.py")
        if not p.stem.startswith("__")
    }


def find_orphans() -> list[str]:
    """Return sorted list of orphan module names."""
    registered = get_registered_modules()
    all_tools = get_tool_modules()
    orphans = all_tools - registered - _INFRA_MODULES
    return sorted(orphans)


def load_baseline() -> set[str]:
    """Load known orphans from baseline (these are tolerated)."""
    if _BASELINE.exists():
        try:
            data = json.loads(_BASELINE.read_text(encoding="utf-8"))
            return set(data.get("known_orphans", []))
        except (json.JSONDecodeError, KeyError):
            return set()
    return set()


def save_baseline(orphans: list[str]) -> None:
    """Persist current orphan list as the new baseline."""
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "known_orphans": sorted(orphans),
        "count": len(orphans),
    }
    _BASELINE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"✅ Baseline guardado: {len(orphans)} módulos huérfanos conocidos")


# ── display ───────────────────────────────────────────────────────────────────

def _print_report(orphans: list[str], new_orphans: list[str]) -> None:
    total = len(orphans)
    new = len(new_orphans)

    print(f"\n🌀 BAGO Orphan Detector — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("─" * 52)
    print(f"  Total huérfanos    : {total}")
    print(f"  Nuevos (no en baseline): {new}")
    print(f"  Registrados OK     : {len(get_registered_modules())}")
    print(f"  Total .py en tools : {len(get_tool_modules())}")
    print()

    if new_orphans:
        print("🚨 NUEVOS módulos huérfanos (fuera de baseline):")
        for m in new_orphans:
            size = (_TOOLS / f"{m}.py").stat().st_size
            print(f"    ❌ {m:<40} {size:>7} bytes")
        print()

    if orphans and not new_orphans:
        print("✅ Sin nuevos huérfanos — todos están en baseline")
    elif not orphans:
        print("✅ Sin huérfanos — todos los módulos están registrados")

    if total > 0:
        print(f"\n💡 Para gestionar: bago orphans --baseline (tolerar) | bago orphans --fix (registrar)")

    print()


# ── auto-register (--fix) ─────────────────────────────────────────────────────

def cmd_fix(orphans: list[str]) -> int:
    """Interactively register orphans as LEGACY entries."""
    if not orphans:
        print("✅ Sin huérfanos que registrar.")
        return 0

    print(f"\n🔧 Registrando {len(orphans)} módulos huérfanos como LEGACY...\n")
    print("  Estos módulos serán visibles en `bago --help` con stability=legacy.")
    print("  Puedes editarlos manualmente en _registry_entries.py después.\n")

    try:
        confirm = input(f"  ¿Continuar? [s/N]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\n⛔ Cancelado.")
        return 0

    if confirm not in ("s", "si", "y", "yes"):
        print("  Cancelado.")
        return 0

    # Read current registry
    reg_text = _REGISTRY.read_text(encoding="utf-8")

    # Find insertion point — just before the last closing brace of the dict
    # Look for the "spiral-agent" or last known entry
    new_entries: list[str] = []
    for mod in orphans:
        py_path = _TOOLS / f"{mod}.py"
        # Try to extract a docstring for description
        try:
            first_lines = py_path.read_text(encoding="utf-8", errors="ignore").split("\n")[:3]
            desc = ""
            for line in first_lines:
                line = line.strip().strip('"""').strip("'''").strip()
                if line and not line.startswith("#") and not line.startswith("import"):
                    desc = line[:80]
                    break
        except Exception:
            desc = f"Módulo {mod} (sin descripción)"
        if not desc:
            desc = f"Módulo {mod} (legacy — auto-registrado por orphan_detector)"

        entry = (
            f'    "{mod}": ToolEntry(\n'
            f'        cmd="{mod.replace("_","-")}", module="{mod}",\n'
            f'        stability="legacy",\n'
            f'        description="{desc}",\n'
            f'        preflight=[PreflightCheck("file", str(TOOLS_DIR / "{mod}.py"))],\n'
            f'    ),\n'
        )
        new_entries.append(entry)

    # Insert before the closing `}` of the registry dict
    insert_marker = "\n}\n"
    if insert_marker not in reg_text:
        insert_marker = "}\n"

    block = "\n    # ── AUTO-REGISTERED by orphan_detector ──────────────────────────────────\n"
    block += "".join(new_entries)
    reg_text = reg_text.replace(insert_marker, block + insert_marker)
    _REGISTRY.write_text(reg_text, encoding="utf-8")

    print(f"\n  ✅ {len(orphans)} módulos registrados como LEGACY")
    print("  💡 Regenera docs: python3 .bago/tools/generate_commands_doc.py")
    return 0


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_list() -> int:
    orphans = find_orphans()
    baseline = load_baseline()
    new_orphans = [o for o in orphans if o not in baseline]
    _print_report(orphans, new_orphans)
    return 0


def cmd_baseline() -> int:
    orphans = find_orphans()
    save_baseline(orphans)
    return 0


def cmd_strict() -> int:
    """Exit 1 if any new orphans found (for pre-push use)."""
    orphans = find_orphans()
    baseline = load_baseline()
    new_orphans = [o for o in orphans if o not in baseline]
    if new_orphans:
        print(f"❌ {len(new_orphans)} nuevos módulos huérfanos detectados:")
        for o in new_orphans:
            print(f"   - {o}")
        print("\n💡 Ejecuta: bago orphans --baseline  (para tolerarlos)")
        print("          bago orphans --fix        (para registrarlos)")
        return 1
    print(f"✅ Sin nuevos huérfanos (baseline: {len(baseline)} conocidos)")
    return 0


# ── main ──────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if "--fix" in args:
        orphans = find_orphans()
        return cmd_fix(orphans)
    if "--baseline" in args:
        return cmd_baseline()
    if "--strict" in args:
        return cmd_strict()
    return cmd_list()


if __name__ == "__main__":
    sys.exit(main())
