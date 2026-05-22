#!/usr/bin/env python3
"""placeholder_scan.py — Herramienta #112: Detector de placeholders y datos ficticios.

Detecta en código Python patrones que indican datos inventados, implementaciones
incompletas o valores de relleno que podrían filtrarse a producción:

  1. FAKE_DATE         — Fechas ISO "YYYY-01-01T00:00:00Z" (centinelas midnight-Jan1)
  2. PLACEHOLDER_STR   — Literales de cadena que son marcadores de posición
                         ("TODO", "PLACEHOLDER", "STUB", "CHANGE_ME", etc.)
  3. STUB_RAISE        — `raise NotImplementedError` en funciones concretas
  4. ELLIPSIS_BODY     — Función concreta cuyo único cuerpo es `...`
  5. TODO_COMMENT      — Comentarios # TODO / # FIXME / # HACK / # XXX / # STUB

Supresión (por línea): añade `# noqa: PLACEHOLDER_SCAN` para ignorar un hallazgo.

Uso:
  python3 .bago/tools/placeholder_scan.py [TARGET] [--json] [--test]
  python3 .bago/tools/placeholder_scan.py . --json       # output JSON (para code_review)
  python3 .bago/tools/placeholder_scan.py src/ --json    # directorio específico

Exit codes:
  0   sin hallazgos de nivel error
  1   hay hallazgos de nivel warning o superior
  2   error interno / ruta inválida
"""
from __future__ import annotations

import ast
import io
import json
import re
import sys
import tokenize
from dataclasses import asdict, dataclass
from pathlib import Path

# ── Constantes ────────────────────────────────────────────────────────────────

TOOL_NAME = "placeholder_scan"

# Directorios excluidos al escanear
EXCLUDE_DIRS: frozenset[str] = frozenset({
    "__pycache__", "node_modules", ".git", ".venv", "venv",
    "dist", "build", "sandbox", ".tox",
})

# Reglas de severidad
SEV_ERROR   = "error"
SEV_WARNING = "warning"
SEV_INFO    = "info"

# Literales de cadena que son inequívocamente marcadores de posición
PLACEHOLDER_LITERALS: frozenset[str] = frozenset({
    "TODO", "FIXME", "PLACEHOLDER", "STUB", "NOT_IMPLEMENTED",
    "YOUR_VALUE_HERE", "CHANGE_ME", "REPLACE_ME", "TBD",
    "<placeholder>", "<TODO>", "<STUB>", "<REPLACE>",
    "YOUR_API_KEY_HERE", "INSERT_YOUR_KEY",
})

# Prefijos de comentario TODO (case-insensitive, ignora espacio post-#)
TODO_KEYWORDS: tuple[str, ...] = ("TODO", "FIXME", "HACK", "XXX", "STUB")

# Fecha centinela: YYYY-01-01T00:00:00[Z|+offset] — midnight 1-enero
# Solo detecta cuando NO está dentro de un comentario suprimido
_FAKE_DATE_RE = re.compile(
    r"""(?x)
    "(\d{4}-01-01T00:00:00(?:Z|[+-]\d{2}:\d{2})?)"
    """,
    re.VERBOSE,
)

# Nombre de la supresión inline
_NOQA_TOKEN = "noqa: PLACEHOLDER_SCAN"


# ── Modelo de hallazgo ─────────────────────────────────────────────────────────

@dataclass
class Finding:
    file:     str
    line:     int
    rule:     str
    severity: str
    message:  str
    snippet:  str = ""

    def fmt(self) -> str:
        sev_map = {SEV_ERROR: "❌", SEV_WARNING: "⚠️ ", SEV_INFO: "ℹ️ "}
        icon = sev_map.get(self.severity, "  ")
        return (
            f"  {icon} [{self.rule}] {self.file}:{self.line}\n"
            f"     {self.message}\n"
            f"     > {self.snippet.strip()}"
        )


# ── Utilidades ─────────────────────────────────────────────────────────────────

