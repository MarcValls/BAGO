#!/usr/bin/env python3
"""
bago_learning_audit.py

Audita la trazabilidad de aprendizaje por proyecto en BAGO.

Uso:
  python3 .bago/tools/bago_learning_audit.py
  python3 .bago/tools/bago_learning_audit.py --json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"


@dataclass
class AuditResult:
    ideas_total: int
    ideas_with_project: int
    ideas_without_project: int
    ideas_unknown_project: int
    projects_distribution: dict[str, int]
    sessions_total: int | None
    sessions_with_project_field: bool
    global_last_promoted_project: str | None
    knowledge_files_total: int
    knowledge_files_with_scope: int
    recent_projects_count: int
    warnings: list[str]


def _safe_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _db_connect_ro(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def _audit_db(db_path: Path) -> tuple[dict[str, Any], list[str]]:
    info: dict[str, Any] = {
        "ideas_total": 0,
        "ideas_with_project": 0,
        "ideas_without_project": 0,
        "ideas_unknown_project": 0,
        "projects_distribution": {},
        "sessions_total": None,
        "sessions_with_project_field": False,
    }
    warnings: list[str] = []

    if not db_path.exists():
        warnings.append("No existe .bago/state/bago.db")
        return info, warnings

    conn = _db_connect_ro(db_path)
    cur = conn.cursor()
    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}

        if "ideas" not in tables:
            warnings.append("La tabla ideas no existe en bago.db")
            return info, warnings

        cur.execute("PRAGMA table_info('ideas')")
        idea_cols = [r[1].lower() for r in cur.fetchall()]
        has_project_col = "project" in idea_cols

        cur.execute("SELECT COUNT(*) FROM ideas")
        info["ideas_total"] = int(cur.fetchone()[0])

        if has_project_col:
            cur.execute("SELECT COUNT(*) FROM ideas WHERE project IS NOT NULL AND TRIM(project) <> ''")
            info["ideas_with_project"] = int(cur.fetchone()[0])

            cur.execute("SELECT COUNT(*) FROM ideas WHERE project IS NULL OR TRIM(project) = ''")
            info["ideas_without_project"] = int(cur.fetchone()[0])

            cur.execute(
                "SELECT COUNT(*) FROM ideas WHERE lower(TRIM(project)) IN ('unknown','desconocido','n/a','none')"
            )
            info["ideas_unknown_project"] = int(cur.fetchone()[0])

            cur.execute(
                "SELECT project, COUNT(*) c FROM ideas GROUP BY project ORDER BY c DESC"
            )
            info["projects_distribution"] = {
                (r[0] if r[0] is not None else "<null>"): int(r[1]) for r in cur.fetchall()
            }
        else:
            warnings.append("La tabla ideas no tiene columna project")

        if "sessions" in tables:
            cur.execute("PRAGMA table_info('sessions')")
            sess_cols = [r[1].lower() for r in cur.fetchall()]
            info["sessions_with_project_field"] = any(
                c in sess_cols for c in ("project", "project_id", "project_name", "source_project")
            )
            cur.execute("SELECT COUNT(*) FROM sessions")
            info["sessions_total"] = int(cur.fetchone()[0])
            if not info["sessions_with_project_field"]:
                warnings.append(
                    "sessions no tiene campo de proyecto (project/project_id/project_name/source_project)"
                )
    finally:
        conn.close()

    return info, warnings


def run_audit(state_dir: Path) -> AuditResult:
    warnings: list[str] = []

    db_info, db_warnings = _audit_db(state_dir / "bago.db")
    warnings.extend(db_warnings)

    global_state = _safe_json(state_dir / "global_state.json", {})
    knowledge_index = _safe_json(state_dir / "knowledge_index.json", {})
    recent_projects = _safe_json(state_dir / "recent_projects.json", {"projects": []})

    global_last_promoted_project = (
        global_state.get("knowledge_index", {}).get("last_promoted_project")
    )
    if global_last_promoted_project in (None, "", "unknown"):
        warnings.append("global_state.knowledge_index.last_promoted_project no esta bien trazado")

    files = knowledge_index.get("knowledge_base", {}).get("files", {})
    knowledge_files_total = len(files)
    knowledge_files_with_scope = 0
    for meta in files.values():
        if isinstance(meta, dict) and any(k in meta for k in ("scope", "project", "source_project")):
            knowledge_files_with_scope += 1

    if knowledge_files_total > 0 and knowledge_files_with_scope == 0:
        warnings.append("knowledge_index no guarda scope/project por archivo")

    projects_list = recent_projects.get("projects", [])
    recent_projects_count = len(projects_list) if isinstance(projects_list, list) else 0
    if recent_projects_count == 0:
        warnings.append("No hay proyectos recientes registrados")

    return AuditResult(
        ideas_total=db_info["ideas_total"],
        ideas_with_project=db_info["ideas_with_project"],
        ideas_without_project=db_info["ideas_without_project"],
        ideas_unknown_project=db_info["ideas_unknown_project"],
        projects_distribution=db_info["projects_distribution"],
        sessions_total=db_info["sessions_total"],
        sessions_with_project_field=db_info["sessions_with_project_field"],
        global_last_promoted_project=global_last_promoted_project,
        knowledge_files_total=knowledge_files_total,
        knowledge_files_with_scope=knowledge_files_with_scope,
        recent_projects_count=recent_projects_count,
        warnings=warnings,
    )


def _print_human(result: AuditResult) -> None:
    print("BAGO Learning Audit")
    print("=" * 60)
    print(f"Ideas totales: {result.ideas_total}")
    print(f"Ideas con proyecto: {result.ideas_with_project}")
    print(f"Ideas sin proyecto: {result.ideas_without_project}")
    print(f"Ideas proyecto unknown: {result.ideas_unknown_project}")
    print(f"Sessions total: {result.sessions_total}")
    print(f"Sessions con campo proyecto: {result.sessions_with_project_field}")
    print(f"Knowledge files totales: {result.knowledge_files_total}")
    print(f"Knowledge files con scope/project: {result.knowledge_files_with_scope}")
    print(f"Recent projects: {result.recent_projects_count}")
    print(f"Last promoted project: {result.global_last_promoted_project}")
    print("\nDistribucion por proyecto (ideas):")
    if result.projects_distribution:
        for project, count in result.projects_distribution.items():
            print(f"  - {project}: {count}")
    else:
        print("  - Sin datos")

    if result.warnings:
        print("\nWarnings:")
        for w in result.warnings:
            print(f"  - {w}")
    else:
        print("\nSin warnings de trazabilidad.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita trazabilidad de aprendizaje por proyecto en BAGO")
    parser.add_argument("--json", action="store_true", help="Salida en JSON")
    parser.add_argument("--state-dir", default=str(STATE), help="Directorio de estado (default: .bago/state)")
    args = parser.parse_args()

    result = run_audit(Path(args.state_dir))
    if args.json:
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    else:
        _print_human(result)
    return 0




def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())
    raise SystemExit(main())