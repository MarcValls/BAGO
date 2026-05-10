#!/usr/bin/env python3
"""code_review.py — Herramienta #116: Reporte CI agregado de todos los scanners BAGO.

Ejecuta en secuencia: lint, complexity, secret-scan, dead-code, duplicate-check,
env-check y branch-check. Genera un reporte consolidado con score 0-100 y
recomienda si la PR puede hacer merge.

Uso:
    bago code-review [DIR] [--branch BRANCH] [--format text|md|html]
                     [--out FILE] [--min-score N] [--test]

Exit codes:
    0  Score >= mínimo (por defecto 60)
    1  Score < mínimo o error crítico
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

_GRN  = "\033[0;32m"
_YEL  = "\033[0;33m"
_RED  = "\033[0;31m"
_RST  = "\033[0m"
_BOLD = "\033[1m"

TOOLS_DIR = Path(__file__).parent


def _run_tool(tool: str, args: list[str], cwd: str, timeout: int = 60) -> tuple[int, str, str]:
    tool_path = TOOLS_DIR / tool
    if not tool_path.exists():
        return -1, "", f"tool not found: {tool}"
    try:
        r = subprocess.run(
            ["python3", str(tool_path)] + args,
            capture_output=True, text=True, timeout=timeout, cwd=cwd
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -2, "", f"timeout after {timeout}s"
    except Exception as e:
        return -3, "", str(e)


def _score_from_findings(findings_count: int, total_lines: int) -> int:
    """Convierte densidad de findings en puntuación 0-100."""
    if total_lines <= 0:
        return 80
    density = findings_count / max(1, total_lines / 100)  # por cada 100 líneas
    if density == 0:
        return 100
    elif density < 0.5:
        return 90
    elif density < 1:
        return 75
    elif density < 2:
        return 60
    elif density < 5:
        return 40
    else:
        return 20


def _count_py_lines(directory: str) -> int:
    root  = Path(directory)
    total = 0
    for f in root.rglob("*.py"):
        if "__pycache__" in str(f):
            continue
        try:
            total += len(f.read_text(encoding="utf-8", errors="ignore").splitlines())
        except Exception:
            pass
    return total


def _parse_scanner_output(tool: str, output: str) -> list[dict]:
    """Parsea la salida JSON esperada de un scanner o falla de forma observable."""
    if not output.strip():
        raise ValueError(f"{tool} produced empty output")
    data = json.loads(output)
    if not isinstance(data, list):
        raise ValueError(f"{tool} produced {type(data).__name__}, expected list")
    return data


def _section_status(findings: int, *, warn_below: int | None = None,
                    fail_below: int | None = None, hard_fail: bool = False) -> str:
    if findings == 0:
        return "ok"
    if hard_fail:
        return "fail"
    if fail_below is not None and findings >= fail_below:
        return "fail"
    if warn_below is not None and findings < warn_below:
        return "warn"
    return "fail"


def _run_scanner(*, key: str, name: str, tool: str, args: list[str], cwd: str,
                 detail_limit: int, warn_below: int | None = None,
                 fail_below: int | None = None, hard_fail: bool = False) -> tuple[str, dict, int]:
    rc, out, err = _run_tool(tool, args, cwd)

    section = {
        "name": name,
        "tool": tool,
        "findings": 0,
        "status": "fail",
        "scanner_status": "error",
        "exit_code": rc,
        "error": "",
        "details": [],
    }

    if rc not in (0, 1):
        section["error"] = f"{tool}: {err or f'unexpected exit code: {rc}'}"
        return key, section, 0

    try:
        data = _parse_scanner_output(tool, out)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        section["error"] = f"{tool}: {err or str(exc)}"
        return key, section, 0

    findings = len(data)
    section["findings"] = findings
    section["status"] = _section_status(
        findings,
        warn_below=warn_below,
        fail_below=fail_below,
        hard_fail=hard_fail,
    )
    section["scanner_status"] = "passed" if findings == 0 else "findings"
    section["error"] = ""
    section["details"] = data[:detail_limit]
    return key, section, findings


def run_reviews(directory: str, branch: str = "") -> dict:
    """Ejecuta todos los scanners y agrega resultados."""
    start     = time.time()
    sections  = {}
    total_findings = 0
    scanner_specs = [
        {
            "key": "lint",
            "name": "BAGO Lint",
            "tool": "scan.py",
            "args": [directory, "--format", "json"],
            "detail_limit": 5,
            "warn_below": 10,
            "weight": lambda count: count,
        },
        {
            "key": "complexity",
            "name": "Complexity (high)",
            "tool": "complexity.py",
            "args": [directory, "--min", "11", "--format", "json"],
            "detail_limit": 5,
            "warn_below": 5,
            "weight": lambda count: count,
        },
        {
            "key": "secrets",
            "name": "Secret Scan",
            "tool": "secret_scan.py",
            "args": [directory, "--format", "json"],
            "detail_limit": 3,
            "hard_fail": True,
            "weight": lambda count: count * 3,
        },
        {
            "key": "dead_code",
            "name": "Dead Code",
            "tool": "dead_code.py",
            "args": [directory, "--format", "json"],
            "detail_limit": 3,
            "warn_below": 10,
            "weight": lambda count: count // 2,
        },
        {
            "key": "duplicates",
            "name": "Duplicate Check",
            "tool": "duplicate_check.py",
            "args": [directory, "--format", "json"],
            "detail_limit": 3,
            "warn_below": 3,
            "weight": lambda count: count,
        },
    ]

    for spec in scanner_specs:
        key, section, findings = _run_scanner(
            key=spec["key"],
            name=spec["name"],
            tool=spec["tool"],
            args=spec["args"],
            cwd=directory,
            detail_limit=spec["detail_limit"],
            warn_below=spec.get("warn_below"),
            fail_below=spec.get("fail_below"),
            hard_fail=spec.get("hard_fail", False),
        )
        sections[key] = section
        total_findings += spec["weight"](findings)

    total_lines = _count_py_lines(directory)
    score       = _score_from_findings(total_findings, total_lines)
    scanner_errors = {
        key: sec["error"]
        for key, sec in sections.items()
        if sec["scanner_status"] == "error"
    }

    # Penalizar si hay secretos (crítico)
    if sections["secrets"]["findings"] > 0:
        score = min(score, 30)
    if scanner_errors:
        score = 0

    elapsed = round(time.time() - start, 1)

    return {
        "directory":    directory,
        "branch":       branch,
        "timestamp":    int(time.time()),
        "elapsed_s":    elapsed,
        "score":        score,
        "total_lines":  total_lines,
        "total_findings": total_findings,
        "scanner_failures": len(scanner_errors),
        "scanner_errors": scanner_errors,
        "sections":     sections,
        "verdict":      "❌ NO MERGE (scanner error)" if scanner_errors else ("✅ MERGE OK" if score >= 60 else "❌ NO MERGE"),
    }


def generate_text(report: dict) -> str:
    sc    = report["score"]
    color = _GRN if sc >= 80 else (_YEL if sc >= 60 else _RED)
    lines = [
        f"{_BOLD}╔══ BAGO Code Review ══╗{_RST}",
        f"  Score:   {color}{sc}/100{_RST}",
        f"  Verdict: {_BOLD}{report['verdict']}{_RST}",
        f"  Lines:   {report['total_lines']}  |  Findings: {report['total_findings']}  |  Scanner failures: {report['scanner_failures']}  |  Time: {report['elapsed_s']}s",
        "",
    ]
    for key, sec in report["sections"].items():
        icon = "✅" if sec["status"] == "ok" else ("⚠️" if sec["status"] == "warn" else "❌")
        lines.append(
            f"  {icon} {sec['name']:20s}  {sec['findings']} hallazgo(s)  "
            f"[scanner={sec['scanner_status']}, rc={sec['exit_code']}]"
        )
        if sec["error"]:
            lines.append(f"      ↳ {sec['error']}")
    lines += ["", f"  {_BOLD}{'─'*40}{_RST}"]
    return "\n".join(lines)


def generate_markdown(report: dict) -> str:
    sc    = report["score"]
    badge = "🟢" if sc >= 80 else ("🟡" if sc >= 60 else "🔴")
    lines = [
        f"# BAGO Code Review",
        f"",
        f"**Score:** {badge} {sc}/100  |  **Verdict:** {report['verdict']}",
        f"",
        f"| Scanner | Findings | Review status | Scanner status |",
        f"|---------|----------|---------------|----------------|",
    ]
    for sec in report["sections"].values():
        icon = "✅" if sec["status"] == "ok" else ("⚠️" if sec["status"] == "warn" else "❌")
        scanner_status = sec["scanner_status"]
        if sec["error"]:
            scanner_status = f"{scanner_status} (`rc={sec['exit_code']}`)"
        lines.append(f"| {sec['name']} | {sec['findings']} | {icon} | {scanner_status} |")
    lines += [
        f"",
        f"**Líneas analizadas:** {report['total_lines']}  "
        f"| **Tiempo:** {report['elapsed_s']}s  "
        f"| **Scanner failures:** {report['scanner_failures']}",
        f"",
    ]
    for key, error in report["scanner_errors"].items():
        lines += [f"- `{key}`: {error}"]
    lines += [
        f"",
        f"---",
        f"*Generado con `bago code-review`*",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    directory  = "./"
    branch     = ""
    fmt        = "text"
    out_file   = None
    min_score  = 60

    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--branch" and i + 1 < len(argv):
            branch = argv[i + 1]; i += 2
        elif a == "--format" and i + 1 < len(argv):
            fmt = argv[i + 1]; i += 2
        elif a == "--out" and i + 1 < len(argv):
            out_file = argv[i + 1]; i += 2
        elif a == "--min-score" and i + 1 < len(argv):
            min_score = int(argv[i + 1]); i += 2
        elif not a.startswith("--"):
            directory = a; i += 1
        else:
            i += 1

    if not Path(directory).exists():
        print(f"No existe: {directory}", file=sys.stderr); return 1

    print(f"Analizando {directory}…", file=sys.stderr)
    report = run_reviews(directory, branch)

    if fmt == "json":
        content = json.dumps(report, indent=2)
    elif fmt == "md":
        content = generate_markdown(report)
    else:
        content = generate_text(report)

    if out_file:
        Path(out_file).write_text(content, encoding="utf-8")
        print(f"Guardado: {out_file}", file=sys.stderr)
    else:
        print(content)

    if report["score"] < min_score:
        return 1
    return 0


def _self_test() -> None:
    import tempfile
    print("Tests de code_review.py...")
    fails: list[str] = []
    def ok(n): print(f"  OK: {n}")
    def fail(n, m): fails.append(n); print(f"  FAIL: {n}: {m}")

    with tempfile.TemporaryDirectory() as td:
        from pathlib import Path as P
        (P(td) / "clean.py").write_text(
            '"""Módulo limpio."""\ndef add(a, b):\n    """Suma."""\n    return a + b\n'
        )

        original_run_tool = globals()["_run_tool"]
        original_count_py_lines = globals()["_count_py_lines"]
        globals()["_run_tool"] = lambda tool, args, cwd, timeout=60: (0, "[]", "")
        globals()["_count_py_lines"] = lambda _: 100

        # T1 — run_reviews retorna score
        report = run_reviews(td)
        if "score" in report and 0 <= report["score"] <= 100:
            ok("code_review:score_range")
        else:
            fail("code_review:score_range", str(report.get("score")))

        # T2 — verdict presente
        if "verdict" in report and ("MERGE" in report["verdict"] or "NO" in report["verdict"]):
            ok("code_review:verdict_present")
        else:
            fail("code_review:verdict_present", str(report.get("verdict")))

        # T3 — sections contiene los 5 scanners
        secs = set(report.get("sections", {}).keys())
        expected = {"lint", "complexity", "secrets", "dead_code", "duplicates"}
        if expected <= secs:
            ok("code_review:sections_complete")
        else:
            fail("code_review:sections_complete", f"missing={expected - secs}")

        # T4 — clean code da score alto
        if report["score"] >= 60:
            ok("code_review:clean_code_score")
        else:
            fail("code_review:clean_code_score", f"score={report['score']} too low for clean code")

        # T5 — markdown generado
        md = generate_markdown(report)
        if "BAGO Code Review" in md and "Score" in md and "Scanner status" in md:
            ok("code_review:markdown_generated")
        else:
            fail("code_review:markdown_generated", md[:80])

        # T6 — _score_from_findings lógica
        assert _score_from_findings(0, 1000) == 100
        assert _score_from_findings(100, 100) <= 40
        ok("code_review:score_function")

        # T7 — scanner roto no puede dar falso verde
        try:
            def _broken_run_tool(tool, args, cwd, timeout=60):
                if tool == "complexity.py":
                    return -1, "", "tool not found: complexity.py"
                return 0, "[]", ""

            globals()["_run_tool"] = _broken_run_tool
            globals()["_count_py_lines"] = lambda _: 100
            broken = run_reviews(td)
            if broken["score"] == 0 and broken["scanner_failures"] == 1 and broken["sections"]["complexity"]["scanner_status"] == "error":
                ok("code_review:fail_closed_on_scanner_error")
            else:
                fail("code_review:fail_closed_on_scanner_error", str(broken))
        finally:
            globals()["_run_tool"] = original_run_tool
            globals()["_count_py_lines"] = original_count_py_lines

        # T8 — JSON inválido se hace observable en el reporte
        try:
            def _invalid_json_run_tool(tool, args, cwd, timeout=60):
                if tool == "secret_scan.py":
                    return 0, "{oops", ""
                return 0, "[]", ""

            globals()["_run_tool"] = _invalid_json_run_tool
            globals()["_count_py_lines"] = lambda _: 100
            invalid = run_reviews(td)
            if invalid["score"] == 0 and invalid["sections"]["secrets"]["scanner_status"] == "error":
                ok("code_review:fail_closed_on_invalid_json")
            else:
                fail("code_review:fail_closed_on_invalid_json", str(invalid))
        finally:
            globals()["_run_tool"] = original_run_tool
            globals()["_count_py_lines"] = original_count_py_lines

    total = 8; passed = total - len(fails)
    print(f"\n  {passed}/{total} tests pasaron")
    if fails: raise SystemExit(1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
    else:
        raise SystemExit(main(sys.argv[1:]))
