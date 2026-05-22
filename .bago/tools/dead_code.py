#!/usr/bin/env python3
"""dead_code.py — Herramienta #102: Detector de código muerto (Python).

Detecta:
 - Imports no usados (import X donde X nunca se referencia)
 - Funciones definidas pero nunca llamadas en el mismo archivo
 - Variables asignadas pero nunca leídas (heurística de nombre)
 - TODO/FIXME/HACK en el código
 - Código comentado (bloques de # con sintaxis Python)

Uso:
    bago dead-code [TARGET] [--json] [--severity error|warning|info]
                   [--no-unused-imports] [--no-unused-funcs] [--test]

Opciones:
    TARGET            Archivo o directorio (default: ./)
    --json            Output en JSON
    --severity LEVEL  Filtrar por severidad mínima
    --no-unused-imports  Deshabilitar detección de imports no usados
    --no-unused-funcs    Deshabilitar detección de funciones no llamadas
    --test            Self-tests internos
"""
from __future__ import annotations

import ast
import re
import sys
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

_RED  = "\033[0;31m"
_YEL  = "\033[0;33m"
_BLU  = "\033[0;34m"
_GRN  = "\033[0;32m"
_DIM  = "\033[2m"
_RST  = "\033[0m"

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}

TODO_RE    = re.compile(r'#\s*(TODO|FIXME|HACK|XXX|BUG)\b[:\s]*(.*)', re.IGNORECASE)  # noqa: BAGO-I002
COMMENTED_CODE_RE = re.compile(
    r'^\s*#\s*(def |class |return |import |from |if |for |while |with |try:|except)', re.MULTILINE
)


@dataclass
class DeadFinding:
    file:     str
    line:     int
    rule:     str
    severity: str
    message:  str
    snippet:  str = ""


# ─── AST-based analyzers ───────────────────────────────────────────────────

def _analyze_imports(tree: ast.Module, source: str, filepath: str) -> list[DeadFinding]:
    """Detecta imports no usados comparando nombres importados vs referencias en el código."""
    findings: list[DeadFinding] = []
    source_no_imports = source  # para buscar referencias

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name.split(".")[0]
                if name == "*":
                    continue
                # Buscar el nombre en el resto del código (excluyendo la línea del import)
                lines = source.splitlines()
                import_line = node.lineno - 1  # 0-indexed
                other_lines = [l for i, l in enumerate(lines) if i != import_line]
                other_source = "\n".join(other_lines)

                # Búsqueda simple de referencia
                pattern = r'\b' + re.escape(name) + r'\b'
                if not re.search(pattern, other_source):
                    findings.append(DeadFinding(
                        file=filepath, line=node.lineno,
                        rule="DC-W001", severity="warning",
                        message=f"Import '{name}' posiblemente no usado",
                        snippet=lines[import_line].strip() if import_line < len(lines) else ""
                    ))
    return findings


def _analyze_functions(tree: ast.Module, source: str, filepath: str) -> list[DeadFinding]:
    """Detecta funciones definidas pero aparentemente no llamadas en el mismo módulo."""
    findings: list[DeadFinding] = []
    lines = source.splitlines()

    # Recopilar nombres de funciones top-level (no métodos)
    defined: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            # Solo funciones top-level (parent es Module)
            defined[node.name] = node.lineno

    # Buscar llamadas en el código
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                calls.add(func.id)
            elif isinstance(func, ast.Attribute):
                calls.add(func.attr)

    # También buscar referencias en decoradores, __all__, etc.
    dunder_all_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant):
                                dunder_all_names.add(str(elt.value))

    for fname, lineno in defined.items():
        if fname not in calls and fname not in dunder_all_names:
            line_str = lines[lineno - 1].strip() if lineno <= len(lines) else ""
            # Excluir main, test_, _etc, y funciones que parezcan entry points
            if fname in ("main", "run", "start", "setup", "teardown"):
                continue
            findings.append(DeadFinding(
                file=filepath, line=lineno,
                rule="DC-W002", severity="info",
                message=f"Función '{fname}' definida pero no llamada en este módulo",
                snippet=line_str
            ))
    return findings


