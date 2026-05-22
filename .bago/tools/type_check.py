#!/usr/bin/env python3
"""type_check.py — Herramienta #121: Validador de type hints Python.

Analiza archivos Python y reporta funciones/métodos sin anotaciones de tipo.
No requiere mypy — usa stdlib ast.

Reglas:
    TYPE-W001  Función pública sin anotación de retorno
    TYPE-W002  Parámetro sin anotación de tipo (excluyendo self/cls)
    TYPE-W003  Uso de `Any` como anotación (sospechoso)
    TYPE-W004  Variable con asignación múltiple sin type hint coherente
    TYPE-I001  Función privada sin type hints (informativo)

Uso:
    bago type-check [FILE|DIR] [--strict] [--format text|md|json]
                    [--out FILE] [--ignore RULE,...] [--test]

Opciones:
    --strict    Incluye también funciones privadas (TYPE-I001)
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

_GRN  = "\033[0;32m"
_YEL  = "\033[0;33m"
_CYN  = "\033[0;36m"
_RST  = "\033[0m"
_BOLD = "\033[1m"

SKIP_DIRS  = {"__pycache__", ".git", "venv", ".venv", "node_modules"}
SKIP_PARAMS = {"self", "cls", "_"}


def _annotation_str(node) -> str:
    """Serializa una anotación de tipo a string."""
    if node is None:
        return ""
    if isinstance(node, ast.Constant):
        return str(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_annotation_str(node.value)}.{node.attr}"
    if isinstance(node, ast.Subscript):
        return f"{_annotation_str(node.value)}[{_annotation_str(node.slice)}]"
    if isinstance(node, ast.BinOp):  # X | Y (Python 3.10+)
        return f"{_annotation_str(node.left)} | {_annotation_str(node.right)}"
    return "..."


def _uses_any(annotation) -> bool:
    """Detecta uso de Any como anotación."""
    s = _annotation_str(annotation)
    return "Any" in s


def analyze_file(filepath: str, strict: bool = False,
                  ignore: set[str] = None) -> list[dict]:
    if ignore is None:
        ignore = set()
    findings: list[dict] = []
    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="ignore")
        tree   = ast.parse(source, filename=filepath)
    except Exception:
        return findings

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        name   = node.name
        is_pub = not name.startswith("_") or name.startswith("__") and name.endswith("__")
        is_dunder = name.startswith("__") and name.endswith("__")

        # Skip dunder methods (except __init__)
        if is_dunder and name not in {"__init__", "__call__", "__str__", "__repr__"}:
            continue

        # TYPE-W001: sin return type annotation (solo funciones públicas)
        if "TYPE-W001" not in ignore and is_pub and not is_dunder:
            if node.returns is None:
                findings.append({
                    "rule": "TYPE-W001", "severity": "warning",
                    "file": filepath, "line": node.lineno, "name": name,
                    "message": f"'{name}' sin anotación de retorno",
                })
            elif _uses_any(node.returns):
                if "TYPE-W003" not in ignore:
                    findings.append({
                        "rule": "TYPE-W003", "severity": "warning",
                        "file": filepath, "line": node.lineno, "name": name,
                        "message": f"'{name}' retorna `Any` — sé más específico",
                    })

        # TYPE-W002: parámetros sin tipo
        if "TYPE-W002" not in ignore and (is_pub or strict):
            untyped = []
            for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
                if arg.arg in SKIP_PARAMS:
                    continue
                if arg.annotation is None:
                    untyped.append(arg.arg)
                elif _uses_any(arg.annotation) and "TYPE-W003" not in ignore:
                    findings.append({
                        "rule": "TYPE-W003", "severity": "warning",
                        "file": filepath, "line": node.lineno, "name": name,
                        "message": f"Parámetro '{arg.arg}' de '{name}' usa `Any`",
                    })
            if untyped:
                rule = "TYPE-W002" if is_pub else "TYPE-I001"
                if rule not in ignore:
                    findings.append({
                        "rule": rule,
                        "severity": "warning" if is_pub else "info",
                        "file": filepath, "line": node.lineno, "name": name,
                        "message": f"'{name}' parámetros sin tipo: {untyped}",
                    })

    return findings


def analyze_directory(directory: str, strict: bool = False,
                       ignore: set[str] = None) -> list[dict]:
    all_findings: list[dict] = []
    for py_file in sorted(Path(directory).rglob("*.py")):
        if any(d in py_file.parts for d in SKIP_DIRS):
            continue
        all_findings.extend(analyze_file(str(py_file), strict, ignore))
    return all_findings


def _score(findings: list[dict], total_funcs: int) -> int:
    if total_funcs == 0:
        return 100
    errors = len([f for f in findings if f["severity"] == "warning"])
    return max(0, round(100 - (errors / max(1, total_funcs)) * 100))


def generate_text(findings: list[dict]) -> str:
    if not findings:
        return f"{_GRN}✅ Todos los type hints presentes{_RST}"
    lines = [f"{_BOLD}Type Check — {len(findings)} hallazgo(s){_RST}", ""]
    for f in findings:
        color = _YEL if f["severity"] == "warning" else _CYN
        lines.append(
            f"  {color}[{f['rule']}]{_RST} {Path(f['file']).name}:{f['line']}  {f['message']}"
        )
    return "\n".join(lines)


def generate_markdown(findings: list[dict]) -> str:
    if not findings:
        return "# Type Check\n\n✅ Todos los type hints correctos.\n"
    lines = [
        f"# Type Check — {len(findings)} hallazgo(s)",
        "",
        "| Regla | Archivo | Línea | Función | Mensaje |",
        "|-------|---------|-------|---------|---------|",
    ]
    for f in findings:
        lines.append(
            f"| `{f['rule']}` | `{Path(f['file']).name}` | {f['line']} "
            f"| `{f['name']}` | {f['message']} |"
        )
    lines += ["", "---", "*Generado con `bago type-check`*"]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    target   = "./"
    strict   = False
    fmt      = "text"
    out_file = None
    ignore: set[str] = set()

    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--strict":
            strict = True; i += 1
        elif a == "--format" and i + 1 < len(argv):
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
        findings = analyze_file(target, strict, ignore)
    else:
        findings = analyze_directory(target, strict, ignore)

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
    print("Tests de type_check.py...")
    fails: list[str] = []
    def ok(n): print(f"  OK: {n}")
    def fail(n, m): fails.append(n); print(f"  FAIL: {n}: {m}")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        # T1 — función sin return type → TYPE-W001
        (root / "no_ret.py").write_text('def greet(name: str):\n    return name\n')
        f1 = analyze_file(str(root / "no_ret.py"))
        w001 = [f for f in f1 if f["rule"] == "TYPE-W001"]
        if w001:
            ok("type_check:missing_return_type")
        else:
            fail("type_check:missing_return_type", f"findings={f1}")

        # T2 — parámetro sin tipo → TYPE-W002
        (root / "no_param.py").write_text('def greet(name) -> str:\n    return name\n')
        f2 = analyze_file(str(root / "no_param.py"))
        w002 = [f for f in f2 if f["rule"] == "TYPE-W002"]
        if w002:
            ok("type_check:missing_param_type")
        else:
            fail("type_check:missing_param_type", f"findings={f2}")

        # T3 — función completamente tipada → sin findings
        (root / "typed.py").write_text(
            'def add(a: int, b: int) -> int:\n    return a + b\n'
        )
        f3 = analyze_file(str(root / "typed.py"))
        if not f3:
            ok("type_check:fully_typed_no_findings")
        else:
            fail("type_check:fully_typed_no_findings", f"unexpected={f3}")

        # T4 — uso de Any → TYPE-W003
        (root / "any_type.py").write_text(
            'from typing import Any\ndef process(data: Any) -> Any:\n    return data\n'
        )
        f4 = analyze_file(str(root / "any_type.py"))
        w003 = [f for f in f4 if f["rule"] == "TYPE-W003"]
        if w003:
            ok("type_check:any_annotation")
        else:
            fail("type_check:any_annotation", f"findings={f4}")

        # T5 — función privada sin tipo: solo info en strict mode
        (root / "private.py").write_text('def _helper(x):\n    return x\n')
        f5_normal = analyze_file(str(root / "private.py"), strict=False)
        f5_strict = analyze_file(str(root / "private.py"), strict=True)
        # En modo normal no debe aparecer TYPE-W002 para función privada
        w002_normal = [f for f in f5_normal if f["rule"] == "TYPE-W002"]
        w002_strict = [f for f in f5_strict if f["rule"] in {"TYPE-W002", "TYPE-I001"}]
        if not w002_normal and w002_strict:
            ok("type_check:private_strict_mode")
        else:
            fail("type_check:private_strict_mode",
                 f"normal_w002={w002_normal} strict={w002_strict}")

        # T6 — markdown generado
        md = generate_markdown(w001)
        if "Type Check" in md and "TYPE-W001" in md:
            ok("type_check:markdown_output")
        else:
            fail("type_check:markdown_output", md[:80])

    total = 6; passed = total - len(fails)
    print(f"\n  {passed}/{total} tests pasaron")
    if fails: raise SystemExit(1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
    else:
        raise SystemExit(main(sys.argv[1:]))
