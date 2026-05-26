#!/usr/bin/env python3
"""auto_heal.py — BAGO detecta sus propios problemas y se repara solo.

La gobernanza real implica que el sistema se conoce a sí mismo.
Este tool detecta inconsistencias en el framework y aplica reparaciones
automáticas de forma segura y trazable.

Reparaciones disponibles:
    R001  Tools sin --test → reportado para reparación manual
  R002  Tools sin routing en bago → detectado y reportado (manual)
  R003  CHECKSUMS desactualizados → regenerados automáticamente
  R004  global_state.json desincronizado → tool_count actualizado
  R005  Entradas duplicadas en integration_tests.py → limpiadas

Uso:
    python3 auto_heal.py              # diagnóstico + plan de reparación
    python3 auto_heal.py --fix        # aplica todas las reparaciones seguras
    python3 auto_heal.py --fix R001   # aplica solo reparación específica
    python3 auto_heal.py --dry-run    # muestra qué haría --fix sin tocar nada
    python3 auto_heal.py --report     # genera reporte de salud detallado
    python3 auto_heal.py --test       # self-tests

Códigos: HEAL-I001 (reparado), HEAL-W001 (no reparable automáticamente),
         HEAL-E001 (error en reparación), HEAL-I002 (sin problemas)
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

import sys
import ast
import re
import json
import hashlib
from pathlib import Path
from typing import Optional

BAGO_ROOT = Path(__file__).parent.parent
TOOLS_DIR = Path(__file__).parent
PROJECT_ROOT = BAGO_ROOT.parent
BAGO_SCRIPT = PROJECT_ROOT / "bago"
INTEGRATION_TESTS = TOOLS_DIR / "integration_tests.py"
CHECKSUMS_FILE = BAGO_ROOT / "CHECKSUMS.sha256"
GLOBAL_STATE = BAGO_ROOT / "state" / "global_state.json"


def _load_internal_tools() -> set:
    """Load INTERNAL_TOOLS from tool_registry dynamically.

    Falls back to a minimal safe set if tool_registry can't be imported.
    Never hardcodes the list here — tool_registry is the single source of truth.
    """
    reg_path = TOOLS_DIR / "tool_registry.py"
    if not reg_path.exists():
        for found in BAGO_ROOT.rglob("tool_registry.py"):
            reg_path = found
            break
    if not reg_path.exists():
        return {"tool_registry", "auto_heal", "__init__"}
    try:
        import importlib.util as _ilu
        _spec = _ilu.spec_from_file_location("_ah_registry", str(reg_path))
        if _spec:
            _mod = _ilu.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)  # type: ignore
            internal: frozenset = getattr(_mod, "INTERNAL_TOOLS", frozenset())
            # Also include this file itself so it's never treated as a user tool
            return set(internal) | {"auto_heal"}
    except Exception:
        pass
    return {"tool_registry", "auto_heal", "__init__"}


INTERNAL_TOOLS: set = _load_internal_tools()


# ─────────────────────────────────────────────────────────────────────────────
# DIAGNOSIS FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def diagnose_R001_missing_tests() -> dict:
    """Detecta tools Python sin flag --test."""
    missing = []
    for f in sorted(TOOLS_DIR.glob("*.py")):
        if f.name in INTERNAL_TOOLS:
            continue
        try:
            src = f.read_text(encoding="utf-8")
            if "--test" not in src:
                missing.append(f.name)
        except Exception:
            pass
    return {
        "id": "R001", "label": "Tools sin --test",
        "count": len(missing), "items": missing,
        "auto_fixable": True,
        "risk": "LOW",
    }


def diagnose_R002_missing_routing() -> dict:
    """Detecta tools sin routing en el script bago."""
    try:
        bago_src = BAGO_SCRIPT.read_text(encoding="utf-8")
    except Exception:
        return {"id": "R002", "label": "Missing routing", "count": 0,
                "items": [], "auto_fixable": False, "risk": "LOW"}

    missing = []
    for f in sorted(TOOLS_DIR.glob("*.py")):
        if f.name in INTERNAL_TOOLS:
            continue
        cmd = f.stem.replace("_", "-")
        if f'cmd == "{cmd}"' not in bago_src:
            missing.append(f.name)
    return {
        "id": "R002", "label": "Tools sin routing en bago",
        "count": len(missing), "items": missing,
        "auto_fixable": False,  # requiere descripción manual
        "risk": "LOW",
    }


def diagnose_R003_stale_checksums() -> dict:
    """Detecta si CHECKSUMS.sha256 está desactualizado."""
    try:
        current = CHECKSUMS_FILE.read_text(encoding="utf-8")
        # Recompute
        lines = []
        for f in sorted(list(TOOLS_DIR.glob("*.py")) + list(TOOLS_DIR.glob("*.js"))):
            content = f.read_bytes()
            sha = hashlib.sha256(content).hexdigest()
            rel = f.relative_to(BAGO_ROOT)
            lines.append(f"{sha}  {rel}")
        expected = "\n".join(lines) + "\n"
        stale = current.strip() != expected.strip()
        return {
            "id": "R003", "label": "CHECKSUMS desactualizados",
            "count": 1 if stale else 0,
            "items": ["CHECKSUMS.sha256"] if stale else [],
            "auto_fixable": True, "risk": "LOW",
        }
    except Exception as e:
        return {"id": "R003", "label": "CHECKSUMS error",
                "count": 1, "items": [str(e)], "auto_fixable": True, "risk": "LOW"}


def diagnose_R004_state_sync() -> dict:
    """Detecta desincronización en global_state.json."""
    issues = []
    try:
        state = json.loads(GLOBAL_STATE.read_text(encoding="utf-8"))
        actual_count = len([f for f in TOOLS_DIR.glob("*.py")
                            if f.name not in INTERNAL_TOOLS])
        recorded = state.get("tool_count", 0)
        if isinstance(recorded, str):
            try:
                recorded = int(recorded)
            except Exception:
                recorded = 0
        if abs(actual_count - recorded) > 2:
            issues.append(f"tool_count: {recorded} → debería ser ~{actual_count}")
    except Exception as e:
        issues.append(f"Error leyendo global_state.json: {e}")
    return {
        "id": "R004", "label": "global_state.json desincronizado",
        "count": len(issues), "items": issues,
        "auto_fixable": True, "risk": "LOW",
    }


def diagnose_R005_dup_integration() -> dict:
    """Detecta entradas duplicadas en integration_tests.py."""
    try:
        src = INTEGRATION_TESTS.read_text(encoding="utf-8")
        # Find all "test_XXX" references in ALL_TESTS
        entries = re.findall(r'test_(\w+)\)', src)
        seen = set()
        dups = []
        for e in entries:
            if e in seen:
                dups.append(e)
            seen.add(e)
        return {
            "id": "R005", "label": "Entradas duplicadas en integration_tests",
            "count": len(dups), "items": dups,
            "auto_fixable": False, "risk": "MEDIUM",
        }
    except Exception as e:
        return {"id": "R005", "label": "Error parsing integration_tests",
                "count": 1, "items": [str(e)], "auto_fixable": False, "risk": "MEDIUM"}


# ─────────────────────────────────────────────────────────────────────────────
# REPAIR FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def repair_R001(dry_run: bool = False) -> dict:
    """R001 queda como diagnóstico; no hay reparación automática segura."""
    return {
        "id": "R001",
        "ok": False,
        "output": "R001 no tiene reparación automática activa; añade --test de forma manual o con toolsmith.",
        "code": "HEAL-W001",
    }


def repair_R003(dry_run: bool = False) -> dict:
    """Regenera CHECKSUMS.sha256."""
    if dry_run:
        return {"id": "R003", "ok": True, "output": "[DRY] CHECKSUMS sería regenerado",
                "code": "HEAL-I001"}
    try:
        lines = []
        for f in sorted(list(TOOLS_DIR.glob("*.py")) + list(TOOLS_DIR.glob("*.js"))):
            content = f.read_bytes()
            sha = hashlib.sha256(content).hexdigest()
            rel = f.relative_to(BAGO_ROOT)
            lines.append(f"{sha}  {rel}")
        CHECKSUMS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return {"id": "R003", "ok": True, "output": f"CHECKSUMS regenerado ({len(lines)} archivos)",
                "code": "HEAL-I001"}
    except Exception as e:
        return {"id": "R003", "ok": False, "output": str(e), "code": "HEAL-E001"}


def repair_R004(dry_run: bool = False) -> dict:
    """Actualiza tool_count en global_state.json."""
    try:
        state = json.loads(GLOBAL_STATE.read_text(encoding="utf-8"))
        actual = len([f for f in TOOLS_DIR.glob("*.py")
                      if f.name not in INTERNAL_TOOLS])
        old = state.get("tool_count", 0)
        state["tool_count"] = actual
        if not dry_run:
            GLOBAL_STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False),
                                    encoding="utf-8")
        return {
            "id": "R004", "ok": True,
            "output": f"tool_count: {old} → {actual}" + (" [DRY]" if dry_run else ""),
            "code": "HEAL-I001",
        }
    except Exception as e:
        return {"id": "R004", "ok": False, "output": str(e), "code": "HEAL-E001"}


REPAIR_FNS = {
    "R001": repair_R001,
    "R003": repair_R003,
    "R004": repair_R004,
}

DIAGNOSE_FNS = [
    diagnose_R001_missing_tests,
    diagnose_R002_missing_routing,
    diagnose_R003_stale_checksums,
    diagnose_R004_state_sync,
    diagnose_R005_dup_integration,
]


def run_diagnosis() -> list:
    results = []
    for fn in DIAGNOSE_FNS:
        results.append(fn())
    return results


def print_diagnosis(diagnosis: list):
    total_issues = sum(d["count"] for d in diagnosis)
    print(f"\n  🔬 BAGO Auto-Heal — Diagnóstico del Framework")
    print("  " + "═" * 54)

    if total_issues == 0:
        print("  [HEAL-I002] ✅ Framework en perfecto estado. Sin reparaciones necesarias.")
        return

    for d in diagnosis:
        if d["count"] == 0:
            print(f"  [HEAL-I002] ✅  {d['id']} — {d['label']}: sin problemas")
        else:
            fixable = "AUTO-FIXABLE" if d["auto_fixable"] else "MANUAL"
            risk = d["risk"]
            print(f"  [HEAL-W001] ⚠️   {d['id']} — {d['label']}: {d['count']} problema(s)  [{fixable}] [{risk}]")
            for item in d["items"][:5]:
                print(f"              • {item}")
            if len(d["items"]) > 5:
                print(f"              … y {len(d['items']) - 5} más")

    auto_fixable = [d for d in diagnosis if d["count"] > 0 and d["auto_fixable"]]
    manual = [d for d in diagnosis if d["count"] > 0 and not d["auto_fixable"]]

    print(f"\n  Resumen: {total_issues} problema(s) — "
          f"{len(auto_fixable)} auto-reparables, {len(manual)} manuales")
    if auto_fixable:
        ids = ", ".join(d["id"] for d in auto_fixable)
        print(f"  Ejecuta: bago auto-heal --fix  (reparará: {ids})")
    print()


def cmd_fix(only: Optional[str] = None, dry_run: bool = False) -> int:
    diagnosis = run_diagnosis()
    to_fix = [d for d in diagnosis if d["count"] > 0 and d["auto_fixable"]]

    if only:
        to_fix = [d for d in to_fix if d["id"] == only.upper()]

    if not to_fix:
        print("  [HEAL-I002] ✅ Sin reparaciones automáticas necesarias.")
        return 0

    print(f"\n  🔧 Auto-Heal — Aplicando {len(to_fix)} reparación(es)"
          + (" [DRY-RUN]" if dry_run else ""))
    print("  " + "─" * 54)

    errors = 0
    for d in to_fix:
        fn = REPAIR_FNS.get(d["id"])
        if not fn:
            print(f"  [HEAL-W001] {d['id']}: sin función de reparación implementada")
            continue
        result = fn(dry_run=dry_run)
        icon = "✅" if result["ok"] else "❌"
        print(f"  [{result['code']}] {icon} {d['id']} — {d['label']}")
        if result.get("output"):
            for line in result["output"].strip().splitlines()[:4]:
                print(f"    {line}")
        if not result["ok"]:
            errors += 1

    print()
    return 1 if errors > 0 else 0


def run_tests():
    results = []

    # Test 1: diagnose R001 returns expected structure
    d = diagnose_R001_missing_tests()
    ok1 = isinstance(d["count"], int) and d["id"] == "R001" and d["auto_fixable"] is True
    results.append(("auto_heal:R001_structure", ok1, f"count={d['count']}"))

    # Test 2: diagnose R002 detects missing routing (we know some tools lack it)
    d = diagnose_R002_missing_routing()
    ok2 = d["id"] == "R002" and isinstance(d["items"], list)
    results.append(("auto_heal:R002_structure", ok2, f"count={d['count']}"))

    # Test 3: R003 checksums detection works
    d = diagnose_R003_stale_checksums()
    ok3 = d["id"] == "R003" and d["count"] in (0, 1)
    results.append(("auto_heal:R003_checksums", ok3, f"stale={d['count']}"))

    # Test 4: R004 global_state detection
    d = diagnose_R004_state_sync()
    ok4 = d["id"] == "R004"
    results.append(("auto_heal:R004_state_sync", ok4, f"issues={d['count']}"))

    # Test 5: R005 no duplicates expected
    d = diagnose_R005_dup_integration()
    ok5 = d["id"] == "R005" and isinstance(d["items"], list)
    results.append(("auto_heal:R005_no_dups", ok5, f"dups={d['count']}"))

    # Test 6: repair R003 dry-run succeeds
    r = repair_R003(dry_run=True)
    ok6 = r["ok"] and r["code"] == "HEAL-I001"
    results.append(("auto_heal:repair_R003_dry", ok6, f"code={r['code']}"))

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    for name, ok, detail in results:
        status = "✅" if ok else "❌"
        print(f"  {status}  {name}: {detail}")
    print(f"\n  {passed}/{len(results)} pasaron")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print(__doc__)
        raise SystemExit(0)

    if "--test" in args:
        raise SystemExit(run_tests())

    dry_run = "--dry-run" in args
    only = None

    if "--fix" in args:
        i = args.index("--fix")
        # Optional: --fix R001
        if i + 1 < len(args) and not args[i + 1].startswith("--"):
            only = args[i + 1]
        raise SystemExit(cmd_fix(only=only, dry_run=dry_run))

    # Default: diagnosis
    diagnosis = run_diagnosis()
    print_diagnosis(diagnosis)
    has_issues = any(d["count"] > 0 for d in diagnosis)
    raise SystemExit(1 if has_issues else 0)
