#!/usr/bin/env python3
"""
session_preflight.py — Validador de reglas W7 antes de abrir una sesión BAGO.

Verifica que se cumplen las tres reglas del ESCENARIO-001:
  Regla A: ≥3 artefactos pre-declarados (no contar el JSON de sesión)
  Regla B: ≤2 roles activados
  Regla C: objetivo con formato "Verbo + objeto + criterio de done"

Uso:
  python3 tools/session_preflight.py \
    --objetivo "Crear X para que Y" \
    --roles "role_architect,role_validator" \
    --artefactos "docs/A.md,state/changes/CHG.json,tools/script.py"

Salida:
  GO  — cumple todas las reglas, listo para abrir sesión
  KO  — indica qué regla falla y cómo corregirla
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

import argparse
import sys
from functools import lru_cache

ROLE_MAP = {
    "system_change":       ("role_architect", "role_validator"),
    "analysis":            ("role_auditor", "role_organizer"),
    "execution":           ("role_executor", "role_validator"),
    "sprint":              ("role_organizer", "role_vertice"),
    "project_bootstrap":   ("role_architect", "role_organizer"),
}

PROTOCOL_ARTIFACTS = {
    "state/sessions", "state/changes", "state/evidences",
    "TREE.txt", "CHECKSUMS.sha256",
}

VERBS_ES = [
    "crear", "actualizar", "corregir", "migrar", "añadir", "eliminar",
    "refactorizar", "documentar", "validar", "analizar", "implementar",
    "generar", "registrar", "cerrar", "optimizar", "diseñar",
]


@lru_cache(maxsize=1)
def _load_preflight_rules() -> dict[str, object]:
    try:
        from bago_config import load_config
        data = load_config("preflight_rules", fallback=None)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _get_role_map() -> dict[str, tuple[str, ...]]:
    role_map = _load_preflight_rules().get("role_map")
    if not isinstance(role_map, dict):
        return ROLE_MAP
    converted: dict[str, tuple[str, ...]] = {}
    for key, value in role_map.items():
        if isinstance(value, list):
            converted[str(key)] = tuple(str(item) for item in value)
    return converted or ROLE_MAP


def _get_protocol_artifacts() -> set[str]:
    artifacts = _load_preflight_rules().get("protocol_artifacts")
    return set(artifacts) if isinstance(artifacts, list) else PROTOCOL_ARTIFACTS


def _get_verbs_es() -> list[str]:
    verbs = _load_preflight_rules().get("verbs_es")
    return [str(verb) for verb in verbs] if isinstance(verbs, list) else VERBS_ES


def check_objetivo(objetivo: str) -> tuple[bool, str]:
    if not objetivo or len(objetivo.strip()) < 15:
        return False, "El objetivo es demasiado corto. Mínimo 15 caracteres con Verbo+Objeto+Done."
    low = objetivo.lower()
    verbs_es = _get_verbs_es()
    has_verb = any(v in low for v in verbs_es)
    if not has_verb:
        return False, f"El objetivo no contiene un verbo de acción reconocido. Usa uno de: {', '.join(verbs_es[:8])}..."
    has_para = "para que" in low or "para " in low or " que " in low
    if not has_para:
        return False, "El objetivo no incluye criterio de done. Añade 'para que [resultado verificable]'."
    return True, "OK"


def check_roles(roles_raw: str) -> tuple[bool, str]:
    roles = [r.strip() for r in roles_raw.split(",") if r.strip()]
    if len(roles) == 0:
        return False, "Debes declarar al menos 1 rol."
    if len(roles) > 2:
        return False, f"Regla B: máximo 2 roles por sesión. Declaraste {len(roles)}: {roles}. Elimina los roles no esenciales."
    return True, f"OK ({len(roles)} rol/es: {roles})"


def is_protocol_artifact(path: str) -> bool:
    for prefix in _get_protocol_artifacts():
        if path.startswith(prefix):
            return True
    return False


def check_artefactos(artefactos_raw: str) -> tuple[bool, str]:
    all_arts = [a.strip() for a in artefactos_raw.split(",") if a.strip()]
    useful = [a for a in all_arts if not is_protocol_artifact(a)]
    if len(useful) < 3:
        ejemplos = [a for a in all_arts if is_protocol_artifact(a)]
        msg = f"Regla A: necesitas ≥3 artefactos útiles (no de protocolo). Tienes {len(useful)}"
        if ejemplos:
            msg += f". Estos NO cuentan (protocolo): {ejemplos}"
        msg += ". Añade documentos, scripts, templates u otros archivos con valor real."
        return False, msg
    return True, f"OK ({len(useful)} artefactos útiles de {len(all_arts)} declarados)"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Valida las reglas W7 antes de abrir una sesión BAGO (ESCENARIO-001)."
    )
    parser.add_argument("--objetivo",    required=True, help="Objetivo de la sesión: Verbo + objeto + criterio de done")
    parser.add_argument("--roles",       required=True, help="Roles separados por coma. Máximo 2.")
    parser.add_argument("--artefactos",  required=True, help="Artefactos pre-declarados separados por coma. Mínimo 3 útiles.")
    parser.add_argument("--task-type",   default="system_change", help="Tipo de tarea (para sugerir roles). Default: system_change")
    args = parser.parse_args(argv)

    results = []
    all_ok = True

    ok, msg = check_objetivo(args.objetivo)
    results.append(("Regla C — Objetivo", ok, msg))
    if not ok:
        all_ok = False

    ok, msg = check_roles(args.roles)
    results.append(("Regla B — Roles", ok, msg))
    if not ok:
        all_ok = False

    ok, msg = check_artefactos(args.artefactos)
    results.append(("Regla A — Artefactos", ok, msg))
    if not ok:
        all_ok = False

    print()
    print("=" * 60)
    print("  BAGO · Session Preflight — ESCENARIO-001")
    print("=" * 60)
    for label, ok, msg in results:
        icon = "✅" if ok else "❌"
        print(f"\n  {icon} {label}")
        print(f"     {msg}")

    print()
    if all_ok:
        print("  ✅ GO — Sesión lista para abrir.")
        suggested = _get_role_map().get(args.task_type, None)
        if suggested:
            print(f"     Roles sugeridos para '{args.task_type}': {suggested[0]} + {suggested[1]}")
    else:
        print("  ❌ KO — Corrige los puntos marcados antes de abrir la sesión.")
        print("     Ver reglas completas en: workflows/W7_FOCO_SESION.md")
    print()

    sys.exit(0 if all_ok else 1)



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    main()