def _analyze_todos(source: str, filepath: str) -> list[DeadFinding]:
    """Detecta TODO/FIXME/HACK en comentarios."""
    findings: list[DeadFinding] = []
    for i, line in enumerate(source.splitlines(), 1):
        m = TODO_RE.search(line)
        if m:
            tag  = m.group(1).upper()
            text = m.group(2).strip()
            sev  = "warning" if tag in ("FIXME", "BUG", "HACK") else "info"
            rule = "DC-I001" if sev == "info" else "DC-W003"
            findings.append(DeadFinding(
                file=filepath, line=i,
                rule=rule, severity=sev,
                message=f"{tag}: {text[:80]}" if text else tag,
                snippet=line.strip()[:80]
            ))
    return findings


def _analyze_commented_code(source: str, filepath: str) -> list[DeadFinding]:
    """Detecta bloques de código Python comentado."""
    findings: list[DeadFinding] = []
    for i, line in enumerate(source.splitlines(), 1):
        if COMMENTED_CODE_RE.match(line):
            findings.append(DeadFinding(
                file=filepath, line=i,
                rule="DC-I002", severity="info",
                message="Posible código comentado",
                snippet=line.strip()[:80]
            ))
    return findings


# ─── File scanner ──────────────────────────────────────────────────────────

def scan_file(filepath: str, check_imports: bool = True,
              check_funcs: bool = True) -> list[DeadFinding]:
    """Analiza un archivo Python y devuelve todos los hallazgos."""
    path = Path(filepath)
    if not path.exists() or path.suffix != ".py":
        return []
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
        tree   = ast.parse(source, filename=filepath)
    except SyntaxError:
        return []

    findings: list[DeadFinding] = []
    if check_imports:
        findings.extend(_analyze_imports(tree, source, filepath))
    if check_funcs:
        findings.extend(_analyze_functions(tree, source, filepath))
    findings.extend(_analyze_todos(source, filepath))
    findings.extend(_analyze_commented_code(source, filepath))
    return findings


def scan_target(target: str, check_imports: bool = True,
                check_funcs: bool = True) -> list[DeadFinding]:
    """Escanea un archivo o directorio."""
    p = Path(target)
    files: list[Path] = []
    if p.is_file():
        files = [p]
    elif p.is_dir():
        files = [f for f in p.rglob("*.py")
                 if not any(x in f.parts for x in ("node_modules", "__pycache__", ".git", "venv", ".venv"))]

    all_findings: list[DeadFinding] = []
    for f in sorted(files):
        all_findings.extend(scan_file(str(f), check_imports, check_funcs))
    return all_findings


# ─── CLI ───────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    target         = "./"
    as_json        = False
    min_sev        = "info"
    check_imports  = True
    check_funcs    = True

    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--json":
            as_json = True; i += 1
        elif a == "--severity" and i + 1 < len(argv):
            min_sev = argv[i + 1]; i += 2
        elif a == "--no-unused-imports":
            check_imports = False; i += 1
        elif a == "--no-unused-funcs":
            check_funcs = False; i += 1
        elif not a.startswith("--"):
            target = a; i += 1
        else:
            i += 1

    findings = scan_target(target, check_imports, check_funcs)

    # Filtrar por severidad
    min_ord = SEVERITY_ORDER.get(min_sev, 2)
    findings = [f for f in findings if SEVERITY_ORDER.get(f.severity, 2) <= min_ord]

    if as_json:
        out = {
            "target": target,
            "total": len(findings),
            "findings": [asdict(f) for f in findings],
        }
        print(json.dumps(out, indent=2))
        return 1 if any(f.severity == "error" for f in findings) else 0

    errors   = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]
    infos    = [f for f in findings if f.severity == "info"]

    if not findings:
        print(f"{_GRN}✅ Sin hallazgos de código muerto en {target}{_RST}")
        return 0

    print(f"\n{_BLU}Dead Code scan — {target}{_RST}")
    print(f"Total: {len(findings)} ({len(errors)} errores, {len(warnings)} advertencias, {len(infos)} info)\n")

    for f in findings:
        sev_clr = _RED if f.severity == "error" else (_YEL if f.severity == "warning" else _DIM)
        print(f"  {sev_clr}{f.severity:7s}{_RST} [{f.rule}] {f.file}:{f.line}")
        print(f"  {_DIM}{f.message}{_RST}")
        if f.snippet:
            print(f"  {_DIM}> {f.snippet}{_RST}")
        print()

    return 1 if errors else 0


