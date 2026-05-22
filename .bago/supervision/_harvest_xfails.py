#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_harvest_xfails.py — Cosecha automática de xfail/xpass del proyecto.

Escanea el suite de tests, detecta ficheros con markers xfail (nuevos,
desaparecidos o que ahora xpasan), y actualiza LEGACY_TEST_MAP.json con
memoria acumulativa de excepciones.

Uso:
    python .bago/supervision/_harvest_xfails.py [--dry-run] [--json]
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT    = Path(__file__).resolve().parent.parent.parent
SUPERVISION  = Path(__file__).resolve().parent
ARTIFACT     = SUPERVISION / "artifacts" / "LEGACY_TEST_MAP.json"
TESTS_DIR    = REPO_ROOT / "tests"


# ── Detección de xfail via AST ─────────────────────────────────────────────────

_SKIP_MARKERS = {"xfail", "skip"}


def _collect_xfail_files(tests_dir: Path) -> dict[str, dict]:
    """Devuelve {filepath: {"marker": "xfail"|"skip", "reason": str}}
    para tests con @pytest.mark.xfail o @pytest.mark.skip (en cualquier scope).
    """
    result: dict[str, dict] = {}
    for py_file in tests_dir.rglob("*.py"):
        rel = py_file.relative_to(REPO_ROOT).as_posix()
        try:
            source = py_file.read_text(encoding="utf-8-sig", errors="replace")
            tree   = ast.parse(source)
        except SyntaxError:
            continue

        found: dict | None = None

        for node in ast.walk(tree):
            if found:
                break
            # Function/class-level decorators
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for decorator in node.decorator_list:
                    hit = _extract_marker_info(decorator, source)
                    if hit is not None:
                        found = hit
                        break
            # pytestmark assignment — anywhere in the tree (module, except, etc.)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "pytestmark":
                        hit = _extract_marker_info(node.value, source)
                        if hit is not None:
                            found = hit
                            break

        if found:
            result[rel] = found
    return result


def _extract_marker_info(node: ast.expr, source: str) -> dict | None:
    """Extrae marker xfail/skip de un nodo AST. Devuelve {"marker": ..., "reason": ...} o None."""
    if isinstance(node, ast.Attribute) and node.attr in _SKIP_MARKERS:
        return {"marker": node.attr, "reason": "no reason"}
    if isinstance(node, ast.Call):
        func = node.func
        marker_name = None
        if isinstance(func, ast.Attribute) and func.attr in _SKIP_MARKERS:
            marker_name = func.attr
        elif isinstance(func, ast.Name) and func.id in _SKIP_MARKERS:
            marker_name = func.id
        if marker_name:
            reason = "no reason"
            for kw in node.keywords:
                if kw.arg == "reason" and isinstance(kw.value, ast.Constant):
                    reason = str(kw.value.value)
                    break
            if not node.keywords and node.args and isinstance(node.args[0], ast.Constant):
                reason = str(node.args[0].value)
            return {"marker": marker_name, "reason": reason}
    if isinstance(node, ast.List):
        for elt in node.elts:
            hit = _extract_marker_info(elt, source)
            if hit is not None:
                return hit
    return None


# ── Detección via pytest --collect-only ───────────────────────────────────────

