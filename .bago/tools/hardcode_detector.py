#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hardcode_detector.py — Detecta datos hardcodeados que deberían ser dinámicos.

Analiza archivos .py buscando patrones de datos estáticos que deberían
calcularse o leerse desde configuración en tiempo de ejecución.

Categorías:
  INTERPRETER  — "python3"/"python" hardcodeados en llamadas subprocess
  ABS_PATH     — rutas absolutas embebidas en strings
  VERSION      — strings de versión fuera de contextos de definición
  PORT         — números de puerto hardcodeados
  USERNAME     — nombres de usuario embebidos en paths
  URL          — URLs con dominios específicos hardcodeados
  DATE         — fechas ISO hardcodeadas en strings
  CWD          — Path.cwd() en herramientas que deberían usar BAGO_USER_CWD

Uso:
  python hardcode_detector.py                → escanea BAGO completo
  python hardcode_detector.py <ruta>         → escanea ruta específica
  python hardcode_detector.py --strict       → incluye hallazgos LOW
  python hardcode_detector.py --json         → salida JSON
  python hardcode_detector.py --summary      → solo resumen por categoría
  python hardcode_detector.py --category X   → filtra por categoría
  python hardcode_detector.py --test         → auto-test
"""

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

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

# ── Rutas ─────────────────────────────────────────────────────────────────────
TOOLS_DIR  = Path(__file__).resolve().parent
BAGO_ROOT  = TOOLS_DIR.parent
REPO_ROOT  = BAGO_ROOT.parent

# ── ANSI ──────────────────────────────────────────────────────────────────────
_USE_COLOR = sys.stdout.isatty() and "--json" not in sys.argv
def _c(code: str, t: str) -> str:
    return f"\033[{code}m{t}\033[0m" if _USE_COLOR else t

RED    = lambda t: _c("1;31", t)
YELLOW = lambda t: _c("1;33", t)
CYAN   = lambda t: _c("1;36", t)
DIM    = lambda t: _c("2",    t)
BOLD   = lambda t: _c("1",    t)
GREEN  = lambda t: _c("1;32", t)


# ── Modelo ─────────────────────────────────────────────────────────────────────

@dataclass
class Finding:
    file:     Path
    line:     int
    category: str
    severity: str   # HIGH | MEDIUM | LOW
    message:  str
    snippet:  str
    fix:      str   # sugerencia concreta

    def to_dict(self) -> dict:
        return {
            "file":     str(self.file.relative_to(REPO_ROOT)),
            "line":     self.line,
            "category": self.category,
            "severity": self.severity,
            "message":  self.message,
            "snippet":  self.snippet.strip(),
            "fix":      self.fix,
        }


# ── Reglas ─────────────────────────────────────────────────────────────────────

@dataclass
class Rule:
    category:    str
    severity:    str
    pattern:     re.Pattern
    message:     str
    fix:         str
    # Líneas a excluir si contienen alguno de estos tokens
    exclude_if:  list[str] = field(default_factory=list)
    # Sólo aplica si la línea contiene alguno de estos tokens
    require_any: list[str] = field(default_factory=list)


def _build_rules() -> list[Rule]:
    return [
        # ── INTERPRETER ───────────────────────────────────────────────────────
        Rule(
            category="INTERPRETER",
            severity="HIGH",
            pattern=re.compile(r'"python3(?:\.exe)?"\s*[,\]]'),
            message='Intérprete "python3" hardcodeado — no existe en Windows',
            fix="Reemplaza con sys.executable",
            exclude_if=["sys.executable", "# noqa", "shebang", "#!/usr/bin", '"language": "python"'],
        ),
        Rule(
            category="INTERPRETER",
            severity="HIGH",
            pattern=re.compile(r'"python(?:\.exe)?"\s*[,\]]'),
            message='Intérprete "python" hardcodeado — puede no estar en PATH',
            fix="Reemplaza con sys.executable",
            exclude_if=["sys.executable", "# noqa", "import python", "#!/", "python3", '"language": "python"'],
        ),
        # ── ABS_PATH ─────────────────────────────────────────────────────────
        Rule(
            category="ABS_PATH",
            severity="HIGH",
            pattern=re.compile(r'["\'](?:/Users/|/home/|/Volumes/|C:\\\\|D:\\\\|E:\\\\)[^"\']{4,}["\']'),
            message="Ruta absoluta hardcodeada con directorio de usuario",
            fix="Usa Path(__file__).resolve() o variables de entorno",
            exclude_if=["# noqa", "example", "TODO", "FIXME", "__doc__", '"""', "'''"  ],
        ),
        Rule(
            category="ABS_PATH",
            severity="MEDIUM",
            pattern=re.compile(r'["\'](?:/Volumes/bago_core|/media/)[^"\']{3,}["\']'),
            message="Ruta de dispositivo externo hardcodeada",
            fix="Usa una variable de entorno BAGO_PADRE_PATH o configuración dinámica",
            exclude_if=["# noqa", '"""', "'''"],
        ),
        # ── VERSION ──────────────────────────────────────────────────────────
        Rule(
            category="VERSION",
            severity="MEDIUM",
            pattern=re.compile(r'"(v?\d+\.\d+(?:\.\d+)?(?:-[a-z]+)?)"'),
            message="String de versión hardcodeado fuera de contexto de definición",
            fix='Lee la versión desde pack.json: json.loads((BAGO_ROOT/"pack.json").read_text())["version"]',
            exclude_if=[
                "__version__", "version =", "version=", "bago_version",
                "# noqa", "CHANGELOG", "EVOLUCION", "bump", "tag:", "requires",
                "python_requires", ">=", "<=", "semantic", "README",
                "pack.json", ".version", "data.get", "state.get",
            ],
            require_any=["subprocess", "print(", "f\"", "f'", '+"', "+=", "=="],
        ),
        # ── PORT ─────────────────────────────────────────────────────────────
        Rule(
            category="PORT",
            severity="MEDIUM",
            pattern=re.compile(r'\b(8080|8000|8888|3000|3001|5000|5001|4000|9000|7000|6006|11434)\b'),
            message="Número de puerto hardcodeado",
            fix='Usa un argumento --port o variable de entorno: int(os.environ.get("BAGO_PORT", "8080"))',
            exclude_if=["# noqa", "default=", "DEFAULT_PORT", "PORT =", "argparse", "help=", "[:", "PRAGMA busy_timeout", "wait_for_timeout", "ShowBalloonTip", "butter(2,", "bp(", "hp(", "shelf(", "lp(", "token_budget=", "size >", "REFRESH =", "limit_per_call", "server.listen(", "parser.add_argument(", "min_ms:", "max_ms:", "fk >"],
        ),
        # ── USERNAME ─────────────────────────────────────────────────────────
        Rule(
            category="USERNAME",
            severity="HIGH",
            pattern=re.compile(r'["\'](?:.*?)[/\\](?:Users|home)[/\\]([a-zA-Z][a-zA-Z0-9_-]+)[/\\]'),
            message="Nombre de usuario embebido en una ruta",
            fix="Usa Path.home() o os.environ['HOME'] / os.environ['USERPROFILE']",
            exclude_if=["# noqa", '"""', "'''", "example", "test_"],
        ),
        # ── URL ──────────────────────────────────────────────────────────────
        Rule(
            category="URL",
            severity="LOW",
            pattern=re.compile(r'"https?://(?!github\.com/[a-zA-Z]+/[a-zA-Z])[^\s"]{12,}"'),
            message="URL con dominio específico hardcodeada",
            fix="Mueve la URL a configuración o usa una variable de entorno",
            exclude_if=["# noqa", '"""', "'''", "# http", "wget", "curl", "README"],
        ),
        # ── DATE ─────────────────────────────────────────────────────────────
        Rule(
            category="DATE",
            severity="LOW",
            pattern=re.compile(r'"(20\d\d-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))"'),
            message="Fecha ISO hardcodeada — debería calcularse en tiempo de ejecución",
            fix="Usa: datetime.now(timezone.utc).strftime('%Y-%m-%d')",
            exclude_if=[
                "# noqa", "CHANGELOG", "test", "created_at", "expected",
                "example", "seeded_at", "since", "until", "last_updated",
                '"""', "'''",
            ],
        ),
        # ── CWD ──────────────────────────────────────────────────────────────
        Rule(
            category="CWD",
            severity="MEDIUM",
            pattern=re.compile(r'Path\.cwd\(\)'),
            message="Path.cwd() puede devolver el directorio de BAGO en lugar del proyecto del usuario",
            fix='Usa: Path(os.environ.get("BAGO_USER_CWD", "")).resolve() o _get_user_cwd()',
            exclude_if=["# noqa", "bago_banner", "bago_shell", "tool_registry", "hardcode_detector", "template_gen"],
        ),
        # ── ACCENT_PATH ───────────────────────────────────────────────────────
        Rule(
            category="ACCENT_PATH",
            severity="HIGH",
            pattern=re.compile(r'["\'][^"\']*[áéíóúñüÁÉÍÓÚÑÜ][^"\']*["\']'),
            message="Carácter acentuado en string de ruta/clave — rompe en shells y sistemas sin UTF-8 path",
            fix="Usa la forma ASCII: á→a, é→e, í→i, ó→o, ú→u, ñ→n, ü→u",
            exclude_if=["# noqa", '"""', "'''", "print(", "log.", "logger.", "raise ", "assert ",
                        "help=", "description=", "epilog=", "message=", "f\"", "f'",
                        "status_line(", "card(", "gr.update(", "callback_data=",
                        "InlineKeyboardButton(", "InlineKeyboardMarkup(", "_prompt_int(",
                        "_prompt_bool(", "ask(", "-->", "==>"],
            require_any=["subprocess", "shell=True", "os.system", "Popen(", "call("],
        ),
        Rule(
            category="ACCENT_PATH",
            severity="MEDIUM",
            pattern=re.compile(r'["\'][^"\']*[áéíóúñüÁÉÍÓÚÑÜ][^"\']*["\']'),
            message="Carácter acentuado en string de ruta o clave — puede ser frágil en Windows/herramientas externas",
            fix="Usa la forma ASCII para rutas internas: á→a, é→e, í→i, ó→o, ú→u, ñ→n",
            exclude_if=["# noqa", '"""', "'''", "print(", "log.", "logger.", "raise ", "assert ",
                        "help=", "description=", "epilog=", "message=", "subprocess", "shell=True",
                        "os.system", "f\"", "f'",
                        "status_line(", "card(", "gr.update(", "callback_data=",
                        "InlineKeyboardButton(", "InlineKeyboardMarkup(", "_prompt_int(",
                        "_prompt_bool(", "ask(", "-->", "==>"],
            require_any=["Path(", "open(", "mkdir", "rmdir", "glob(", "os.path"],
        ),
    ]