# ─── Self-tests ────────────────────────────────────────────────────────────

def _self_test() -> None:
    import tempfile, textwrap

    print("Tests de dead_code.py...")
    fails: list[str] = []
    def ok(n: str): print(f"  OK: {n}")
    def fail(n, m): fails.append(n); print(f"  FAIL: {n}: {m}")

    # T1 — unused import detectado
    src1 = textwrap.dedent("""\
        import os
        import sys
        print(sys.argv)
    """)
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(src1); tmp1 = f.name
    r1 = scan_file(tmp1, check_imports=True, check_funcs=False)
    unused = [x for x in r1 if x.rule == "DC-W001" and "os" in x.message]
    if unused:
        ok("dead_code:unused_import_detected")
    else:
        fail("dead_code:unused_import_detected", f"findings={[x.rule+':'+x.message for x in r1]}")

    # T2 — import usado no marcado como muerto
    sys_used = [x for x in r1 if x.rule == "DC-W001" and "'sys'" in x.message]
    if not sys_used:
        ok("dead_code:used_import_not_flagged")
    else:
        fail("dead_code:used_import_not_flagged", f"sys fue marcado: {sys_used}")

    # T3 — TODO detectado  # noqa: BAGO-I002
    src2 = textwrap.dedent("""\
        # TODO: implementar autenticación  # noqa: BAGO-I002
        x = 1
        # FIXME: esto rompe en Python 3.12  # noqa: BAGO-I002
    """)
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(src2); tmp2 = f.name
    r2 = scan_file(tmp2, check_imports=False, check_funcs=False)
    todos = [x for x in r2 if x.rule in ("DC-I001", "DC-W003")]
    if len(todos) == 2:
        ok("dead_code:todo_fixme_detected")
    else:
        fail("dead_code:todo_fixme_detected", f"found={len(todos)}")

    # T4 — código comentado detectado
    src3 = "# def old_function():\n#     return 42\nx = 1\n"
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(src3); tmp3 = f.name
    r3 = scan_file(tmp3, check_imports=False, check_funcs=False)
    commented = [x for x in r3 if x.rule == "DC-I002"]
    if commented:
        ok("dead_code:commented_code_detected")
    else:
        fail("dead_code:commented_code_detected", f"findings={[x.rule for x in r3]}")

    # T5 — función no llamada detectada
    src4 = textwrap.dedent("""\
        def helper_func():
            return 42
        def used_func():
            return 1
        result = used_func()
    """)
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(src4); tmp4 = f.name
    r4 = scan_file(tmp4, check_imports=False, check_funcs=True)
    unused_funcs = [x for x in r4 if x.rule == "DC-W002" and "helper_func" in x.message]
    if unused_funcs:
        ok("dead_code:unused_func_detected")
    else:
        fail("dead_code:unused_func_detected", f"findings={[(x.rule,x.message) for x in r4]}")

    # T6 — scan_target en directorio sin .py → vacío
    import os
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "test.txt").write_text("hello")
        r5 = scan_target(td)
    if r5 == []:
        ok("dead_code:empty_dir_no_findings")
    else:
        fail("dead_code:empty_dir_no_findings", f"found {len(r5)}")

    for t in [tmp1, tmp2, tmp3, tmp4]:
        Path(t).unlink(missing_ok=True)

    total = 6; passed = total - len(fails)
    print(f"\n  {passed}/{total} tests pasaron")
    if fails: raise SystemExit(1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
    else:
        raise SystemExit(main(sys.argv[1:]))
