#!/usr/bin/env python3
"""scope_detector.py — Detecta el ámbito (scope) de un script BAGO.

Analiza un archivo Python y determina si opera sobre:
  - el framework BAGO en sí mismo (framework)
  - el proyecto activo del usuario (project)
  - ambos (both)

La clasificación scope es la base para el modelo PADRE/SIEMBRA:
  scope=framework → herramienta que queda en el framework padre
  scope=project   → herramienta que puede ir al seed del proyecto
  scope=both      → herramienta compartida (va en ambos o solo en padre)

Uso:
  python3 scope_detector.py <script.py>
  python3 scope_detector.py --all          # escanea todo tools/
  python3 scope_detector.py --test
"""
import sys
from pathlib import Path

# ── Patrones que indican operación sobre el FRAMEWORK ─────────────────────────
_FW_PATTERNS = [
    ".bago/",
    "BAGO_ROOT",
    "TOOLS_DIR",
    "bago.db",
    "global_state",
    "global_state.json",
    "pack.json",
    "CHECKSUMS",
    "TREE.txt",
    "guardian_runs",
    "tool_registry",
    "validate_pack",
    "health_score",
    "audit_v2",
    "INTERNAL_TOOLS",
    "session_closes",
    "bago_banner",
]

# ── Patrones que indican operación sobre el PROYECTO ──────────────────────────
_PROJ_PATTERNS = [
    "os.getcwd()",
    "Path.cwd()",
    ".cwd()",
    "cwd =",
    "cwd=",
    "project_dir",
    "repo_root",
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "src/",
    "tests/",
    "setup.py",
    "Makefile",
    "git diff",
    "git log",
    "subprocess.*git",
]


def detect_scope(script_path: Path) -> str:
    """Returns 'framework', 'project', or 'both'.

    Heuristic: counts pattern hits in the source text.
    """
    try:
        source = script_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return "both"

    fw_hits = sum(1 for p in _FW_PATTERNS if p in source)
    proj_hits = sum(1 for p in _PROJ_PATTERNS if p in source)

    if fw_hits > 0 and proj_hits > 0:
        return "both"
    if fw_hits > 0:
        return "framework"
    if proj_hits > 0:
        return "project"
    return "both"  # sin señales claras → ambos


def detect_scope_detail(script_path: Path) -> dict:
    """Returns detailed breakdown for inspection."""
    try:
        source = script_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {"scope": "both", "fw_hits": [], "proj_hits": [], "error": "unreadable"}

    fw_hits   = [p for p in _FW_PATTERNS   if p in source]
    proj_hits = [p for p in _PROJ_PATTERNS if p in source]

    if fw_hits and proj_hits:
        scope = "both"
    elif fw_hits:
        scope = "framework"
    elif proj_hits:
        scope = "project"
    else:
        scope = "both"

    return {"scope": scope, "fw_hits": fw_hits, "proj_hits": proj_hits}


def _badge(scope: str) -> str:
    return {"framework": "🔵", "project": "🟢", "both": "⚪"}.get(scope, "⚪")


def _scan_all() -> None:
    tools_dir = Path(__file__).parent
    scripts = sorted(tools_dir.glob("*.py"))
    print(f"\n  {'SCRIPT':<40} {'SCOPE':<12} SEÑALES")
    print("  " + "─" * 72)
    counts = {"framework": 0, "project": 0, "both": 0}
    for s in scripts:
        detail = detect_scope_detail(s)
        scope = detail["scope"]
        counts[scope] += 1
        fw  = len(detail["fw_hits"])
        pr  = len(detail["proj_hits"])
        badge = _badge(scope)
        print(f"  {s.name:<40} {badge} {scope:<10}  fw={fw} proj={pr}")
    print(f"\n  framework={counts['framework']}  project={counts['project']}  both={counts['both']}")
    print()


def _self_test() -> None:
    from io import StringIO
    # Simula scripts con contenido conocido
    class _FakeFile:
        def __init__(self, content):
            self._c = content
        def read_text(self, **_):
            return self._c
        @property
        def name(self):
            return "test"

    import unittest.mock as mock

    tests = [
        ("fw only",   "import BAGO_ROOT\nbago.db path",        "framework"),
        ("proj only",  "cwd = os.getcwd()\ngit diff HEAD",     "project"),
        ("both",      "BAGO_ROOT\nos.getcwd()",                 "both"),
        ("empty",     "print('hello')",                         "both"),
    ]
    passed = 0
    for name, content, expected in tests:
        with mock.patch("pathlib.Path.read_text", return_value=content):
            result = detect_scope(Path("fake.py"))
        ok = result == expected
        print(f"  {'✅' if ok else '❌'} {name}: expected={expected} got={result}")
        if ok:
            passed += 1
    print(f"\n  {passed}/{len(tests)} tests pasaron")
    sys.exit(0 if passed == len(tests) else 1)


def main() -> None:
    args = sys.argv[1:]
    if "--test" in args:
        _self_test()
        return
    if "--all" in args:
        _scan_all()
        return
    if not args or args[0].startswith("-"):
        print(__doc__)
        return
    for path_str in args:
        p = Path(path_str)
        if not p.exists():
            print(f"❌ No encontrado: {p}")
            continue
        detail = detect_scope_detail(p)
        scope = detail["scope"]
        badge = _badge(scope)
        print(f"\n  {badge} {p.name}  →  scope={scope}")
        if detail["fw_hits"]:
            print(f"     framework signals: {', '.join(detail['fw_hits'][:5])}")
        if detail["proj_hits"]:
            print(f"     project signals:   {', '.join(detail['proj_hits'][:5])}")
        print()


if __name__ == "__main__":
    main()
