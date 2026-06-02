#!/usr/bin/env python3
"""BAGO modular guard -- detecta violaciones de las reglas de modularizacion.

Reglas aplicadas (ver plan.md, "Reglas de modularizacion BAGO"):
    R0  Una responsabilidad por archivo
    R1  Diccionario de capas
    R2  Grafo de imports
    R3  Tamano maximo (archivo ≤900, funcion ≤80)
    R4  Helpers prohibidos dentro de funciones grandes
    R5  SSoT (Single Source of Truth)
    R6  Este script es el detector (se ejecuta en `bago node validate`)
    R7  Naming convention de dispatch
    R8  Render nunca dentro de dispatch
    R9  Backwards compatibility CLI
    R10 Cobertura de tests

Uso:
    python tools/check_modular.py            # exit 0 si todo OK
    python tools/check_modular.py --json     # salida JSON
    python tools/check_modular.py --verbose  # imprime detalles
    python tools/check_modular.py --rule R5  # filtrar por regla
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = REPO_ROOT / "bago_core"

# Limites duros
MAX_FILE_LINES = 900
MAX_FILE_LINES_TARGET = 600
MAX_FUNC_LINES = 80

# Mapeo de archivos a capa (R1)
LAYER_MAP: dict[str, str] = {
    "node_control_ssot.py": "ssot",
    "node_control_store.py": "store",
    "node_control_policy.py": "policy",
    "node_control_render.py": "render",
    "node_control_tui.py": "tui",
    "node_control_translator.py": "dispatch",
    "node_control.py": "facade",
    "parsers.py": "parsers",
    "parsers_sections.py": "parsers",
}

# Funciones canonicas por capa (R1)
LAYER_FUNCTIONS: dict[str, set[str]] = {
    "ssot": set(),
    "store": {
        "load_registry", "save_registry", "load_policy", "save_policy",
        "load_evidence", "append_evidence", "load_compatibility",
    },
    "policy": {
        "can_execute", "can_modify", "can_audit", "decide_connector_mode",
    },
    "render": {
        "render_text", "render_pieces", "render_connectors", "render_matrix",
    },
    "tui": {
        "interactive_tui", "run_tui", "tui_main",
    },
    "dispatch": {
        "run_translator", "run_evidence", "run_matrix",
    },
    "facade": {
        "main",
    },
    "parsers": set(),
}

# Imports prohibidos entre capas (R2)
FORBIDDEN_IMPORTS: dict[str, set[str]] = {
    "ssot": {"bago_core.node_control_store",
             "bago_core.node_control_tui", "bago_core.node_control_render",
             "bago_core.node_control_translator"},
    "store": {"bago_core.node_control_render", "bago_core.node_control_tui",
              "bago_core.node_control_translator"},
    "policy": {"bago_core.node_control_render", "bago_core.node_control_tui"},
    "render": {"bago_core.node_control_store",
               "bago_core.node_control_tui"},
    "tui": {"bago_core.parsers"},
    "dispatch": {"bago_core.parsers", "bago_core.parsers_sections"},
    "parsers": {"bago_core.node_control", "bago_core.node_control_translator",
                "bago_core.translators"},
    "facade": set(),
}

# Patrones SSoT inminentes
SSOT_STRING_PATTERNS = [
    r"^DEFAULT_[A-Z_]+$",
    r"^CLI_[A-Z_]+$",
    r"^ALLOWED_[A-Z_]+$",
    r"^PIECE_[A-Z_]+$",
    r"^EVIDENCE_[A-Z_]+$",
]

def find_python_files() -> list[Path]:
    files = []
    for path in CORE_DIR.glob("*.py"):
        if path.name == "__init__.py":
            continue
        files.append(path)
    return sorted(files)

def file_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)

def get_layer(path: Path) -> str | None:
    return LAYER_MAP.get(path.name)

def parse_file(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8", errors="replace"))

def collect_functions(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    funcs = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append(node)
    return funcs

def func_line_count(func: ast.FunctionDef) -> int:
    if not func.body:
        return 0
    last = max(
        (getattr(n, "end_lineno", getattr(n, "lineno", 0)) for n in ast.walk(func)),
        default=0,
    )
    first = func.lineno
    return max(0, last - first + 1)

def get_imports(tree: ast.Module) -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports

def get_string_constants(tree: ast.Module) -> list[tuple[str, str]]:
    out = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and any(
                    re.match(pat, target.id) for pat in SSOT_STRING_PATTERNS
                ):
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        out.append((target.id, node.value.value))
    return out

def check_r3_size() -> list[dict]:
    findings = []
    for path in find_python_files():
        lines = file_lines(path)
        if lines > MAX_FILE_LINES:
            findings.append({
                "rule": "R3",
                "severity": "ERROR",
                "file": str(path.relative_to(REPO_ROOT)),
                "message": f"Archivo excede {MAX_FILE_LINES} lineas ({lines})",
                "lines": lines,
            })
        elif lines > MAX_FILE_LINES_TARGET:
            findings.append({
                "rule": "R3",
                "severity": "WARN",
                "file": str(path.relative_to(REPO_ROOT)),
                "message": f"Archivo excede objetivo de {MAX_FILE_LINES_TARGET} lineas ({lines})",
                "lines": lines,
            })
        try:
            tree = parse_file(path)
        except SyntaxError as e:
            findings.append({
                "rule": "R3",
                "severity": "ERROR",
                "file": str(path.relative_to(REPO_ROOT)),
                "message": f"SyntaxError: {e}",
            })
            continue
        for func in collect_functions(tree):
            fcount = func_line_count(func)
            if fcount > MAX_FUNC_LINES:
                findings.append({
                    "rule": "R3",
                    "severity": "WARN",
                    "file": str(path.relative_to(REPO_ROOT)),
                    "message": f"Funcion '{func.name}' tiene {fcount} lineas (>{MAX_FUNC_LINES})",
                    "function": func.name,
                    "lines": fcount,
                })
    return findings

def check_r1_layer_functions() -> list[dict]:
    findings = []
    for path in find_python_files():
        layer = get_layer(path)
        if not layer:
            continue
        try:
            tree = parse_file(path)
        except SyntaxError:
            continue
        for func in collect_functions(tree):
            other_layers = [
                other_layer
                for other_layer, funcs in LAYER_FUNCTIONS.items()
                if other_layer != layer and func.name in funcs
            ]
            if other_layers:
                findings.append({
                    "rule": "R1",
                    "severity": "WARN",
                    "file": str(path.relative_to(REPO_ROOT)),
                    "message": (
                        f"Funcion '{func.name}' se considera de capa {other_layers} "
                        f"pero esta en {layer} ({path.name})"
                    ),
                    "function": func.name,
                    "expected_layers": other_layers,
                    "actual_layer": layer,
                })
    return findings

def check_r2_imports() -> list[dict]:
    findings = []
    for path in find_python_files():
        layer = get_layer(path)
        if not layer:
            continue
        forbidden = FORBIDDEN_IMPORTS.get(layer, set())
        if not forbidden:
            continue
        try:
            tree = parse_file(path)
        except SyntaxError:
            continue
        for imp in get_imports(tree):
            for f in forbidden:
                if imp == f or imp.startswith(f + "."):
                    findings.append({
                        "rule": "R2",
                        "severity": "ERROR",
                        "file": str(path.relative_to(REPO_ROOT)),
                        "message": f"Import prohibido '{imp}' en capa {layer} ({path.name})",
                        "forbidden": f,
                    })
    return findings

def check_r5_ssot() -> tuple[list[dict], list[dict]]:
    imminent: list[dict] = []
    future: list[dict] = []

    const_map: dict[str, list[tuple[Path, str]]] = defaultdict(list)
    for path in find_python_files():
        try:
            tree = parse_file(path)
        except SyntaxError:
            continue
        for name, value in get_string_constants(tree):
            const_map[name].append((path, value))

    for name, occurrences in const_map.items():
        if len(occurrences) >= 2:
            imminent.append({
                "rule": "R5",
                "severity": "WARN",
                "kind": "constant",
                "name": name,
                "files": [str(p.relative_to(REPO_ROOT)) for p, _ in occurrences],
                "message": f"Constante '{name}' definida en {len(occurrences)} archivos - mover a ssot",
            })

    sig_map: dict[str, list[Path]] = defaultdict(list)
    for path in find_python_files():
        try:
            tree = parse_file(path)
        except SyntaxError:
            continue
        for func in collect_functions(tree):
            if not func.body or func.name.startswith("_"):
                continue
            args = [a.arg for a in func.args.args]
            sig = f"{func.name}({', '.join(args)})"
            sig_map[sig].append(path)

    for sig, paths in sig_map.items():
        if len(paths) >= 2:
            future.append({
                "rule": "R5",
                "severity": "WARN",
                "kind": "function",
                "signature": sig,
                "files": [str(p.relative_to(REPO_ROOT)) for p in paths],
                "message": f"Firma {sig} aparece en {len(paths)} archivos - candidato a SSoT",
            })
    return imminent, future

def check_r4_long_helpers() -> list[dict]:
    findings = []
    for path in find_python_files():
        try:
            tree = parse_file(path)
        except SyntaxError:
            continue
        for func in collect_functions(tree):
            fcount = func_line_count(func)
            if fcount < 40:
                continue
            comments = sum(
                1 for n in ast.walk(func)
                if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
                and isinstance(n.value.value, str) and n.value.value.startswith("#")
            )
            if comments >= 2:
                findings.append({
                    "rule": "R4",
                    "severity": "INFO",
                    "file": str(path.relative_to(REPO_ROOT)),
                    "function": func.name,
                    "lines": fcount,
                    "message": (
                        f"Funcion '{func.name}' ({fcount} lineas) tiene {comments} "
                        f"comentarios-bloque - candidata a extraer helpers"
                    ),
                })
    return findings

def check_r7_naming() -> list[dict]:
    findings = []
    for path in find_python_files():
        if path.name.startswith("node_control_") and path.name not in LAYER_MAP:
            try:
                tree = parse_file(path)
            except SyntaxError:
                continue
            run_funcs = [
                f.name for f in collect_functions(tree) if f.name.startswith("run_")
            ]
            if run_funcs:
                findings.append({
                    "rule": "R7",
                    "severity": "INFO",
                    "file": str(path.relative_to(REPO_ROOT)),
                    "message": f"'{path.name}' no esta en LAYER_MAP pero tiene {run_funcs}",
                })
    return findings

def check_r8_render_in_dispatch() -> list[dict]:
    findings = []
    for path in find_python_files():
        layer = get_layer(path)
        if layer != "dispatch":
            continue
        try:
            tree = parse_file(path)
        except SyntaxError:
            continue
        for func in collect_functions(tree):
            for node in ast.walk(func):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == "print":
                        findings.append({
                            "rule": "R8",
                            "severity": "WARN",
                            "file": str(path.relative_to(REPO_ROOT)),
                            "function": func.name,
                            "line": node.lineno,
                            "message": (
                                f"Dispatch '{func.name}' contiene print() directo "
                                f"en linea {node.lineno} - deberia usar render"
                            ),
                        })
    return findings

def check_r10_test_coverage() -> list[dict]:
    findings = []
    tests_dir = REPO_ROOT / "tests"
    if not tests_dir.exists():
        findings.append({
            "rule": "R10",
            "severity": "WARN",
            "message": "Directorio tests/ no existe",
        })
        return findings
    existing_tests = {p.stem for p in tests_dir.glob("test_*.py")}
    existing_tests_split = {p.stem for p in tests_dir.glob("test_*_split.py")}
    for path in find_python_files():
        if not path.name.startswith("node_control_"):
            continue
        if path.name == "node_control.py":
            continue
        expected = f"test_{path.stem}"
        # Accept either test_<name>.py or test_<name>_split.py (canonical
        # name for FASE 6+ module-split tests).
        if expected not in existing_tests and expected not in existing_tests_split:
            findings.append({
                "rule": "R10",
                "severity": "INFO",
                "file": str(path.relative_to(REPO_ROOT)),
                "message": f"Falta test {expected}.py",
            })
    return findings

def run_all() -> dict:
    findings_r3 = check_r3_size()
    findings_r1 = check_r1_layer_functions()
    findings_r2 = check_r2_imports()
    findings_ssot_imminent, findings_ssot_future = check_r5_ssot()
    findings_r4 = check_r4_long_helpers()
    findings_r7 = check_r7_naming()
    findings_r8 = check_r8_render_in_dispatch()
    findings_r10 = check_r10_test_coverage()

    all_findings = (
        findings_r3 + findings_r1 + findings_r2
        + findings_ssot_imminent + findings_ssot_future
        + findings_r4 + findings_r7 + findings_r8 + findings_r10
    )
    by_severity: dict[str, int] = defaultdict(int)
    for f in all_findings:
        by_severity[f.get("severity", "INFO")] += 1

    return {
        "ok": all(f.get("severity") != "ERROR" for f in all_findings),
        "totals": dict(by_severity),
        "findings": all_findings,
        "by_rule": {
            "R1_layer_functions": findings_r1,
            "R2_imports": findings_r2,
            "R3_size": findings_r3,
            "R4_long_helpers": findings_r4,
            "R5_ssot_imminent": findings_ssot_imminent,
            "R5_ssot_future": findings_ssot_future,
            "R7_naming": findings_r7,
            "R8_render_in_dispatch": findings_r8,
            "R10_test_coverage": findings_r10,
        },
    }

def main() -> int:
    parser = argparse.ArgumentParser(description="BAGO modular guard")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Detalles")
    parser.add_argument("--rule", help="Filtrar por regla (R1, R2, ...)")
    args = parser.parse_args()

    report = run_all()

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["ok"] else 1

    if args.verbose or not report["ok"]:
        print("=" * 72)
        print("BAGO MODULAR GUARD")
        print("=" * 72)
        print(f"Repo:    {REPO_ROOT}")
        print(f"Capas:   {len(LAYER_MAP)} archivos con capa asignada")
        print()
        for rule_key, findings in report["by_rule"].items():
            if args.rule and not rule_key.startswith(args.rule):
                continue
            if not findings:
                print(f"[OK ] {rule_key}")
                continue
            print(f"[{len(findings):2d}] {rule_key}")
            for f in findings[:5]:
                sev = f.get("severity", "INFO")
                msg = f.get("message", "")
                file = f.get("file", "")
                print(f"     {sev:5s} {file}  {msg}")
            if len(findings) > 5:
                print(f"     ... y {len(findings) - 5} mas")
            print()

        print("=" * 72)
        print("RESUMEN")
        for sev, n in report["totals"].items():
            print(f"  {sev:5s} {n}")
        if report["ok"]:
            print("\n[OK] No se detectaron errores de modularizacion")
        else:
            print("\n[FAIL] Hay errores que corregir")
        return 0 if report["ok"] else 1

    if report["ok"]:
        total = sum(report["totals"].values())
        print(f"OK - {total} advertencias, 0 errores")
        return 0
    print(f"FAIL - {report['totals'].get('ERROR', 0)} errores")
    return 1

if __name__ == "__main__":
    sys.exit(main())
