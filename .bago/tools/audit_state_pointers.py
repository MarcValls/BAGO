#!/usr/bin/env python3
"""audit_state_pointers.py — Detecta bugs de punteros huérfanos en global_state.json.

Patrón de bug: un campo en global_state apunta a un ID cuyo archivo
referenciado no existe, o cuyos campos derivados no coinciden con él.

Ejecutar: python3 audit_state_pointers.py
Flags:    --fix-report   → muestra cómo arreglar cada fallo
          --test         → comprueba imports y sale
"""

import sys
import json
import argparse
from pathlib import Path

if "--test" in sys.argv:
    print("audit_state_pointers --test: PASS (imports OK)")
    sys.exit(0)

ROOT   = Path(__file__).resolve().parents[2]
STATE  = ROOT / ".bago" / "state"
GS     = STATE / "global_state.json"

# ── Definición del contrato de punteros ───────────────────────────────────────
# Cada entrada: (campo_puntero, directorio, campos_derivados)
# campos_derivados: [(campo_en_gs, campo_en_archivo_referenciado)]
POINTER_CONTRACT = [
    (
        "last_completed_session_id",
        STATE / "sessions",
        [
            ("last_completed_task_type",  "task_type"),
            ("last_completed_workflow",   "selected_workflow"),
            ("last_completed_roles",      "roles_activated"),
        ],
    ),
    (
        "active_session_id",
        STATE / "sessions",
        [
            ("active_task_type",  "task_type"),
            ("active_roles",      "roles_activated"),
        ],
    ),
    ("last_completed_change_id",   STATE / "changes",   []),
    ("last_completed_evidence_id", STATE / "evidences", []),
]

# ── Propietarios legítimos de cada campo ──────────────────────────────────────
FIELD_OWNERS = {
    "last_completed_session_id":  "cosecha.py",
    "last_completed_task_type":   "cosecha.py",
    "last_completed_workflow":    "cosecha.py",
    "last_completed_roles":       "cosecha.py",
    "last_completed_change_id":   "cosecha.py",
    "last_completed_evidence_id": "cosecha.py",
    "active_session_id":          "workflow_selector.py / session tools",
    "active_task_type":           "workflow_selector.py / session tools",
    "active_roles":               "workflow_selector.py / session tools",
    "active_workflows":           "workflow_selector.py / session tools",
}


def _load_gs() -> dict:
    return json.loads(GS.read_text(encoding="utf-8"))


def audit() -> list[dict]:
    """Devuelve lista de hallazgos: {field, type, detail, owner, fix}."""
    findings = []
    gs = _load_gs()

    for ptr_field, directory, derived in POINTER_CONTRACT:
        ptr_value = gs.get(ptr_field)
        if not ptr_value:
            continue  # campo vacío/null — OK

        ref_file = directory / f"{ptr_value}.json"
        if not ref_file.exists():
            findings.append({
                "field": ptr_field,
                "value": ptr_value,
                "type": "ORPHAN_POINTER",
                "detail": f"Apunta a {ref_file.relative_to(ROOT)} que no existe",
                "owner": FIELD_OWNERS.get(ptr_field, "desconocido"),
                "fix": f"Ejecutar `bago cosecha` para regenerar, o limpiar el campo con null",
            })
            continue  # no podemos verificar derivados si el archivo no existe

        ref_data = json.loads(ref_file.read_text(encoding="utf-8"))
        for gs_field, ref_key in derived:
            gs_val  = gs.get(gs_field)
            ref_val = ref_data.get(ref_key)
            if gs_val != ref_val:
                findings.append({
                    "field": gs_field,
                    "value": gs_val,
                    "type": "DERIVED_MISMATCH",
                    "detail": (
                        f"global_state.{gs_field}={gs_val!r} "
                        f"≠ {ref_file.name}:{ref_key}={ref_val!r}"
                    ),
                    "owner": FIELD_OWNERS.get(gs_field, "desconocido"),
                    "fix": f"Solo `{FIELD_OWNERS.get(gs_field, 'cosecha.py')}` debe escribir este campo",
                })

    return findings


def main():
    p = argparse.ArgumentParser(description="Audita punteros huérfanos en global_state.json")
    p.add_argument("--fix-report", action="store_true", help="Muestra instrucciones de reparación")
    args = p.parse_args()

    findings = audit()

    if not findings:
        print("✅  audit_state_pointers: CLEAN — ningún puntero huérfano ni derivado inconsistente")
        sys.exit(0)

    print(f"⚠️  audit_state_pointers: {len(findings)} hallazgo(s)\n")
    for f in findings:
        icon = "🔴" if f["type"] == "ORPHAN_POINTER" else "🟡"
        print(f"  {icon} [{f['type']}] {f['field']}")
        print(f"       Valor  : {f['value']!r}")
        print(f"       Detalle: {f['detail']}")
        print(f"       Dueño  : {f['owner']}")
        if args.fix_report:
            print(f"       Fix    : {f['fix']}")
        print()

    print("──────────────────────────────────────────────────")
    print("Regla: los campos last_completed_* y active_* SOLO")
    print("deben ser escritos por sus herramientas propietarias.")
    print("Nunca editar global_state.json manualmente para ellos.")
    sys.exit(1)


if __name__ == "__main__":
    main()
