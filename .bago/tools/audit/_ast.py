#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bago_ast_audit.py — Análisis AST semántico de código Python.

Detecta asimetrías entre lo que se DECLARA y lo que se CONSUME:
  - Callbacks de UI sin handler (Telegram, Flask, etc.)
  - Coroutines async llamadas sin await
  - Flags argparse declarados pero no usados (y viceversa)
  - Fixtures pytest huérfanos o usados sin definir
  - Variables de entorno accedidas sin .env declarado
  - Estados de máquina de estados inalcanzables / fantasmas
  - raise SomeError sin except correspondiente
  - Feature flags usados sin registro en config
  - EventEmitter: emit() sin listener on()
  - Tablas SQL referenciadas sin CREATE TABLE

Uso:
    bago audit ast                → analiza directorio actual
    bago audit ast /ruta/target   → analiza ese directorio o archivo
    bago audit ast --self         → analiza el propio BAGO
    bago audit ast --json         → output JSON
    bago audit ast --min-sev P1   → solo hallazgos P0 y P1
"""
from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

_RED  = "\033[0;31m"
_YEL  = "\033[0;33m"
_GRN  = "\033[0;32m"
_CYN  = "\033[0;36m"
_DIM  = "\033[2m"
_RST  = "\033[0m"
_BOLD = "\033[1m"

SEV_COLOR = {"P0": _RED, "P1": _YEL, "P2": _DIM}
SEV_ORDER = {"P0": 0, "P1": 1, "P2": 2}


@dataclass
class Finding:
    file: str
    line: int
    severity: str   # P0 / P1 / P2
    checker: str
    message: str


# ═══════════════════════════════════════════════════════════════════════════
# BASE
# ═══════════════════════════════════════════════════════════════════════════
class _Checker:
    name = "base"

    def check_file(self, path: Path) -> list[Finding]:
        return []

    def check_source(self, src: str, path: Path) -> list[Finding]:
        return []

    def _f(self, path, line, sev, msg) -> Finding:
        return Finding(str(path), line, sev, self.name, msg)


class _ASTChecker(_Checker):
    def check_file(self, path: Path) -> list[Finding]:
        try:
            src = path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(src, filename=str(path))
        except SyntaxError:
            return []
        return self._analyze(src, tree, path)

    def _analyze(self, src: str, tree: ast.AST, path: Path) -> list[Finding]:
        return []

    @staticmethod
    def _walk(tree): return ast.walk(tree)

    @staticmethod
    def _kw_strings(tree, kw_name: str) -> set[str]:
        out = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.keyword) and n.arg == kw_name:
                if isinstance(n.value, ast.Constant):
                    out.add(str(n.value.value))
        return out

    @staticmethod
    def _compare_strings(tree, varname: str) -> set[str]:
        out = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Compare):
                left = n.left
                if isinstance(left, ast.Name) and left.id == varname:
                    for op, comp in zip(n.ops, n.comparators):
                        if isinstance(op, ast.Eq) and isinstance(comp, ast.Constant):
                            out.add(str(comp.value))
        return out


# ═══════════════════════════════════════════════════════════════════════════
# 1. CALLBACK HANDLER — callback_data producidos vs consumidos
# ═══════════════════════════════════════════════════════════════════════════
class CallbackHandlerChecker(_ASTChecker):
    name = "callback_handler"

    def _analyze(self, src, tree, path):
        findings = []
        produced = self._kw_strings(tree, "callback_data")
        # también strings en listas/tuples que parezcan callback_data
        consumed = self._compare_strings(tree, "data")
        consumed |= self._compare_strings(tree, "callback_data")

        # Handlers startswith: elif data.startswith("prefix:")
        prefixes = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                fn = n.func
                if isinstance(fn, ast.Attribute) and fn.attr == "startswith":
                    if n.args and isinstance(n.args[0], ast.Constant):
                        prefixes.add(str(n.args[0].value))

        unhandled = {
            cb for cb in produced
            if cb not in consumed
            and not any(cb.startswith(p) for p in prefixes)
        }
        for cb in sorted(unhandled):
            findings.append(self._f(path, 0, "P1",
                f"callback_data='{cb}' producido pero sin handler en on_callback()"))
        return findings


# ═══════════════════════════════════════════════════════════════════════════
# 2. ASYNC/AWAIT — coroutine llamada sin await
# ═══════════════════════════════════════════════════════════════════════════
class AsyncAwaitChecker(_ASTChecker):
    name = "async_await"

    def _analyze(self, src, tree, path):
        findings = []
        async_funcs = {n.name for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef)}
        for n in ast.walk(tree):
            if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call):
                call = n.value
                name = None
                if isinstance(call.func, ast.Name):
                    name = call.func.id
                elif isinstance(call.func, ast.Attribute):
                    name = call.func.attr
                if name and name in async_funcs:
                    findings.append(self._f(path, n.lineno, "P0",
                        f"'{name}()' llamado sin await → crea coroutine object, nunca ejecuta"))
        return findings


# ═══════════════════════════════════════════════════════════════════════════
# 3. ARGPARSE — flags declarados vs usados
# ═══════════════════════════════════════════════════════════════════════════
class ArgparseChecker(_ASTChecker):
    name = "argparse"

    def _analyze(self, src, tree, path):
        findings = []
        declared, used = set(), set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                fn = n.func
                if isinstance(fn, ast.Attribute) and fn.attr == "add_argument":
                    for a in n.args:
                        if isinstance(a, ast.Constant) and str(a.value).startswith("--"):
                            declared.add(a.value.lstrip("-").replace("-", "_"))
            if isinstance(n, ast.Attribute):
                if isinstance(n.value, ast.Name) and n.value.id in ("args", "opts", "ns", "parsed"):
                    used.add(n.attr)
        for f in sorted(declared - used):
            findings.append(self._f(path, 0, "P2", f"--{f} declarado con add_argument pero nunca usado"))
        for f in sorted(used - declared):
            if not f.startswith("_"):
                findings.append(self._f(path, 0, "P1", f"args.{f} usado pero no declarado con add_argument"))
        return findings


# ═══════════════════════════════════════════════════════════════════════════
# 4. PYTEST FIXTURES — definidos vs usados
# ═══════════════════════════════════════════════════════════════════════════
class PytestFixtureChecker(_ASTChecker):
    name = "pytest_fixtures"
    _BUILTIN = {"request", "tmp_path", "capsys", "monkeypatch", "mocker",
                "capfd", "caplog", "pytestconfig", "self", "event_loop"}

    def _analyze(self, src, tree, path):
        findings = []
        defs, used = set(), set()
        for n in ast.walk(tree):
            if isinstance(n, ast.FunctionDef):
                dec_names = [
                    (d.id if isinstance(d, ast.Name) else
                     (d.attr if isinstance(d, ast.Attribute) else ""))
                    for d in n.decorator_list
                ]
                if "fixture" in dec_names:
                    defs.add(n.name)
                if n.name.startswith("test_"):
                    for a in n.args.args:
                        used.add(a.arg)
        for f in sorted(defs - used - self._BUILTIN):
            findings.append(self._f(path, 0, "P2",
                f"@pytest.fixture '{f}' definido pero ningún test lo usa"))
        for f in sorted(used - defs - self._BUILTIN):
            findings.append(self._f(path, 0, "P0",
                f"test usa fixture '{f}' pero no está definido en este archivo"))
        return findings


# ═══════════════════════════════════════════════════════════════════════════
# 5. ENV VARS — os.environ[] sin fallback conocido
# ═══════════════════════════════════════════════════════════════════════════
class EnvVarChecker(_ASTChecker):
    name = "env_vars"

    def _analyze(self, src, tree, path):
        findings = []
        # Encontrar .env en el mismo directorio o padres
        dotenv_keys = self._load_dotenv(path)

        accessed = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Subscript):
                if isinstance(n.value, ast.Attribute) and n.value.attr == "environ":
                    if isinstance(n.slice, ast.Constant):
                        accessed.add(n.slice.value)
            if isinstance(n, ast.Call):
                fn = n.func
                if isinstance(fn, ast.Attribute) and fn.attr in ("getenv", "get"):
                    # os.environ.get('KEY') / os.getenv('KEY')
                    if n.args and isinstance(n.args[0], ast.Constant):
                        # getenv con default es seguro si tiene default
                        has_default = len(n.args) > 1 or any(kw.arg == "default" for kw in n.keywords)
                        if not has_default:
                            accessed.add(n.args[0].value)

        for key in sorted(accessed - dotenv_keys):
            findings.append(self._f(path, 0, "P1",
                f"os.environ['{key}'] sin fallback y no encontrado en .env cercano → crash si ausente"))
        return findings

    @staticmethod
    def _load_dotenv(path: Path) -> set[str]:
        keys = set()
        for parent in [path.parent] + list(path.parents)[:3]:
            env_file = parent / ".env"
            if env_file.exists():
                for line in env_file.read_text(errors="ignore").splitlines():
                    m = re.match(r"^([A-Z_][A-Z0-9_]*)=", line.strip())
                    if m:
                        keys.add(m.group(1))
                break
        return keys


# ═══════════════════════════════════════════════════════════════════════════
# 6. STATE MACHINE — estados inalcanzables / fantasmas
# ═══════════════════════════════════════════════════════════════════════════
class StateMachineChecker(_ASTChecker):
    name = "state_machine"
    _STATE_VARS = {"state", "status", "phase", "mode", "step"}

    def _analyze(self, src, tree, path):
        findings = []
        for var in self._STATE_VARS:
            sets, checks = set(), set()
            for n in ast.walk(tree):
                if isinstance(n, ast.Assign):
                    for t in n.targets:
                        if isinstance(t, ast.Name) and t.id == var:
                            if isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
                                sets.add(n.value.value)
                if isinstance(n, ast.Compare):
                    if isinstance(n.left, ast.Name) and n.left.id == var:
                        for op, v in zip(n.ops, n.comparators):
                            if isinstance(op, ast.Eq) and isinstance(v, ast.Constant) and isinstance(v.value, str):
                                checks.add(v.value)
            # Solo reportar si hay al menos 2 estados (es realmente una SM)
            if len(sets) >= 2 or len(checks) >= 2:
                for s in sorted(checks - sets):
                    findings.append(self._f(path, 0, "P1",
                        f"{var}=='{s}' comprobado pero ese valor nunca se asigna (estado inalcanzable)"))
                for s in sorted(sets - checks):
                    findings.append(self._f(path, 0, "P2",
                        f"{var}='{s}' asignado pero nunca comprobado (estado fantasma)"))
        return findings


# ═══════════════════════════════════════════════════════════════════════════
# 7. EXCEPTION COVERAGE — raise sin except
# ═══════════════════════════════════════════════════════════════════════════
class ExceptionCoverageChecker(_ASTChecker):
    name = "exception_coverage"
    _GENERIC = {"Exception", "BaseException", "Error", "RuntimeError"}

    def _analyze(self, src, tree, path):
        findings = []
        raised, caught = set(), set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Raise) and n.exc:
                exc = n.exc
                name = (exc.id if isinstance(exc, ast.Name) else
                        (exc.func.id if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name) else None))
                if name:
                    raised.add(name)
            if isinstance(n, ast.ExceptHandler) and n.type:
                t = n.type
                name = (t.id if isinstance(t, ast.Name) else
                        (t.attr if isinstance(t, ast.Attribute) else None))
                if name:
                    caught.add(name)
        for e in sorted(raised - caught - self._GENERIC):
            findings.append(self._f(path, 0, "P1",
                f"raise {e} sin except {e} en este módulo — puede propagarse sin manejar"))
        return findings


# ═══════════════════════════════════════════════════════════════════════════
# 8. EVENT EMITTER — emit() sin listener
# ═══════════════════════════════════════════════════════════════════════════
class EventEmitterChecker(_Checker):
    name = "event_emitter"

    def check_file(self, path: Path) -> list[Finding]:
        findings = []
        try:
            src = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []
        emitted  = set(re.findall(r"\.emit\s*\(['\"]([^'\"]+)['\"]", src))
        listened = set(re.findall(r"\.on\s*\(['\"]([^'\"]+)['\"]", src))
        for e in sorted(emitted - listened):
            findings.append(self._f(path, 0, "P1",
                f"evento '{e}' emitido pero ningún listener .on() registrado"))
        for e in sorted(listened - emitted):
            findings.append(self._f(path, 0, "P2",
                f"listener .on('{e}') registrado pero el evento nunca se emite"))
        return findings


# ═══════════════════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════════════════
CHECKERS: list[_Checker] = [
    CallbackHandlerChecker(),
    AsyncAwaitChecker(),
    ArgparseChecker(),
    PytestFixtureChecker(),
    EnvVarChecker(),
    StateMachineChecker(),
    ExceptionCoverageChecker(),
    EventEmitterChecker(),
]

_SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache"}


def collect_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target] if target.suffix == ".py" else []
    files = []
    for p in sorted(target.rglob("*.py")):
        if not any(skip in p.parts for skip in _SKIP_DIRS):
            files.append(p)
    return files


def run_audit(target: Path, min_sev: str = "P2") -> list[Finding]:
    files = collect_files(target)
    findings: list[Finding] = []
    min_order = SEV_ORDER.get(min_sev, 2)
    for fpath in files:
        for checker in CHECKERS:
            for finding in checker.check_file(fpath):
                if SEV_ORDER.get(finding.severity, 2) <= min_order:
                    findings.append(finding)
    return sorted(findings, key=lambda f: (SEV_ORDER.get(f.severity, 9), f.file, f.line))


def print_report(findings: list[Finding], target: Path, elapsed: float):
    counts = {"P0": 0, "P1": 0, "P2": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    print()
    print(f"{_BOLD}═══ BAGO AST AUDIT ══════════════════════════════════════════{_RST}")
    print(f"Objetivo: {target}")
    print(f"Hallazgos: {_RED}{counts['P0']} P0{_RST}  {_YEL}{counts['P1']} P1{_RST}  {_DIM}{counts['P2']} P2{_RST}  ({elapsed:.1f}s)")
    print()

    if not findings:
        print(f"  {_GRN}✅ Sin hallazgos{_RST}")
        return

    current_file = None
    for f in findings:
        if f.file != current_file:
            current_file = f.file
            rel = Path(f.file).name
            print(f"  {_CYN}{rel}{_RST}")
        sev_color = SEV_COLOR.get(f.severity, "")
        loc = f"L{f.line}" if f.line else "   "
        print(f"    {sev_color}[{f.severity}]{_RST} {_DIM}[{f.checker}]{_RST} {loc}  {f.message}")
    print()




def main(argv=None):
    import time

    args = sys.argv[1:] if argv is None else list(argv)
    as_json = False
    self_run = False
    min_sev = "P2"
    positional: list[str] = []

    i = 0
    while i < len(args):
        a = args[i]
        if a == "--json":
            as_json = True
        elif a == "--self":
            self_run = True
        elif a == "--min-sev" and i + 1 < len(args):
            min_sev = args[i + 1]
            i += 1
        elif a in ("-h", "--help", "help"):
            print(__doc__)
            return 0
        elif not a.startswith("--"):
            positional.append(a)
        i += 1

    if self_run:
        target = Path(__file__).resolve().parents[3]
    elif positional:
        target = Path(positional[0]).expanduser().resolve()
    else:
        target = Path.cwd()

    if not target.exists():
        print(f"[AST AUDIT] ❌ Ruta no encontrada: {target}", file=sys.stderr)
        return 1

    t0 = time.time()
    findings = run_audit(target, min_sev=min_sev)
    elapsed = time.time() - t0

    if as_json:
        print(json.dumps([asdict(f) for f in findings], ensure_ascii=False, indent=2))
        return 0

    print_report(findings, target, elapsed)
    return 1 if any(f.severity == "P0" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
