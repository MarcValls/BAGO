#!/usr/bin/env python3
"""naming_check.py — Herramienta #120: Validador de convenciones de nombres.

Verifica que funciones, clases, variables y módulos sigan las convenciones
PEP 8 y convenciones BAGO configurables.

Reglas:
    NAME-W001  Función/método no en snake_case
    NAME-W002  Clase no en PascalCase
    NAME-W003  Constante no en UPPER_SNAKE_CASE (si tiene valor literal)
    NAME-W004  Variable con nombre demasiado corto (<3 chars, excepto i/j/k/n/x/y)
    NAME-W005  Módulo (filename) no en snake_case
    NAME-I001  Función con nombre genérico (do, run, process, handle sin sufijo)
    NAME-I002  Clase con nombre genérico (Manager, Helper, Utils sin prefijo)

Uso:
    bago naming-check [FILE|DIR] [--format text|md|json] [--out FILE]
                      [--ignore RULE,...] [--test]
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

_GRN  = "\033[0;32m"
_YEL  = "\033[0;33m"
_CYN  = "\033[0;36m"
_RST  = "\033[0m"
_BOLD = "\033[1m"

SKIP_DIRS = {"__pycache__", ".git", "venv", ".venv", "node_modules"}

SNAKE_RE   = re.compile(r"^[a-z][a-z0-9_]*$")
PASCAL_RE  = re.compile(r"^[A-Z][a-zA-Z0-9]*$")
UPPER_RE   = re.compile(r"^[A-Z][A-Z0-9_]*$")
SHORT_OK   = {"i", "j", "k", "n", "x", "y", "e", "f", "v", "k", "s", "_"}

GENERIC_FUNCS   = {"do", "run", "process", "handle", "execute", "perform", "go"}
GENERIC_CLASSES = {"Manager", "Helper", "Utils", "Util", "Handler", "Processor",
                   "Executor", "Worker", "Service"}


def _is_snake(name: str) -> bool:
    return bool(SNAKE_RE.match(name))


def _is_pascal(name: str) -> bool:
    return bool(PASCAL_RE.match(name))


def _is_upper_snake(name: str) -> bool:
    return bool(UPPER_RE.match(name))


def analyze_file(filepath: str, ignore: set[str]) -> list[dict]:
    findings: list[dict] = []

    # NAME-W005 — módulo filename
    stem = Path(filepath).stem
    if "NAME-W005" not in ignore and not _is_snake(stem) and not stem.startswith("_"):
        findings.append({
            "rule": "NAME-W005", "severity": "warning",
            "file": filepath, "line": 0,
            "name": stem,
            "message": f"Módulo '{stem}' no está en snake_case",
        })

    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="ignore")
        tree   = ast.parse(source, filename=filepath)
    except Exception:
        return findings

    for node in ast.walk(tree):
        # NAME-W002 — clases
        if isinstance(node, ast.ClassDef):
            if "NAME-W002" not in ignore and not _is_pascal(node.name):
                findings.append({
                    "rule": "NAME-W002", "severity": "warning",
                    "file": filepath, "line": node.lineno,
                    "name": node.name,
                    "message": f"Clase '{node.name}' no está en PascalCase",
                })
            if "NAME-I002" not in ignore and node.name in GENERIC_CLASSES:
                findings.append({
                    "rule": "NAME-I002", "severity": "info",
                    "file": filepath, "line": node.lineno,
                    "name": node.name,
                    "message": f"Clase '{node.name}' tiene nombre genérico — añade prefijo descriptivo",
                })

        # NAME-W001 — funciones/métodos
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            if name.startswith("__") and name.endswith("__"):
                continue
            if "NAME-W001" not in ignore and not _is_snake(name):
                findings.append({
                    "rule": "NAME-W001", "severity": "warning",
                    "file": filepath, "line": node.lineno,
                    "name": name,
                    "message": f"Función '{name}' no está en snake_case",
                })
            if "NAME-I001" not in ignore and name in GENERIC_FUNCS:
                findings.append({
                    "rule": "NAME-I001", "severity": "info",
                    "file": filepath, "line": node.lineno,
                    "name": name,
                    "message": f"Función '{name}' tiene nombre genérico — sé más específico",
                })

        # NAME-W003 — constantes (asignaciones en módulo/clase con valor literal)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                vname = target.id
                if vname.startswith("_"):
                    continue
                if "NAME-W003" not in ignore:
                    val = node.value
                    is_literal = isinstance(val, (ast.Constant, ast.List, ast.Tuple, ast.Dict))
                    looks_const = vname.upper() == vname and "_" in vname or len(vname) > 2 and vname.isupper()
                    if is_literal and looks_const and not _is_upper_snake(vname):
                        findings.append({
                            "rule": "NAME-W003", "severity": "warning",
                            "file": filepath, "line": node.lineno,
                            "name": vname,
                            "message": f"Constante aparente '{vname}' no está en UPPER_SNAKE_CASE",
                        })

                # NAME-W004 — nombres cortos
                if "NAME-W004" not in ignore:
                    if len(vname) < 3 and vname.lower() not in SHORT_OK:
                        findings.append({
                            "rule": "NAME-W004", "severity": "warning",
                            "file": filepath, "line": node.lineno,
                            "name": vname,
                            "message": f"Variable '{vname}' demasiado corta — usa un nombre descriptivo",
                        })

    return findings


def analyze_directory(directory: str, ignore: set[str]) -> list[dict]:
    all_findings: list[dict] = []
    for py_file in sorted(Path(directory).rglob("*.py")):
        if any(d in py_file.parts for d in SKIP_DIRS):
            continue
        all_findings.extend(analyze_file(str(py_file), ignore))
    return all_findings


def generate_text(findings: list[dict]) -> str:
    if not findings:
        return f"{_GRN}✅ Convenciones de nombres correctas{_RST}"
    lines = [f"{_BOLD}Naming Check — {len(findings)} hallazgo(s){_RST}", ""]
    for f in findings:
        color = _YEL if f["severity"] == "warning" else _CYN
        lines.append(
            f"  {color}[{f['rule']}]{_RST} {Path(f['file']).name}:{f['line']}  {f['message']}"
        )
    return "\n".join(lines)


def generate_markdown(findings: list[dict]) -> str:
    if not findings:
        return "# Naming Check\n\n✅ Todas las convenciones correctas.\n"
    lines = [
        f"# Naming Check — {len(findings)} hallazgo(s)",
        "",
        "| Regla | Archivo | Línea | Mensaje |",
        "|-------|---------|-------|---------|",
    ]
    for f in findings:
        lines.append(
            f"| `{f['rule']}` | `{Path(f['file']).name}` | {f['line']} | {f['message']} |"
        )
    lines += ["", "---", "*Generado con `bago naming-check`*"]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    target   = "./"
    fmt      = "text"
    out_file = None
    ignore: set[str] = set()

    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--format" and i + 1 < len(argv):
            fmt = argv[i + 1]; i += 2
        elif a == "--out" and i + 1 < len(argv):
            out_file = argv[i + 1]; i += 2
        elif a == "--ignore" and i + 1 < len(argv):
            ignore = set(argv[i + 1].split(",")); i += 2
        elif not a.startswith("--"):
            target = a; i += 1
        else:
            i += 1

    target_path = Path(target)
    if not target_path.exists():
        print(f"No existe: {target}", file=sys.stderr); return 1

    if target_path.is_file():
        findings = analyze_file(target, ignore)
    else:
        findings = analyze_directory(target, ignore)

    if fmt == "json":
        content = json.dumps(findings, indent=2)
    elif fmt == "md":
        content = generate_markdown(findings)
    else:
        content = generate_text(findings)

    if out_file:
        Path(out_file).write_text(content, encoding="utf-8")
        print(f"Guardado: {out_file}", file=sys.stderr)
    else:
        print(content)
    return 0


def _self_test() -> None:
    import tempfile
    print("Tests de naming_check.py...")
    fails: list[str] = []
    def ok(n): print(f"  OK: {n}")
    def fail(n, m): fails.append(n); print(f"  FAIL: {n}: {m}")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        # T1 — función camelCase → NAME-W001
        (root / "bad_names.py").write_text(
            'def getUsers():\n    pass\n'
        )
        f1 = analyze_file(str(root / "bad_names.py"), set())
        w001 = [f for f in f1 if f["rule"] == "NAME-W001"]
        if w001:
            ok("naming_check:camelcase_function")
        else:
            fail("naming_check:camelcase_function", f"findings={f1}")

        # T2 — clase snake_case → NAME-W002
        (root / "bad_class.py").write_text(
            'class my_service:\n    pass\n'
        )
        f2 = analyze_file(str(root / "bad_class.py"), set())
        w002 = [f for f in f2 if f["rule"] == "NAME-W002"]
        if w002:
            ok("naming_check:snake_class")
        else:
            fail("naming_check:snake_class", f"findings={f2}")

        # T3 — archivo bien nombrado, funciones bien nombradas → sin warnings
        (root / "clean_module.py").write_text(
            'def get_users():\n    pass\n\nclass UserService:\n    pass\n'
        )
        f3 = analyze_file(str(root / "clean_module.py"), set())
        bad = [f for f in f3 if f["rule"] in {"NAME-W001", "NAME-W002"}]
        if not bad:
            ok("naming_check:clean_no_warnings")
        else:
            fail("naming_check:clean_no_warnings", f"unexpected={bad}")

        # T4 — nombre genérico de clase → NAME-I002
        (root / "generic.py").write_text('class Manager:\n    pass\n')
        f4 = analyze_file(str(root / "generic.py"), set())
        i002 = [f for f in f4 if f["rule"] == "NAME-I002"]
        if i002:
            ok("naming_check:generic_class_name")
        else:
            fail("naming_check:generic_class_name", f"findings={f4}")

        # T5 — ignore NAME-I002 suprime el warning
        f5 = analyze_file(str(root / "generic.py"), {"NAME-I002"})
        i002_ignored = [f for f in f5 if f["rule"] == "NAME-I002"]
        if not i002_ignored:
            ok("naming_check:ignore_rule")
        else:
            fail("naming_check:ignore_rule", f"still found={i002_ignored}")

        # T6 — markdown generado
        md = generate_markdown(w001)
        if "Naming Check" in md and "NAME-W001" in md:
            ok("naming_check:markdown_output")
        else:
            fail("naming_check:markdown_output", md[:80])

    total = 6; passed = total - len(fails)
    print(f"\n  {passed}/{total} tests pasaron")
    if fails: raise SystemExit(1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
    else:
        raise SystemExit(main(sys.argv[1:]))
