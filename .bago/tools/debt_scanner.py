#!/usr/bin/env python3
"""
debt_scanner.py — BAGO Sonda de Deuda Técnica Invisible

Detecta patrones que generan deuda silenciosa en proyectos Python/CLI.
No falla builds, no modifica código. Solo informa con severidad y remedio.

Patrones detectados:
  D01  Parsers argparse anónimos (no asignados a variable)
  D02  Archivos demasiado grandes (>400 LOC)
  D03  Funciones demasiado largas (>60 líneas)
  D04  Funciones con demasiados parámetros (>6)
  D05  Rutas absolutas hardcodeadas en código
  D06  Swallow de excepciones silencioso (except ... pass / ...)
  D07  Imports wildcard (from X import *)
  D08  sys.path.insert hacks en código no-test
  D09  Funciones públicas sin type hints
  D10  Duplicados de nombre de función entre módulos

CLI:
  python debt_scanner.py [--root DIR] [--severity error|warning|info] [--json] [--test]
  bago scan debt [--root DIR] [--severity ...] [--json]
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterator

# ── portabilidad ──────────────────────────────────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))
try:
    from bago_utils import get_scan_root
except ImportError:
    def get_scan_root(override=None):
        return Path(override) if override else Path(os.environ.get("BAGO_SCAN_ROOT", os.getcwd()))

SCANNER_VERSION = "1.0.0"

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}

_SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "node_modules",
    "dist", "build", ".bago", "site-packages",
}


# ══════════════════════════════════════════════════════════════════════════════
#  MODELO DE DATOS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Finding:
    code: str          # D01 … D10
    severity: str      # error / warning / info
    file: str
    line: int
    message: str
    remedy: str

    def __str__(self) -> str:
        sev = self.severity.upper()[:4]
        return f"  [{sev}] {self.code}  {self.file}:{self.line}  {self.message}"


@dataclass
class DebtReport:
    root: str
    findings: list[Finding] = field(default_factory=list)
    scanner_version: str = SCANNER_VERSION

    @property
    def score(self) -> int:
        """Puntuación de deuda (mayor = más deuda)."""
        weights = {"error": 10, "warning": 3, "info": 1}
        return sum(weights.get(f.severity, 1) for f in self.findings)

    def summary(self) -> dict:
        by_sev: dict[str, int] = {"error": 0, "warning": 0, "info": 0}
        by_code: dict[str, int] = defaultdict(int)
        for f in self.findings:
            by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
            by_code[f.code] += 1
        return {
            "total": len(self.findings),
            "score": self.score,
            "by_severity": by_sev,
            "by_code": dict(by_code),
        }

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "scanner_version": self.scanner_version,
            "summary": self.summary(),
            "findings": [asdict(f) for f in self.findings],
        }


# ══════════════════════════════════════════════════════════════════════════════
#  UTILIDADES
# ══════════════════════════════════════════════════════════════════════════════

def _python_files(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fname in filenames:
            if fname.endswith(".py"):
                yield Path(dirpath) / fname


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def _parse_ast(src: str) -> ast.Module | None:
    try:
        return ast.parse(src)
    except SyntaxError:
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  DETECTORES
# ══════════════════════════════════════════════════════════════════════════════

def detect_anonymous_parsers(path: Path, src: str, root: Path) -> list[Finding]:
    """D01 — add_parser() sin asignar a variable."""
    findings = []
    # Regex: línea que llama .add_parser( pero NO comienza con "var = "
    pattern = re.compile(
        r"""^[ \t]*(?!\w+\s*=)   # no hay asignación al inicio
            (?:\w+\.)+add_parser\(  # algún_obj.add_parser(
        """,
        re.VERBOSE | re.MULTILINE,
    )
    for m in pattern.finditer(src):
        lineno = src[: m.start()].count("\n") + 1
        findings.append(Finding(
            code="D01", severity="warning",
            file=_rel(path, root), line=lineno,
            message="add_parser() sin asignar — parser sellado, no extensible",
            remedy="Capturar: `my_parser = sub.add_parser(...)`",
        ))
    return findings


def detect_large_files(path: Path, src: str, root: Path) -> list[Finding]:
    """D02 — Archivos demasiado grandes."""
    lines = src.count("\n") + 1
    if lines > 600:
        sev, msg = "error",   f"{lines} líneas — candidato a split urgente"
    elif lines > 400:
        sev, msg = "warning", f"{lines} líneas — considerar dividir en módulos"
    else:
        return []
    return [Finding(
        code="D02", severity=sev,
        file=_rel(path, root), line=1,
        message=msg,
        remedy="Extraer responsabilidades a submódulos (como commands/ o parsers.py)",
    )]


def detect_long_functions(path: Path, src: str, root: Path) -> list[Finding]:
    """D03 — Funciones demasiado largas."""
    tree = _parse_ast(src)
    if not tree:
        return []
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end = getattr(node, "end_lineno", node.lineno)
        length = end - node.lineno
        if length > 100:
            sev, msg = "error",   f"`{node.name}` tiene {length} líneas"
        elif length > 60:
            sev, msg = "warning", f"`{node.name}` tiene {length} líneas"
        else:
            continue
        findings.append(Finding(
            code="D03", severity=sev,
            file=_rel(path, root), line=node.lineno,
            message=msg,
            remedy="Extraer subfunciones o mover lógica a helpers",
        ))
    return findings


def detect_many_params(path: Path, src: str, root: Path) -> list[Finding]:
    """D04 — Funciones con demasiados parámetros."""
    tree = _parse_ast(src)
    if not tree:
        return []
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = node.args
        count = len(args.args) + len(args.kwonlyargs) + len(args.posonlyargs)
        if count <= 6:
            continue
        findings.append(Finding(
            code="D04", severity="warning",
            file=_rel(path, root), line=node.lineno,
            message=f"`{node.name}` tiene {count} parámetros",
            remedy="Agrupar parámetros en dataclass/NamedTuple o Config object",
        ))
    return findings


def detect_hardcoded_paths(path: Path, src: str, root: Path) -> list[Finding]:
    """D05 — Rutas absolutas hardcodeadas."""
    findings = []
    # Busca strings con rutas Windows o Unix absolutas (fuera de comentarios)
    pattern = re.compile(
        r"""(?:["'])          # abre comilla
            (
              [A-Za-z]:\\    # Windows C:\...
              | /(?:home|usr|etc|var|opt|root)/  # Unix absolutas comunes
            )
            [^"']{4,}         # al menos 4 chars de ruta
            (?:["'])          # cierra comilla
        """,
        re.VERBOSE,
    )
    lines_src = src.splitlines()
    for lineno, line in enumerate(lines_src, 1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        for m in pattern.finditer(line):
            findings.append(Finding(
                code="D05", severity="warning",
                file=_rel(path, root), line=lineno,
                message=f"Ruta absoluta hardcodeada: {m.group()[:60]}",
                remedy="Usar Path(__file__).parents[N] o variable de entorno",
            ))
    return findings


def detect_silent_exceptions(path: Path, src: str, root: Path) -> list[Finding]:
    """D06 — except ... pass o ellipsis silencioso."""
    tree = _parse_ast(src)
    if not tree:
        return []
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        body = node.body
        if len(body) == 1:
            stmt = body[0]
            if isinstance(stmt, ast.Pass):
                silent = True
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and stmt.value.value is ...:
                silent = True
            else:
                silent = False
            if silent:
                exc_name = getattr(node.type, "id", "Exception") if node.type else "bare"
                findings.append(Finding(
                    code="D06", severity="warning",
                    file=_rel(path, root), line=node.lineno,
                    message=f"Excepción `{exc_name}` tragada en silencio",
                    remedy="Añadir al menos logging.debug o raise desde dentro",
                ))
    return findings


def detect_wildcard_imports(path: Path, src: str, root: Path) -> list[Finding]:
    """D07 — from X import *"""
    findings = []
    pattern = re.compile(r"^\s*from\s+\S+\s+import\s+\*", re.MULTILINE)
    for m in pattern.finditer(src):
        lineno = src[: m.start()].count("\n") + 1
        findings.append(Finding(
            code="D07", severity="warning",
            file=_rel(path, root), line=lineno,
            message="Wildcard import — namespace contaminado, dependencias ocultas",
            remedy="Importar explícitamente los nombres necesarios",
        ))
    return findings


def detect_syspath_hacks(path: Path, src: str, root: Path) -> list[Finding]:
    """D08 — sys.path.insert en código no-test."""
    if "test" in path.name.lower() or "test" in str(path.parent).lower():
        return []
    findings = []
    pattern = re.compile(r"sys\.path\.insert\s*\(", re.MULTILINE)
    for m in pattern.finditer(src):
        lineno = src[: m.start()].count("\n") + 1
        findings.append(Finding(
            code="D08", severity="info",
            file=_rel(path, root), line=lineno,
            message="sys.path.insert hack — frágil ante cambios de estructura",
            remedy="Usar installable package (pyproject.toml) o bago_utils get_scan_root",
        ))
    return findings


def detect_missing_type_hints(path: Path, src: str, root: Path) -> list[Finding]:
    """D09 — Funciones públicas sin return type hint."""
    tree = _parse_ast(src)
    if not tree:
        return []
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue  # privadas OK
        if node.returns is None:
            findings.append(Finding(
                code="D09", severity="info",
                file=_rel(path, root), line=node.lineno,
                message=f"`{node.name}` sin return type hint",
                remedy="Añadir `-> ReturnType:` — facilita IDEs y refactors",
            ))
    return findings


def detect_duplicate_function_names(files_src: dict[Path, str], root: Path) -> list[Finding]:
    """D10 — Mismos nombres de función en múltiples módulos."""
    name_to_files: dict[str, list[tuple[Path, int]]] = defaultdict(list)
    for path, src in files_src.items():
        tree = _parse_ast(src)
        if not tree:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    name_to_files[node.name].append((path, node.lineno))

    findings = []
    for name, locations in name_to_files.items():
        if len(locations) < 2:
            continue
        # Solo reporta si están en módulos distintos (no en misma clase)
        unique_files = {p for p, _ in locations}
        if len(unique_files) < 2:
            continue
        first_path, first_line = locations[0]
        others = ", ".join(f"{_rel(p, root)}:{l}" for p, l in locations[1:3])
        findings.append(Finding(
            code="D10", severity="info",
            file=_rel(first_path, root), line=first_line,
            message=f"`{name}` duplicada también en: {others}",
            remedy="Consolidar en módulo compartido o renombrar para distinguir",
        ))
    return findings


# ══════════════════════════════════════════════════════════════════════════════
#  ORQUESTADOR
# ══════════════════════════════════════════════════════════════════════════════

_PER_FILE_DETECTORS = [
    detect_anonymous_parsers,
    detect_large_files,
    detect_long_functions,
    detect_many_params,
    detect_hardcoded_paths,
    detect_silent_exceptions,
    detect_wildcard_imports,
    detect_syspath_hacks,
    detect_missing_type_hints,
]


def scan(root: Path) -> DebtReport:
    report = DebtReport(root=str(root))
    files_src: dict[Path, str] = {}

    for path in _python_files(root):
        src = _read(path)
        if src is None:
            continue
        files_src[path] = src
        for detector in _PER_FILE_DETECTORS:
            report.findings.extend(detector(path, src, root))

    # Detector multi-archivo
    report.findings.extend(detect_duplicate_function_names(files_src, root))

    # Ordenar: error primero, luego warning, luego info; dentro de cada uno por archivo
    report.findings.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.file, f.line))
    return report


# ══════════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════════

def _print_report(report: DebtReport, min_severity: str = "info") -> None:
    min_order = SEVERITY_ORDER.get(min_severity, 2)
    visible = [f for f in report.findings if SEVERITY_ORDER.get(f.severity, 9) <= min_order]

    summ = report.summary()
    total = summ["by_severity"]
    print(f"\n{'─'*60}")
    print(f"  BAGO Debt Scanner v{report.scanner_version}  —  {report.root}")
    print(f"{'─'*60}")
    print(f"  Hallazgos: {summ['total']}  "
          f"(🔴 {total['error']} error  🟡 {total['warning']} warning  ⚪ {total['info']} info)")
    print(f"  Puntuación de deuda: {report.score}")
    print(f"{'─'*60}\n")

    if not visible:
        print("  ✅ Sin deuda técnica detectable con este nivel de severidad.\n")
        return

    current_code = None
    descriptions = {
        "D01": "Parsers argparse anónimos",
        "D02": "Archivos demasiado grandes",
        "D03": "Funciones demasiado largas",
        "D04": "Demasiados parámetros",
        "D05": "Rutas absolutas hardcodeadas",
        "D06": "Excepciones tragadas en silencio",
        "D07": "Wildcard imports",
        "D08": "sys.path.insert hacks",
        "D09": "Funciones públicas sin type hints",
        "D10": "Nombres de función duplicados",
    }
    for f in visible:
        if f.code != current_code:
            current_code = f.code
            print(f"  ── {f.code}: {descriptions.get(f.code, f.code)} ──")
        sev_icon = {"error": "🔴", "warning": "🟡", "info": "⚪"}.get(f.severity, "·")
        print(f"  {sev_icon} {f.file}:{f.line}")
        print(f"       {f.message}")
        print(f"       → {f.remedy}")
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="debt_scanner",
        description="BAGO Sonda de Deuda Técnica Invisible",
    )
    parser.add_argument("--root",     default="",        help="Raíz del proyecto a escanear")
    parser.add_argument("--severity", default="warning", choices=["error", "warning", "info"],
                        help="Nivel mínimo a mostrar (default: warning)")
    parser.add_argument("--json",     action="store_true", help="Salida JSON")
    parser.add_argument("--test",     action="store_true", help="Ejecuta tests internos")

    args = parser.parse_args(argv)

    if args.test:
        return _run_tests()

    root = get_scan_root(args.root or None)
    report = scan(root)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False, default=str))
    else:
        _print_report(report, min_severity=args.severity)

    summ = report.summary()
    return 1 if summ["by_severity"]["error"] > 0 else 0


# ══════════════════════════════════════════════════════════════════════════════
#  TESTS INTERNOS
# ══════════════════════════════════════════════════════════════════════════════

def _run_tests() -> int:
    import tempfile, textwrap

    passed = 0
    failed = 0

    def ok(name: str, cond: bool) -> None:
        nonlocal passed, failed
        if cond:
            print(f"  PASS  {name}")
            passed += 1
        else:
            print(f"  FAIL  {name}")
            failed += 1

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        # D01 — anonymous parser
        (root / "parsers_bad.py").write_text(
            "sub.add_parser('foo', help='x')\n", encoding="utf-8"
        )
        src = (root / "parsers_bad.py").read_text(encoding="utf-8")
        r = detect_anonymous_parsers(root / "parsers_bad.py", src, root)
        ok("D01 anonymous parser detectado", len(r) == 1 and r[0].code == "D01")

        # D01 — assigned parser (no finding)
        src2 = "my_p = sub.add_parser('foo', help='x')\n"
        (root / "parsers_ok.py").write_text(src2, encoding="utf-8")
        r2 = detect_anonymous_parsers(root / "parsers_ok.py", src2, root)
        ok("D01 parser asignado ignorado", len(r2) == 0)

        # D02 — large file
        big_src = "x = 1\n" * 450
        (root / "big.py").write_text(big_src, encoding="utf-8")
        r3 = detect_large_files(root / "big.py", big_src, root)
        ok("D02 archivo grande detectado", len(r3) == 1 and r3[0].code == "D02")

        # D03 — long function
        long_fn = "def foo():\n" + "    x = 1\n" * 70 + "\n"
        (root / "longfn.py").write_text(long_fn, encoding="utf-8")
        r4 = detect_long_functions(root / "longfn.py", long_fn, root)
        ok("D03 función larga detectada", any(f.code == "D03" for f in r4))

        # D05 — hardcoded path
        src5 = 'path = "C:\\\\Users\\\\foo\\\\bar.py"\n'
        (root / "paths.py").write_text(src5, encoding="utf-8")
        r5 = detect_hardcoded_paths(root / "paths.py", src5, root)
        ok("D05 ruta hardcodeada detectada", len(r5) >= 1 and r5[0].code == "D05")

        # D06 — silent exception
        src6 = textwrap.dedent("""\
            try:
                x = 1
            except Exception:
                pass
        """)
        (root / "silent.py").write_text(src6, encoding="utf-8")
        r6 = detect_silent_exceptions(root / "silent.py", src6, root)
        ok("D06 excepción silenciosa detectada", len(r6) == 1 and r6[0].code == "D06")

        # D07 — wildcard import
        src7 = "from os.path import *\n"
        (root / "wild.py").write_text(src7, encoding="utf-8")
        r7 = detect_wildcard_imports(root / "wild.py", src7, root)
        ok("D07 wildcard import detectado", len(r7) == 1 and r7[0].code == "D07")

        # D09 — missing type hint
        src9 = "def public_fn(x, y):\n    return x + y\n"
        (root / "nohint.py").write_text(src9, encoding="utf-8")
        r9 = detect_missing_type_hints(root / "nohint.py", src9, root)
        ok("D09 función sin type hint detectada", len(r9) == 1 and r9[0].code == "D09")

        # D09 — private function ignored
        src9b = "def _private(x):\n    return x\n"
        (root / "priv.py").write_text(src9b, encoding="utf-8")
        r9b = detect_missing_type_hints(root / "priv.py", src9b, root)
        ok("D09 función privada ignorada", len(r9b) == 0)

        # D10 — duplicate names
        (root / "mod_a.py").write_text("def process():\n    pass\n", encoding="utf-8")
        (root / "mod_b.py").write_text("def process():\n    pass\n", encoding="utf-8")
        files_src = {
            root / "mod_a.py": "def process():\n    pass\n",
            root / "mod_b.py": "def process():\n    pass\n",
        }
        r10 = detect_duplicate_function_names(files_src, root)
        ok("D10 función duplicada detectada", len(r10) >= 1 and r10[0].code == "D10")

        # full scan returns DebtReport
        report = scan(root)
        ok("scan() devuelve DebtReport", isinstance(report, DebtReport))
        ok("DebtReport.score > 0", report.score > 0)
        ok("DebtReport.to_dict() es dict", isinstance(report.to_dict(), dict))

    print(f"\n  {'ALL PASS' if failed == 0 else f'{failed} FAILED'}  ({passed}/{passed+failed})")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