# ── Escáner ────────────────────────────────────────────────────────────────────

# Archivos/directorios a ignorar
_IGNORE_DIRS = {
    "__pycache__", ".git", "node_modules", ".venv", "venv",
    "state.example", "docs", "knowledge", "prompts",
}
_IGNORE_FILES = {
    "hardcode_detector.py",      # este mismo script
    "legacy_registry.py",        # lista histórica intencionalmente estática
    "EVOLUCION.md",
    "CHANGELOG.md",
}

# Extensiones a escanear
_SCAN_EXTS = {".py"}


def _should_skip_file(path: Path) -> bool:
    if path.name in _IGNORE_FILES:
        return True
    for part in path.parts:
        if part in _IGNORE_DIRS:
            return True
    return False


def _is_comment_or_docstring(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''")


def _scan_file(path: Path, rules: list[Rule], include_low: bool) -> Iterator[Finding]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return

    in_docstring = False
    docstring_char = None

    for lineno, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()

        # Track docstrings (simplified — doesn't handle all edge cases)
        if not in_docstring:
            if stripped.startswith('"""') or stripped.startswith("r\"\"\""):
                if stripped.count('"""') % 2 == 1:  # odd = opens without closing
                    in_docstring = True
                    docstring_char = '"""'
                    continue
            elif stripped.startswith("'''"):
                if stripped.count("'''") % 2 == 1:
                    in_docstring = True
                    docstring_char = "'''"
                    continue
        else:
            if docstring_char and docstring_char in stripped:
                in_docstring = False
            continue

        # Skip pure comments
        if stripped.startswith("#"):
            continue

        # Strip inline comment portion for matching
        code_part = raw_line.split("#")[0]

        for rule in rules:
            if rule.severity == "LOW" and not include_low:
                continue

            # Check require_any: skip rule if none of the required tokens appear
            if rule.require_any and not any(t in code_part for t in rule.require_any):
                continue

            # Check exclude_if: skip rule if any exclusion token appears in the full line
            if any(excl in raw_line for excl in rule.exclude_if):
                continue

            match = rule.pattern.search(code_part)
            if match:
                yield Finding(
                    file=path,
                    line=lineno,
                    category=rule.category,
                    severity=rule.severity,
                    message=rule.message,
                    snippet=raw_line.rstrip(),
                    fix=rule.fix,
                )
                break  # one finding per line per rule group is enough


def _iter_python_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*")):
        if path.suffix not in _SCAN_EXTS:
            continue
        if _should_skip_file(path):
            continue
        yield path


def scan(root: Path, include_low: bool = False, category_filter: str | None = None) -> list[Finding]:
    rules = _build_rules()
    if category_filter:
        rules = [r for r in rules if r.category == category_filter.upper()]

    findings: list[Finding] = []
    for py_file in _iter_python_files(root):
        for f in _scan_file(py_file, rules, include_low):
            findings.append(f)

    return findings


# ── Formateo ──────────────────────────────────────────────────────────────────

_SEV_ICON = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "⚪"}
_SEV_COLOR = {
    "HIGH":   RED,
    "MEDIUM": YELLOW,
    "LOW":    DIM,
}

