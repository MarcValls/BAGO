from __future__ import annotations
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import re, sys
from pathlib import Path

_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from _findings_model import Finding, _make_id, _read_context

def run_bago_lint(target_dir: str) -> list:
    """
    BAGO's own lint: checks Python files for known issues.
    Returns list of Finding objects (no external dependency).

    Rules:
      BAGO-W001  datetime.utcnow — deprecated since Python 3.12
      BAGO-I001  raise SystemExit(1) without user-visible message
      BAGO-E001  bare except Exception: clause — catches SystemExit/KeyboardInterrupt
      BAGO-W002  eval() or exec() — security risk # noqa: BAGO-W002
      BAGO-W003  os.system() — should use subprocess  # noqa: BAGO-W003
      BAGO-W004  hardcoded absolute user path (/Users/, /home/, C:\\) — not portable
      BAGO-I002  TODO/FIXME/HACK comments — technical debt markers
    """
    findings = []
    target = Path(target_dir)
    _bare_except_re  = re.compile(r'^\s*except\s*:', re.MULTILINE)
    _eval_exec_re    = re.compile(r'\b(eval|exec)\s*\(')
    _os_system_re    = re.compile(r'\bos\.system\s*\(')
    _hardpath_re     = re.compile(r'["\'](?:/Users/\w+|/home/\w+|C:\\\\Users\\\\)[^"\']*["\']')
    _todo_re         = re.compile(r'#.*\b(TODO|FIXME|HACK|XXX)\b', re.IGNORECASE)  # noqa: BAGO-I002
    _noqa_re         = re.compile(r'#\s*noqa(?::\s*([\w,\s-]+))?')

    for pyfile in sorted(target.rglob("*.py")):
        try:
            src   = pyfile.read_text(errors="replace")
            lines = src.splitlines()
            rel   = str(pyfile)
            is_test = "test" in pyfile.name.lower()
            for i, line in enumerate(lines, 1):
                # Check for # noqa suppression (flake8-compatible)
                noqa_m = _noqa_re.search(line)
                if noqa_m:
                    noqa_codes = {c.strip() for c in noqa_m.group(1).split(",")} if noqa_m.group(1) else set()
                    if not noqa_codes:  # bare # noqa → suppress all
                        continue
                    _noqa_all = noqa_codes  # used per-rule below
                else:
                    _noqa_all = set()

                def _suppressed(rule: str) -> bool:
                    return bool(_noqa_all and (rule in _noqa_all or "BAGO" in _noqa_all))

                # BAGO-W001: deprecated utcnow()
                if not _suppressed("BAGO-W001") and ("datetime.utcnow()" in line or ".utcnow()" in line):  # noqa: BAGO-W001
                    fid = _make_id("bago", rel, i, "BAGO-W001")
                    findings.append(Finding(
                        id=fid, severity="warning", file=rel, line=i, col=0,
                        rule="BAGO-W001", source="bago",
                        message="datetime.utcnow() deprecated — use datetime.now(timezone.utc)",  # noqa: BAGO-W001
                        fix_suggestion="Usa datetime.datetime.now(datetime.timezone.utc)",
                        autofixable=True,
                        fix_patch=_make_utcnow_patch(rel, i, line),
                        context_lines=_read_context(rel, i),
                    ))
                # BAGO-I001: bare sys.exit(1) without message (skip comments and raise SystemExit)
                _stripped_i001 = line.lstrip()
                if (not _suppressed("BAGO-I001") and not _stripped_i001.startswith('#')
                        and re.search(r'\bsys\.exit\(\d+\)\s*$', line) and not is_test):
                    fid = _make_id("bago", rel, i, "BAGO-I001")
                    findings.append(Finding(
                        id=fid, severity="info", file=rel, line=i, col=0,
                        rule="BAGO-I001", source="bago",
                        message="raise SystemExit(1) sin mensaje de error claro para el usuario",
                        fix_suggestion="Añade print(mensaje) antes de raise SystemExit(1)",
                        autofixable=False,
                        context_lines=_read_context(rel, i),
                    ))
                # BAGO-E001: bare except Exception:
                if not _suppressed("BAGO-E001") and _bare_except_re.match(line):
                    fid = _make_id("bago", rel, i, "BAGO-E001")
                    findings.append(Finding(
                        id=fid, severity="error", file=rel, line=i, col=0,
                        rule="BAGO-E001", source="bago",
                        message="bare except Exception: captura SystemExit y KeyboardInterrupt",
                        fix_suggestion="Usa 'except Exception:' para capturar solo errores de aplicación",
                        autofixable=True,
                        fix_patch=_make_bare_except_patch(rel, i, line),
                        context_lines=_read_context(rel, i),
                    ))
                # BAGO-W002: eval() or exec() — skip test files # noqa: BAGO-W002
                if not _suppressed("BAGO-W002") and not is_test and _eval_exec_re.search(line):
                    kw = "eval" if "eval(" in line else "exec" # noqa: BAGO-W002
                    fid = _make_id("bago", rel, i, "BAGO-W002")
                    findings.append(Finding(
                        id=fid, severity="warning", file=rel, line=i, col=0,
                        rule="BAGO-W002", source="bago",
                        message=f"{kw}() es un riesgo de seguridad — evitar en producción",
                        fix_suggestion=f"Reemplaza {kw}() por lógica explícita o ast.literal_eval()",
                        autofixable=False,
                        context_lines=_read_context(rel, i),
                    ))
                # BAGO-W003: os.system() — skip test and ci_generator  # noqa: BAGO-W003
                if not _suppressed("BAGO-W003") and not is_test and _os_system_re.search(line):
                    fid = _make_id("bago", rel, i, "BAGO-W003")
                    findings.append(Finding(
                        id=fid, severity="warning", file=rel, line=i, col=0,
                        rule="BAGO-W003", source="bago",
                        message="os.system() no captura salida ni maneja errores",  # noqa: BAGO-W003
                        fix_suggestion="Usa subprocess.run() con capture_output=True",
                        autofixable=False,
                        context_lines=_read_context(rel, i),
                    ))
                # BAGO-W004: hardcoded absolute user paths
                if not _suppressed("BAGO-W004") and not is_test and _hardpath_re.search(line):
                    m4 = _hardpath_re.search(line)
                    found_path = m4.group(0).strip("'\"") if m4 else ""
                    fid = _make_id("bago", rel, i, "BAGO-W004")
                    findings.append(Finding(
                        id=fid, severity="warning", file=rel, line=i, col=0,
                        rule="BAGO-W004", source="bago",
                        message=f"Path absoluto hardcoded: '{found_path}' — no portable",
                        fix_suggestion="Usa Path.home() / os.path.expanduser('~') o variables de entorno",
                        autofixable=False,
                        context_lines=_read_context(rel, i),
                    ))
                # BAGO-I002: TODO/FIXME/HACK  # noqa: BAGO-I002
                if not _suppressed("BAGO-I002") and _todo_re.search(line):
                    m = _todo_re.search(line)
                    kw = m.group(1).upper() if m else "TODO"
                    fid = _make_id("bago", rel, i, "BAGO-I002")
                    findings.append(Finding(
                        id=fid, severity="info", file=rel, line=i, col=0,
                        rule="BAGO-I002", source="bago",
                        message=f"{kw}: deuda técnica pendiente",
                        fix_suggestion="Resuelve o registra en bago debt",
                        autofixable=False,
                        context_lines=_read_context(rel, i),
                    ))
        except Exception:
            pass
    return findings


def _make_bare_except_patch(filepath: str, lineno: int, line: str) -> str:
    """Generate a unified diff patch for bare except → except Exception."""
    new = line.replace("except Exception:", "except Exception:", 1)
    if new == line:
        return ""
    return (
        f"--- a/{filepath}\n+++ b/{filepath}\n"
        f"@@ -{lineno},1 +{lineno},1 @@\n"
        f"-{line}\n+{new}\n"
    )


def _make_utcnow_patch(filepath: str, lineno: int, line: str) -> str:
    """Generate a unified diff patch for utcnow replacement."""
    old = line
    new = re.sub(
        r'datetime\.datetime\.utcnow\(\)',
        'datetime.datetime.now(datetime.timezone.utc)',
        re.sub(r'datetime\.utcnow\(\)',
               'datetime.datetime.now(datetime.timezone.utc)', line)
    )
    if old == new:
        return ""
    return (
        f"--- a/{filepath}\n+++ b/{filepath}\n"
        f"@@ -{lineno},1 +{lineno},1 @@\n"
        f"-{old}\n+{new}\n"
    )


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