def _collect_via_pytest() -> set[str]:
    """Corre pytest --collect-only y detecta ficheros que tienen xfail."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q",
             "--no-header", "--tb=no"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(REPO_ROOT), timeout=60,
        )
        # Busca líneas como "<Module test_bago_brutal.py>"
        modules: set[str] = set()
        for line in result.stdout.splitlines():
            m = re.search(r"<Module\s+(tests[\\/].+\.py)>", line)
            if m:
                modules.add(m.group(1).replace("\\", "/"))
        return modules
    except Exception:
        return set()


# ── Actualización del artefacto ───────────────────────────────────────────────

def _load_artifact() -> dict:
    if ARTIFACT.exists():
        try:
            return json.loads(ARTIFACT.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "schema_version": "1.0",
        "description": "Mapa de tests legacy — estado de migración",
        "last_scanned": None,
        "summary": {"total": 0, "done": 0, "xfail": 0, "needs_migration": 0},
        "tests": [],
        "exception_log": [],
    }


def run_harvest(dry_run: bool = False) -> dict:
    """Cosecha xfails/skips y actualiza LEGACY_TEST_MAP.json."""
    now = datetime.now().isoformat()

    # Detectar xfails y skips via AST
    detected = _collect_xfail_files(TESTS_DIR)  # {filepath: {"marker": ..., "reason": ...}}

    data = _load_artifact()
    existing_tests: dict[str, dict] = {t["file"]: t for t in data.get("tests", [])}

    new_entries: list[str]         = []
    disappeared_entries: list[str] = []
    unchanged: list[str]           = []

    # Detectar NUEVOS (no estaban en el mapa)
    for filepath, info in detected.items():
        marker = info["marker"]
        reason = info["reason"]
        if filepath not in existing_tests:
            new_entries.append(filepath)
            existing_tests[filepath] = {
                "file":         filepath,
                "status":       marker,   # "xfail" o "skip"
                "reason":       reason,
                "coverage_by":  None,
                "action":       "needs_review",
                "since_version": "auto",
                "discovered_at": now,
            }
        else:
            # Actualizar marker/reason si cambió
            existing = existing_tests[filepath]
            if existing.get("status") != marker:
                existing["status"]      = marker
                existing["reason"]      = reason
                existing["updated_at"]  = now
            unchanged.append(filepath)

    # Detectar DESAPARECIDOS (estaban en el mapa, ahora no tienen marker)
    for filepath, entry in list(existing_tests.items()):
        if entry.get("status") in {"xfail", "skip"} and filepath not in detected:
            disappeared_entries.append(filepath)
            existing_tests[filepath] = {
                **entry,
                "status":      "migrated",
                "migrated_at": now,
            }

    # Actualizar artefacto
    data["tests"] = list(existing_tests.values())
    data["last_scanned"] = now

    xfail_count    = sum(1 for t in data["tests"] if t.get("status") == "xfail")
    skip_count     = sum(1 for t in data["tests"] if t.get("status") == "skip")
    migrated_count = sum(1 for t in data["tests"] if t.get("status") == "migrated")
    needs_review   = sum(1 for t in data["tests"] if t.get("action") == "needs_review")

    data["summary"] = {
        "total":           len(data["tests"]),
        "xfail":           xfail_count,
        "skip":            skip_count,
        "migrated":        migrated_count,
        "needs_migration": needs_review,
        "done":            migrated_count,
    }
    data["overall"] = "yellow" if needs_review > 0 else "green"

    # Append al log de excepciones (memoria acumulativa)
    log_entry = {
        "timestamp":   now,
        "new_found":   new_entries,
        "disappeared": disappeared_entries,
        "total_xfail": xfail_count,
        "total_skip":  skip_count,
        "status":      "new_found" if new_entries else ("migrated" if disappeared_entries else "stable"),
    }
    data.setdefault("exception_log", []).append(log_entry)
    if len(data["exception_log"]) > 50:
        data["exception_log"] = data["exception_log"][-50:]

    if not dry_run:
        ARTIFACT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "new":         new_entries,
        "disappeared": disappeared_entries,
        "unchanged":   len(unchanged),
        "total_xfail": xfail_count,
        "total_skip":  skip_count,
        "dry_run":     dry_run,
    }


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    as_json = "--json" in sys.argv

    result = run_harvest(dry_run=dry_run)

    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    status = "DRY-RUN " if dry_run else ""
    print(f"🔍 {status}harvest xfail/skip: {result['total_xfail']} xfails + {result['total_skip']} skips activos")
    if result["new"]:
        print(f"  🆕 Nuevos detectados ({len(result['new'])}):")
        for f in result["new"]:
            print(f"     + {f}")
    if result["disappeared"]:
        print(f"  ✅ Migrados/eliminados ({len(result['disappeared'])}):")
        for f in result["disappeared"]:
            print(f"     - {f}")
    if not result["new"] and not result["disappeared"]:
        print(f"  ✔  Sin cambios ({result['unchanged']} ficheros xfail estables)")
    return 1 if result["new"] else 0


if __name__ == "__main__":
    sys.exit(main())