def _print_findings(findings: list[Finding], summary_only: bool = False) -> None:
    if not findings:
        print(GREEN("✅ Sin hallazgos de datos hardcodeados."))
        return

    if not summary_only:
        # Group by file
        by_file: dict[Path, list[Finding]] = {}
        for f in findings:
            by_file.setdefault(f.file, []).append(f)

        for fpath, file_findings in sorted(by_file.items()):
            rel = fpath.relative_to(REPO_ROOT)
            print()
            print(BOLD(str(rel)))
            for f in sorted(file_findings, key=lambda x: x.line):
                icon  = _SEV_ICON.get(f.severity, "•")
                color = _SEV_COLOR.get(f.severity, DIM)
                print(f"  {icon} L{f.line:4d}  {color(f.category):<12}  {f.message}")
                print(f"         {DIM(f.snippet.strip()[:90])}")
                print(f"         {CYAN('→ ' + f.fix)}")

    # Summary
    print()
    print(BOLD("── Resumen ─────────────────────────────────────────"))
    by_cat: dict[str, list[Finding]] = {}
    by_sev: dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        by_cat.setdefault(f.category, []).append(f)
        by_sev[f.severity] = by_sev.get(f.severity, 0) + 1

    for cat, cat_findings in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        highs  = sum(1 for f in cat_findings if f.severity == "HIGH")
        meds   = sum(1 for f in cat_findings if f.severity == "MEDIUM")
        lows   = sum(1 for f in cat_findings if f.severity == "LOW")
        parts  = []
        if highs:  parts.append(RED(f"{highs}H"))
        if meds:   parts.append(YELLOW(f"{meds}M"))
        if lows:   parts.append(DIM(f"{lows}L"))
        print(f"  {BOLD(cat):<16}  {len(cat_findings):3d} hallazgos  ({', '.join(parts)})")

    print()
    total = len(findings)
    high_count = by_sev["HIGH"]
    med_count  = by_sev["MEDIUM"]
    low_count  = by_sev["LOW"]
    print(f"  Total: {BOLD(str(total))}  —  "
          f"{RED(str(high_count))} HIGH  "
          f"{YELLOW(str(med_count))} MEDIUM  "
          f"{DIM(str(low_count))} LOW")

    exit_code = 1 if high_count > 0 else 0
    if exit_code:
        print(f"\n  {RED('❌ Hay hallazgos HIGH — corrección recomendada.')}")
    else:
        print(f"\n  {GREEN('✅ Sin hallazgos HIGH.')}")


