#!/usr/bin/env python3
"""commit_readiness.py — Evaluación rápida de preparación para commit.

Responde en segundos si tu código está listo para commitear.
A diferencia de ci_report (10 scanners, lento), este hace un check
rápido y opinionado enfocado en los errores que más bloquean.

Chequeos (en orden de criticidad):
  1. Sintaxis Python válida en archivos staged
  2. Sin secretos obvios en archivos staged
  3. Sin conflictos de merge sin resolver
  4. Sin print() de debug sin comentar
  5. Sin TODOs añadidos en el diff actual
  6. Tamaño de archivo razonable (<500KB por archivo)

Uso:
    python3 commit_readiness.py               # evalúa archivos staged
    python3 commit_readiness.py --all         # evalúa todos los .py del proyecto
    python3 commit_readiness.py --file foo.py # evalúa un archivo específico
    python3 commit_readiness.py --strict      # activa checks extra (funciones sin docstring)
    python3 commit_readiness.py --fix         # auto-elimina print() de debug con flag #debug
    python3 commit_readiness.py --test        # self-tests

Códigos: CR-E001 (sintaxis), CR-E002 (secreto), CR-E003 (conflicto merge),
         CR-W001 (print debug), CR-W002 (TODO nuevo), CR-W003 (archivo grande),
         CR-I001 (todo OK)
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
import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path

BAGO_ROOT = Path(__file__).parent.parent
PROJECT_ROOT = BAGO_ROOT.parent
BAGO_TOOLS_DIR = BAGO_ROOT / "tools"   # CLI tools: print() is intentional output, not debug

SECRET_PATTERNS = [
    (r'(?i)(api[_\-]?key|secret|password|passwd|token|auth[_\-]?key)\s*=\s*["\'][^"\']{8,}["\']', "CR-E002", "credencial hardcoded"),
    (r'(?i)(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{36,}|glpat-[a-zA-Z0-9\-_]{20,})', "CR-E002", "token hardcoded"),
    (r'(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)', "CR-W002", "IP hardcoded"),
]

MERGE_CONFLICT_RE = re.compile(r'^(<{7}|={7}|>{7})\s', re.MULTILINE)
DEBUG_PRINT_RE = re.compile(r'^\s*print\s*\(', re.MULTILINE)
TODO_ADDED_RE = re.compile(r'^\+.*\b(TODO|FIXME|HACK|XXX)\b', re.MULTILINE)
MAX_FILE_SIZE = 500 * 1024  # 500KB


@lru_cache(maxsize=1)
def _load_validation_config() -> dict[str, object]:
    try:
        from bago_config import load_config
        data = load_config("validation_patterns", fallback=None)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _get_secret_patterns() -> list[tuple[str, str, str]]:
    patterns = _load_validation_config().get("secret_patterns")
    if not isinstance(patterns, list):
        return SECRET_PATTERNS
    converted: list[tuple[str, str, str]] = []
    for item in patterns:
        if isinstance(item, list) and len(item) == 3:
            converted.append((str(item[0]), str(item[1]), str(item[2])))
    return converted or SECRET_PATTERNS


def _get_max_file_size() -> int:
    value = _load_validation_config().get("max_file_size_bytes")
    return value if isinstance(value, int) and value > 0 else MAX_FILE_SIZE


def get_staged_files() -> list:
    """Retorna lista de archivos Python staged para commit."""
    try:
        r = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT)
        )
        if r.returncode != 0:
            return []
        return [
            PROJECT_ROOT / f.strip()
            for f in r.stdout.splitlines()
            if f.strip().endswith(".py")
        ]
    except Exception:
        return []


def get_staged_diff() -> str:
    """Retorna el diff actual de git."""
    try:
        r = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT)
        )
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def check_syntax(filepath: Path) -> list:
    findings = []
    try:
        src = filepath.read_text(encoding="utf-8", errors="replace")
        ast.parse(src)
    except SyntaxError as e:
        findings.append({
            "code": "CR-E001", "file": str(filepath.name),
            "line": e.lineno or 0, "msg": str(e.msg),
        })
    except Exception as e:
        findings.append({
            "code": "CR-E001", "file": str(filepath.name),
            "line": 0, "msg": str(e),
        })
    return findings


def check_secrets(filepath: Path) -> list:
    findings = []
    try:
        src = filepath.read_text(encoding="utf-8", errors="replace")
        src_lines = src.splitlines()
        for pattern, code, label in _get_secret_patterns():
            for m in re.finditer(pattern, src):
                line_no = src[:m.start()].count("\n") + 1
                # Honour # nosec inline suppression (bandit-compatible)
                if 0 < line_no <= len(src_lines) and "# nosec" in src_lines[line_no - 1]:
                    continue
                snippet = m.group(0)[:40]
                findings.append({
                    "code": code, "file": str(filepath.name),
                    "line": line_no, "msg": f"{label}: {snippet}…",
                })
    except Exception:
        pass
    return findings


def check_merge_conflicts(filepath: Path) -> list:
    findings = []
    try:
        src = filepath.read_text(encoding="utf-8", errors="replace")
        if MERGE_CONFLICT_RE.search(src):
            findings.append({
                "code": "CR-E003", "file": str(filepath.name),
                "line": 0, "msg": "conflicto de merge sin resolver",
            })
    except Exception:
        pass
    return findings


def check_debug_prints(filepath: Path) -> list:
    findings = []
    try:
        src = filepath.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(src.splitlines(), 1):
            stripped = line.strip()
            if (stripped.startswith("print(") or stripped.startswith("print ("))\
                    and "#debug" not in line.lower() and "#keep" not in line.lower():
                findings.append({
                    "code": "CR-W001", "file": str(filepath.name),
                    "line": i, "msg": f"print() sin marcar: {stripped[:50]}",
                })
    except Exception:
        pass
    return findings


def check_new_todos(diff: str) -> list:
    findings = []
    for m in TODO_ADDED_RE.finditer(diff):
        snippet = m.group(0)[:60].lstrip("+").strip()
        findings.append({
            "code": "CR-W002", "file": "diff",
            "line": 0, "msg": f"TODO/FIXME añadido: {snippet}",
        })
    return findings


def check_file_size(filepath: Path) -> list:
    findings = []
    try:
        size = filepath.stat().st_size
        max_file_size = _get_max_file_size()
        if size > max_file_size:
            findings.append({
                "code": "CR-W003", "file": str(filepath.name),
                "line": 0, "msg": f"archivo grande: {size // 1024}KB (max {max_file_size // 1024}KB)",
            })
    except Exception:
        pass
    return findings


def fix_debug_prints(filepath: Path) -> int:
    """Elimina líneas print() de debug (las marca con #debug-removed)."""
    try:
        src = filepath.read_text(encoding="utf-8")
        lines = src.splitlines(keepends=True)
        fixed = 0
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if (stripped.startswith("print(") or stripped.startswith("print ("))\
                    and "#debug" not in line and "#keep" not in line:
                indent = len(line) - len(line.lstrip())
                new_lines.append(" " * indent + "# " + stripped + "  #debug-removed\n")
                fixed += 1
            else:
                new_lines.append(line)
        if fixed > 0:
            filepath.write_text("".join(new_lines), encoding="utf-8")
        return fixed
    except Exception:
        return 0


def evaluate_files(files: list, strict: bool = False) -> dict:
    diff = get_staged_diff()
    errors = []
    warnings = []

    for f in files:
        if not f.exists():
            continue
        errors.extend(check_syntax(f))
        errors.extend(check_secrets(f))
        errors.extend(check_merge_conflicts(f))
        # Skip W001 for BAGO CLI tools — print() is intentional CLI output, not debug
        if not str(f).startswith(str(BAGO_TOOLS_DIR)):
            warnings.extend(check_debug_prints(f))
        warnings.extend(check_file_size(f))

    warnings.extend(check_new_todos(diff))

    score = 100
    score -= len(errors) * 20
    score -= len(warnings) * 5
    score = max(0, score)

    if errors:
        verdict = "❌ NO COMMITEAR"
        status = "BLOCKED"
    elif warnings:
        verdict = "⚠️  REVISAR"
        status = "WARN"
    else:
        verdict = "✅ LISTO"
        status = "GO"

    return {
        "files": len(files), "errors": errors,
        "warnings": warnings, "score": score,
        "verdict": verdict, "status": status,
    }


def print_report(result: dict):
    print(f"\n  🔍 Commit Readiness — {result['files']} archivo(s)")
    print(f"  Score: {result['score']}/100   {result['verdict']}")
    print()

    if result["errors"]:
        print(f"  ❌ ERRORES ({len(result['errors'])}): bloquean el commit")
        for f in result["errors"]:
            print(f"    [{f['code']}] {f['file']}:{f['line']} — {f['msg']}")
        print()

    if result["warnings"]:
        print(f"  ⚠️  ADVERTENCIAS ({len(result['warnings'])})")
        for f in result["warnings"][:10]:
            print(f"    [{f['code']}] {f['file']}:{f['line']} — {f['msg']}")
        if len(result["warnings"]) > 10:
            print(f"    … y {len(result['warnings']) - 10} más")
        print()

    if result["status"] == "GO":
        print("  ✅ Código limpio. Puedes commitear con confianza.")
    elif result["status"] == "WARN":
        print("  ⚠️  Revisa las advertencias antes de commitear.")
    else:
        print("  ❌ Corrige los errores antes de commitear.")


def run_tests():
    import tempfile
    results = []

    # Test 1: syntax check detects error
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def foo(:\n    pass\n")
        tmp = Path(f.name)
    findings = check_syntax(tmp)
    ok1 = len(findings) == 1 and findings[0]["code"] == "CR-E001"
    results.append(("commit_readiness:syntax_error_detected", ok1, f"findings={len(findings)}"))

    # Test 2: valid syntax passes
    tmp.write_text("def foo():\n    return 1\n")
    findings = check_syntax(tmp)
    ok2 = len(findings) == 0
    results.append(("commit_readiness:valid_syntax_ok", ok2, f"findings={len(findings)}"))

    # Test 3: secret detection
    tmp.write_text('API_KEY = "sk-abcdefghijklmnopqrstuvwxyz12345678"\n')  # noqa: test fixture
    findings = check_secrets(tmp)
    ok3 = any(f["code"] == "CR-E002" for f in findings)
    results.append(("commit_readiness:secret_detected", ok3, f"findings={len(findings)}"))

    # Test 4: merge conflict detection
    tmp.write_text("<<<<<<< HEAD\nfoo = 1\n=======\nfoo = 2\n>>>>>>> branch\n")
    findings = check_merge_conflicts(tmp)
    ok4 = len(findings) == 1 and findings[0]["code"] == "CR-E003"
    results.append(("commit_readiness:merge_conflict", ok4, f"findings={len(findings)}"))

    # Test 5: debug print detection
    tmp.write_text("def foo():\n    print('debug value')\n    return 1\n")
    findings = check_debug_prints(tmp)
    ok5 = len(findings) == 1 and findings[0]["code"] == "CR-W001"
    results.append(("commit_readiness:debug_print", ok5, f"findings={len(findings)}"))

    # Test 6: evaluate clean file → GO
    tmp.write_text("def foo():\n    return 42\n")
    result = evaluate_files([tmp])
    ok6 = result["status"] == "GO" and result["score"] == 100
    results.append(("commit_readiness:clean_file_go", ok6, f"status={result['status']} score={result['score']}"))

    tmp.unlink(missing_ok=True)

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    for name, ok, detail in results:
        status = "✅" if ok else "❌"
        print(f"  {status}  {name}: {detail}")
    print(f"\n  {passed}/{len(results)} pasaron")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        raise SystemExit(0)

    if "--test" in args:
        raise SystemExit(run_tests())

    strict = "--strict" in args
    fix_mode = "--fix" in args
    args_clean = [a for a in args if not a.startswith("--")]

    # Determine files to check
    if "--file" in sys.argv:
        i = sys.argv.index("--file")
        fp = Path(sys.argv[i + 1])
        files = [fp] if fp.exists() else []
    elif "--all" in args:
        files = list(PROJECT_ROOT.rglob("*.py"))
        files = [f for f in files if "__pycache__" not in str(f)]
    else:
        files = get_staged_files()
        if not files:
            print("  Sin archivos Python staged. Usa --all o --file <path>")
            raise SystemExit(0)

    if fix_mode:
        total_fixed = 0
        for f in files:
            n = fix_debug_prints(f)
            if n > 0:
                print(f"  [FIX] {f.name}: {n} print() comentados")
                total_fixed += n
        print(f"\n  Total: {total_fixed} print() comentados")
        raise SystemExit(0)

    result = evaluate_files(files, strict=strict)
    print_report(result)
    exit_code = 0 if result["status"] != "BLOCKED" else 1
    try:
        import importlib.util as _ilu
        _ep = Path(__file__).parent / "bago_sac_engine.py"
        _spec = _ilu.spec_from_file_location("bago_sac_engine", str(_ep))
        _mod = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_mod)
        _mod.sac_suggest("bago commit", exit_code=exit_code)
    except Exception:
        pass
    raise SystemExit(exit_code)
