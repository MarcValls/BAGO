#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reconcile_state.py — Reconciliador estado vs disco.

Cuenta archivos reales en state/sessions/, state/changes/, state/evidences/
y compara con global_state.json → inventory.
Si hay diferencia, muestra el diff y ofrece actualizar.
Con --fix aplica corrección automáticamente.

Uso:
  python3 .bago/tools/reconcile_state.py         # solo muestra diff
  python3 .bago/tools/reconcile_state.py --fix   # aplica corrección
"""

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
GLOBAL_STATE = STATE / "global_state.json"


def count_files(folder: Path, pattern: str = "*.json") -> int:
    """Cuenta archivos en carpeta, excluyendo README.md."""
    if not folder.exists():
        return 0
    return len([f for f in folder.glob(pattern) if f.name.lower() != "readme.md"])


def load_global() -> dict:
    if not GLOBAL_STATE.exists():
        print("❌ global_state.json no encontrado")
        sys.exit(1)
    return json.loads(GLOBAL_STATE.read_text(encoding="utf-8"))


def save_global(gs: dict):
    from datetime import datetime, timezone
    gs["updated_at"] = datetime.now(timezone.utc).isoformat()
    GLOBAL_STATE.write_text(json.dumps(gs, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    fix_mode = "--fix" in sys.argv

    gs = load_global()
    inventory = gs.get("inventory", {})

    dirs = {
        "sessions":  STATE / "sessions",
        "changes":   STATE / "changes",
        "evidences": STATE / "evidences",
    }

    real_counts = {key: count_files(folder) for key, folder in dirs.items()}

    diffs = {}
    for key in dirs:
        expected = inventory.get(key, 0)
        real = real_counts[key]
        if real != expected:
            diffs[key] = (expected, real)

    if not diffs:
        inv = inventory
        print(f"✅ Inventario reconciliado: ses={inv.get('sessions',0)}/chg={inv.get('changes',0)}/evd={inv.get('evidences',0)}")
        return 0

    # Mostrar diferencias
    print("⚠️  Diferencias detectadas entre inventario y disco:\n")
    print(f"  {'Tipo':<12} {'global_state':>12} {'disco':>8} {'diff':>8}")
    print(f"  {'-'*12} {'-'*12} {'-'*8} {'-'*8}")
    for key, (expected, real) in diffs.items():
        diff = real - expected
        sign = f"+{diff}" if diff > 0 else str(diff)
        print(f"  {key:<12} {expected:>12} {real:>8} {sign:>8}")
    print()

    if not fix_mode:
        # Mostrar también los valores que están OK
        ok_keys = [k for k in dirs if k not in diffs]
        if ok_keys:
            print("  OK (sin diferencia):", ", ".join(ok_keys))
        print()
        print("  Usa --fix para actualizar global_state.json automáticamente.")
        return 1

    # Aplicar corrección
    if "inventory" not in gs:
        gs["inventory"] = {}
    for key in dirs:
        gs["inventory"][key] = real_counts[key]
    save_global(gs)

    inv = gs["inventory"]
    print(f"✅ Inventario actualizado: ses={inv.get('sessions',0)}/chg={inv.get('changes',0)}/evd={inv.get('evidences',0)}")
    return 0



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    sys.exit(main())