def _is_test_file(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    return (
        "tests" in parts
        or "test" in parts
        or path.name.startswith("test_")
        or path.name.endswith("_test.py")
    )


def _is_suppressed(line: str) -> bool:
    return _NOQA_TOKEN in line


def _source_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


# ── Escáner 1: FAKE_DATE (regex sobre líneas) ──────────────────────────────────

def scan_fake_dates(path: Path, lines: list[str], is_test: bool) -> list[Finding]:
    """Detecta fechas ISO sentinel YYYY-01-01T00:00:00Z en código no-test."""
    out: list[Finding] = []
    for i, raw in enumerate(lines, start=1):
        if _is_suppressed(raw):
            continue
        for m in _FAKE_DATE_RE.finditer(raw):
            out.append(Finding(
                file=str(path),
                line=i,
                rule="FAKE_DATE",
                severity=SEV_WARNING,
                message=(
                    f"Fecha centinela '{m.group(1)}' detectada — "
                    "posible placeholder de test filtrado a código de producción."
                ),
                snippet=raw.strip(),
            ))
    return out


# ── Escáner 2: TODO_COMMENT (tokenize, solo comentarios reales) ────────────────

def scan_todo_comments(path: Path, source: str, lines: list[str]) -> list[Finding]:
    """Detecta comentarios TODO/FIXME usando tokenize para evitar falsos positivos."""
    out: list[Finding] = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError:
        return out

    for tok_type, tok_string, (srow, _scol), *_ in tokens:
        if tok_type != tokenize.COMMENT:
            continue
        raw_line = lines[srow - 1] if srow <= len(lines) else ""
        if _is_suppressed(raw_line):
            continue
        # Strip leading #/spaces from comment text
        comment_text = tok_string.lstrip("#").strip()
        for kw in TODO_KEYWORDS:
            if comment_text.upper().startswith(kw):
                out.append(Finding(
                    file=str(path),
                    line=srow,
                    rule="TODO_COMMENT",
                    severity=SEV_INFO,
                    message=f"Comentario pendiente: {tok_string.strip()}",
                    snippet=raw_line.strip(),
                ))
                break
    return out


# ── Escáner 3+4+5: AST-based ──────────────────────────────────────────────────

def _is_abstract_func(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Retorna True si la función está decorada con @abstractmethod."""
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == "abstractmethod":
            return True
        if isinstance(dec, ast.Attribute) and dec.attr == "abstractmethod":
            return True
    return False


def _is_abstract_class(cls: ast.ClassDef) -> bool:
    """Retorna True si la clase hereda de ABC, Protocol, o abc.ABC."""
    for base in cls.bases:
        if isinstance(base, ast.Name) and base.id in ("ABC", "Protocol"):
            return True
        if isinstance(base, ast.Attribute) and base.attr in ("ABC", "Protocol"):
            return True
    return False


def _is_test_func(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return node.name.startswith("test_") or node.name in ("_self_test", "setUp", "tearDown")


def _body_is_only_ellipsis(body: list[ast.stmt]) -> bool:
    """True si el cuerpo es solo `...` (Ellipsis como expresión)."""
    real = [s for s in body if not isinstance(s, ast.Expr) or not isinstance(
        getattr(s, "value", None), ast.Constant
    ) or s.value.value is not ...  # type: ignore[union-attr]
    ]
    # Versión compatible: body == [Expr(Constant(...))]
    if len(body) == 1:
        stmt = body[0]
        if isinstance(stmt, ast.Expr) and isinstance(getattr(stmt, "value", None), ast.Constant):
            return stmt.value.value is ...  # type: ignore[union-attr]
    return False


def _body_has_raise_not_impl(body: list[ast.stmt]) -> int | None:
    """Retorna el número de línea si hay `raise NotImplementedError` en el cuerpo."""
    for stmt in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(stmt, ast.Raise) and stmt.exc is not None:
            exc = stmt.exc
            name = None
            if isinstance(exc, ast.Name):
                name = exc.id
            elif isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
                name = exc.func.id
            if name == "NotImplementedError":
                return getattr(stmt, "lineno", None)
    return None


def _body_has_placeholder_return(body: list[ast.stmt], lines: list[str]) -> list[tuple[int, str]]:
    """Busca `return "PLACEHOLDER_LITERAL"` en el cuerpo."""
    results: list[tuple[int, str]] = []
    for stmt in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(stmt, ast.Return) and isinstance(getattr(stmt, "value", None), ast.Constant):
            val = stmt.value.value  # type: ignore[union-attr]
            if isinstance(val, str) and val.upper() in {v.upper() for v in PLACEHOLDER_LITERALS}:
                ln = getattr(stmt, "lineno", 0)
                snippet = lines[ln - 1].strip() if ln and ln <= len(lines) else ""
                results.append((ln, snippet))
    return results


def scan_ast(path: Path, source: str, lines: list[str], is_test: bool) -> list[Finding]:
    """
    Escanea con AST:
      - STUB_RAISE: raise NotImplementedError en funciones concretas
      - ELLIPSIS_BODY: función concreta cuyo cuerpo es solo ...
      - PLACEHOLDER_STR: return "PLACEHOLDER_LITERAL"
    """
    out: list[Finding] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return out

    # Mapa de clase -> abstract para contexto
    abstract_classes: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and _is_abstract_class(node):
            abstract_classes.add(node.name)

    # Buscar funciones en primer nivel y en clases
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if is_test and _is_test_func(node):
            continue
        if _is_abstract_func(node):
            continue

        ln = node.lineno
        raw_line = lines[ln - 1] if ln <= len(lines) else ""
        if _is_suppressed(raw_line):
            continue

        # ELLIPSIS_BODY
        if _body_is_only_ellipsis(node.body):
            out.append(Finding(
                file=str(path),
                line=ln,
                rule="ELLIPSIS_BODY",
                severity=SEV_INFO,
                message=f"Función '{node.name}' tiene solo `...` como cuerpo — posible stub sin implementar.",
                snippet=raw_line.strip(),
            ))

        # STUB_RAISE
        raise_line = _body_has_raise_not_impl(node.body)
        if raise_line is not None:
            raise_raw = lines[raise_line - 1] if raise_line <= len(lines) else raw_line
            if not _is_suppressed(raise_raw):
                out.append(Finding(
                    file=str(path),
                    line=raise_line,
                    rule="STUB_RAISE",
                    severity=SEV_WARNING,
                    message=f"Función '{node.name}' lanza NotImplementedError — implementación pendiente.",
                    snippet=raise_raw.strip(),
                ))

        # PLACEHOLDER_STR (return values)
        for ret_ln, snippet in _body_has_placeholder_return(node.body, lines):
            ret_raw = lines[ret_ln - 1] if ret_ln <= len(lines) else ""
            if not _is_suppressed(ret_raw):
                out.append(Finding(
                    file=str(path),
                    line=ret_ln,
                    rule="PLACEHOLDER_STR",
                    severity=SEV_WARNING,
                    message=f"Función '{node.name}' retorna un literal placeholder.",
                    snippet=snippet,
                ))

    # PLACEHOLDER_STR en asignaciones de nivel módulo
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(getattr(node, "value", None), ast.Constant):
            continue
        val = node.value.value  # type: ignore[union-attr]
        if not isinstance(val, str):
            continue
        if val.upper() not in {v.upper() for v in PLACEHOLDER_LITERALS}:
            continue
        ln = node.lineno
        raw_line = lines[ln - 1] if ln <= len(lines) else ""
        if _is_suppressed(raw_line):
            continue
        # Evitar falsos positivos en regex patterns (líneas que tienen r"...")
        if "re.compile" in raw_line or "_RE" in raw_line or "pattern" in raw_line.lower():
            continue
        out.append(Finding(
            file=str(path),
            line=ln,
            rule="PLACEHOLDER_STR",
            severity=SEV_WARNING,
            message=f"Asignación con literal placeholder: {val!r}",
            snippet=raw_line.strip(),
        ))

    return out


# ── Escaneo de un archivo ──────────────────────────────────────────────────────

def scan_file(path: Path, skip_test_files: bool = False) -> list[Finding]:
    """Escanea un archivo .py con todas las reglas."""
    is_test = _is_test_file(path)
    if skip_test_files and is_test:
        return []

    lines = _source_lines(path)
    if not lines:
        return []

    source = "\n".join(lines)
    findings: list[Finding] = []

    # Normalizar path relativo si es posible
    try:
        rel = path.relative_to(Path.cwd())
        display_path = str(rel).replace("\\", "/")
    except ValueError:
        display_path = str(path).replace("\\", "/")

    def _with_path(fs: list[Finding]) -> list[Finding]:
        for f in fs:
            f.file = display_path
        return fs

    findings.extend(_with_path(scan_fake_dates(path, lines, is_test)))
    findings.extend(_with_path(scan_todo_comments(path, source, lines)))
    findings.extend(_with_path(scan_ast(path, source, lines, is_test)))

    return findings


# ── Escaneo de un directorio ───────────────────────────────────────────────────

def scan_target(target: str, skip_tests: bool = False) -> list[Finding]:
    """Escanea TARGET (archivo o directorio recursivo)."""
    p = Path(target)
    if not p.exists():
        return []

    if p.is_file() and p.suffix == ".py":
        return scan_file(p, skip_tests)

    if p.is_dir():
        all_findings: list[Finding] = []
        for pyfile in sorted(p.rglob("*.py")):
            if any(part in EXCLUDE_DIRS for part in pyfile.parts):
                continue
            all_findings.extend(scan_file(pyfile, skip_tests))
        return all_findings

    return []


# ── CLI ────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]

    target     = "."
    as_json    = False
    skip_tests = False
    run_test   = False

    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--json":
            as_json = True; i += 1
        elif a == "--skip-tests":
            skip_tests = True; i += 1
        elif a == "--test":
            run_test = True; i += 1
        elif not a.startswith("--"):
            target = a; i += 1
        else:
            i += 1

    if run_test:
        return _self_test()

    findings = scan_target(target, skip_tests)

    if as_json:
        out = {
            "target": target,
            "total": len(findings),
            "findings": [asdict(f) for f in findings],
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 1 if any(f.severity in (SEV_ERROR, SEV_WARNING) for f in findings) else 0

    # Output legible
    if not findings:
        print(f"✅ Sin placeholders detectados en {target}")
        return 0

    errors   = [f for f in findings if f.severity == SEV_ERROR]
    warnings = [f for f in findings if f.severity == SEV_WARNING]
    infos    = [f for f in findings if f.severity == SEV_INFO]

    print(f"\n🔍 Placeholder Scan — {target}")
    print(f"  {len(findings)} hallazgo(s)  [{len(errors)} error, {len(warnings)} warning, {len(infos)} info]\n")
    for f in findings:
        print(f.fmt())
        print()

    return 1 if (errors or warnings) else 0


# ── Self-tests ─────────────────────────────────────────────────────────────────

def _self_test() -> int:
    import tempfile, textwrap, traceback

    print("Tests de placeholder_scan.py...")
    fails: list[str] = []

    def _ok(name: str) -> None:
        print(f"  ✅ {name}")

    def _fail(name: str, detail: str) -> None:
        fails.append(f"{name}: {detail}")
        print(f"  ❌ {name}: {detail}")

    def _write(tmp: Path, name: str, code: str) -> Path:
        f = tmp / name
        f.write_text(textwrap.dedent(code), encoding="utf-8")
        return f

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # T1: FAKE_DATE detectado
        f1 = _write(tmp, "fake_date.py", """\
            x = "2026-01-01T00:00:00Z"
        """)
        r1 = scan_file(f1)
        if any(f.rule == "FAKE_DATE" for f in r1):
            _ok("T1: FAKE_DATE detectado")
        else:
            _fail("T1", f"No se detectó FAKE_DATE, findings={[f.rule for f in r1]}")

        # T2: FAKE_DATE suprimido con noqa
        f2 = _write(tmp, "fake_date_noqa.py", """\
            x = "2026-01-01T00:00:00Z"  # noqa: PLACEHOLDER_SCAN
        """)
        r2 = [f for f in scan_file(f2) if f.rule == "FAKE_DATE"]
        if not r2:
            _ok("T2: FAKE_DATE suprimido con noqa")
        else:
            _fail("T2", "FAKE_DATE no fue suprimido")

        # T3: TODO_COMMENT en comentario real
        f3 = _write(tmp, "todo_comment.py", """\
            def foo():
                pass  # TODO: implement this
        """)
        r3 = scan_file(f3)
        if any(f.rule == "TODO_COMMENT" for f in r3):
            _ok("T3: TODO_COMMENT detectado en comentario")
        else:
            _fail("T3", f"No se detectó TODO_COMMENT, findings={[f.rule for f in r3]}")

        # T4: TODO dentro de string NO debe flaguearse
        f4 = _write(tmp, "todo_in_string.py", """\
            TODO_RE = r"#\\s*(TODO|FIXME)"
        """)
        r4 = [f for f in scan_file(f4) if f.rule == "TODO_COMMENT"]
        if not r4:
            _ok("T4: TODO en string no flagueado")
        else:
            _fail("T4", f"TODO en string fue flagueado incorrectamente: {r4}")

        # T5: STUB_RAISE detectado en función concreta
        f5 = _write(tmp, "stub_raise.py", """\
            def my_func():
                raise NotImplementedError
        """)
        r5 = scan_file(f5)
        if any(f.rule == "STUB_RAISE" for f in r5):
            _ok("T5: STUB_RAISE detectado")
        else:
            _fail("T5", f"No se detectó STUB_RAISE, findings={[f.rule for f in r5]}")

        # T6: STUB_RAISE en @abstractmethod NO debe flaguearse
        f6 = _write(tmp, "abstract_raise.py", """\
            from abc import abstractmethod, ABC
            class Foo(ABC):
                @abstractmethod
                def bar(self):
                    raise NotImplementedError
        """)
        r6 = [f for f in scan_file(f6) if f.rule == "STUB_RAISE"]
        if not r6:
            _ok("T6: STUB_RAISE ignorado en @abstractmethod")
        else:
            _fail("T6", f"STUB_RAISE flagueado en abstractmethod: {r6}")

        # T7: ELLIPSIS_BODY detectado en función concreta
        f7 = _write(tmp, "ellipsis_body.py", """\
            def not_implemented():
                ...
        """)
        r7 = scan_file(f7)
        if any(f.rule == "ELLIPSIS_BODY" for f in r7):
            _ok("T7: ELLIPSIS_BODY detectado")
        else:
            _fail("T7", f"No se detectó ELLIPSIS_BODY, findings={[f.rule for f in r7]}")

        # T8: PLACEHOLDER_STR en return
        f8 = _write(tmp, "placeholder_return.py", """\
            def get_value():
                return "PLACEHOLDER"
        """)
        r8 = scan_file(f8)
        if any(f.rule == "PLACEHOLDER_STR" for f in r8):
            _ok("T8: PLACEHOLDER_STR detectado en return")
        else:
            _fail("T8", f"No se detectó PLACEHOLDER_STR, findings={[f.rule for f in r8]}")

        # T9: output JSON tiene campo 'findings'
        f9 = _write(tmp, "json_test.py", """\
            x = "2026-01-01T00:00:00Z"
        """)
        findings9 = scan_target(str(f9))
        payload = {"total": len(findings9), "findings": [asdict(f) for f in findings9]}
        assert "findings" in payload, "payload no tiene campo findings"
        assert payload["total"] > 0, "total debe ser > 0"
        _ok("T9: output JSON válido con campo findings")

    if fails:
        print(f"\n  ❌ {len(fails)} test(s) fallaron")
        return 1

    print(f"  ✅ Todos los tests pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