# ── Auto-test ──────────────────────────────────────────────────────────────────

def _self_test() -> None:
    import tempfile, textwrap

    cases = [
        # (description, code, expected_categories, unexpected_categories)
        (
            "python3 en subprocess",
            'subprocess.run(["python3", str(path)])',
            ["INTERPRETER"],
            [],
        ),
        (
            "sys.executable OK",
            'subprocess.run([sys.executable, str(path)])',
            [],
            ["INTERPRETER"],
        ),
        (
            "Ruta absoluta /Users/",
            'x = "/Users/paola/Documents/bago"',
            ["ABS_PATH"],
            [],
        ),
        (
            "Path relativa OK",
            'x = Path(__file__).resolve().parent',
            [],
            ["ABS_PATH"],
        ),
        (
            "Path.cwd() en tool",
            'target = Path.cwd()',
            ["CWD"],
            [],
        ),
        (
            "Puerto hardcodeado sin default=",
            'server.listen(8080)',
            ["PORT"],
            [],
        ),
        (
            "Puerto con default= OK",
            'parser.add_argument("--port", default=8080)',
            [],
            ["PORT"],
        ),
        (
            "Fecha ISO en string de reporte",
            'report_date = "2026-01-15"',
            ["DATE"],
            [],
        ),
        (
            "Acento en subprocess arg",
            'subprocess.run(["cp", "análisis/datos.csv", dst], args)',
            ["ACCENT_PATH"],
            [],
        ),
        (
            "Acento en Path() — MEDIUM",
            'ruta = Path("configuración") / "datos"',
            ["ACCENT_PATH"],
            [],
        ),
        (
            "Acento en mensaje de usuario — OK",
            'print("Error: la configuración es inválida")',
            [],
            ["ACCENT_PATH"],
        ),
    ]

    passed = 0
    failed = 0
    rules  = _build_rules()

    for desc, code, expected, unexpected in cases:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code + "\n")
            tmp = Path(f.name)

        try:
            findings = list(_scan_file(tmp, rules, include_low=True))
            found_cats = {fi.category for fi in findings}

            ok = True
            for cat in expected:
                if cat not in found_cats:
                    print(f"  ❌ FAIL [{desc}]: esperaba {cat}, no encontrado")
                    ok = False
            for cat in unexpected:
                if cat in found_cats:
                    print(f"  ❌ FAIL [{desc}]: no esperaba {cat}, pero se encontró")
                    ok = False
            if ok:
                print(f"  ✅ PASS [{desc}]")
                passed += 1
            else:
                failed += 1
        finally:
            tmp.unlink(missing_ok=True)

    print(f"\n  {passed}/{passed+failed} tests pasaron")
    sys.exit(0 if failed == 0 else 1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]

    if "--test" in args:
        _self_test()
        return

    include_low    = "--strict" in args
    summary_only   = "--summary" in args
    json_output    = "--json" in args

    category_filter: str | None = None
    if "--category" in args:
        idx = args.index("--category")
        if idx + 1 < len(args):
            category_filter = args[idx + 1]

    # Determine root to scan
    positional = [a for a in args if not a.startswith("--")]
    if positional:
        root = Path(positional[0]).resolve()
        if not root.exists():
            print(f"❌ Ruta no encontrada: {root}", file=sys.stderr)
            sys.exit(1)
    else:
        root = BAGO_ROOT   # .bago/ only — not the whole repo

    print(f"  🔍 Escaneando: {root.relative_to(REPO_ROOT) if root.is_relative_to(REPO_ROOT) else root}")
    if category_filter:
        print(f"     Filtro: {category_filter}")
    if include_low:
        print(f"     Modo: strict (incluye LOW)")

    findings = scan(root, include_low=include_low, category_filter=category_filter)

    if json_output:
        print(json.dumps([f.to_dict() for f in findings], ensure_ascii=False, indent=2))
        sys.exit(1 if any(f.severity == "HIGH" for f in findings) else 0)

    _print_findings(findings, summary_only=summary_only)
    sys.exit(1 if any(f.severity == "HIGH" for f in findings) else 0)


if __name__ == "__main__":
    main()
