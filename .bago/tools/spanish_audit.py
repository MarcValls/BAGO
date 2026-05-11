#!/usr/bin/env python3
"""spanish_audit.py — Detecta inconsistencias ortográficas en español que rompen código.

Detecta en strings estructurales (claves de dict, args de Path(), nombres de comando):
  ACCENT_CONFLICT  — misma palabra con y sin tilde en contextos equivalentes
                     ej: COMMAND_MAP["configuracion"] vs Path("configuración")
  PLURAL_CONFLICT  — misma raíz en singular/plural como clave/ruta/comando (opt-in)
                     ej: config["tarea"] vs config["tareas"] en el mismo archivo

Usa análisis AST para distinguir strings estructurales de prose (mensajes, docstrings).
Suprime hallazgos en líneas con # noqa.

Uso:
    python spanish_audit.py [path]          # escanea .bago (ACCENT_CONFLICT por defecto)
    python spanish_audit.py --plural        # también muestra PLURAL_CONFLICT
    python spanish_audit.py --test          # self-tests
    python spanish_audit.py --json          # salida JSON
    python spanish_audit.py --summary       # sólo resumen
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
import tempfile
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ── Configuración ──────────────────────────────────────────────────────────────

_IGNORE_DIRS  = {"__pycache__", ".git", "node_modules", ".venv", "venv", "state.example", "docs"}
_IGNORE_FILES = {"spanish_audit.py"}
_MIN_WORD_LEN = 3   # mínimo para comparar palabras

# Nombres de función que indican contexto de ruta/archivo
_PATH_FUNCS = {
    "Path", "open", "mkdir", "rmdir", "glob", "touch",
    "write_text", "read_text", "joinpath", "join",
}
# Nombres de función que indican contexto de comando/subcomando
_CMD_FUNCS = {
    "add_parser", "add_argument", "add_subparsers",
    "register", "dispatch",
}
# Variables cuyo nombre sugiere que su valor es una clave/ruta
_KEY_HINTS = {
    "path", "dir", "file", "key", "cmd", "command", "route",
    "endpoint", "slug", "id", "name", "module",
}


# Pares singular/plural que son semánticamente DISTINTOS por diseño (no reportar)
# (la raíz canónica, sin acento, sin plural)
_PLURAL_WHITELIST: frozenset[str] = frozenset({
    # Inglés — colección vs elemento son conceptos distintos
    "file", "type", "rule", "node", "line", "issue", "role", "size",
    "name", "close", "merge", "address", "change", "event", "error",
    "page", "tag", "scope", "item", "step", "stage", "phase", "block",
    "note", "test", "task", "mode", "flag", "hook", "link", "port",
    "user", "group", "class", "model", "route", "patch", "field",
    # Inglés técnico común
    "argument", "parameter", "option", "command", "module", "import",
    "package", "require", "depend", "version", "release", "commit",
    "branch", "remote", "origin", "target", "source",
    # Español — pares con semántica diferenciada
    "idea",      # idea = single, ideas = collection (diseño del schema BAGO)
    "archivo",   # archivo vs archivos en contextos de colección/item
    "tarea",     # tarea = single (returned item), tareas = collection (endpoint)
})


# ── Utilidades de texto ────────────────────────────────────────────────────────

def _strip_accents(text: str) -> str:
    """Devuelve text sin diacríticos: 'configuración' → 'configuracion'."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def _has_accent(text: str) -> bool:
    return bool(re.search(r'[áéíóúñüÁÉÍÓÚÑÜ]', text))


def _tokenize(s: str) -> list[str]:
    """Divide un string en tokens de palabras: 'project-init' → ['project', 'init']."""
    parts = re.split(r'[-_/. ]', s.lower())
    return [p for p in parts if len(p) >= _MIN_WORD_LEN and p.isalpha()]


def _plural_root(word: str) -> str | None:
    """Devuelve la raíz singular si la palabra parece un plural español, o None.

    Reglas (conservadoras — evita falsos positivos con palabras inglesas):
      - 'usuarios' → 'usuario'  (termina en vocal + s)
      - 'controles' → 'control'  (termina en consonante + es, raíz ≥ 5 chars)
      - 'siembras' → 'siembra'  (termina en vocal + as)
    """
    w = word.lower()
    # Plural de vocal + es: 'controles' → 'control' (raíz mínima 5 para evitar 'not' de 'notes')
    if w.endswith("es") and len(w) > 6 and w[-3] not in "aeiou":
        root = w[:-2]
        if len(root) >= 4:
            return root
    # Plural de vocal + s: 'usuarios' → 'usuario', 'tareas' → 'tarea'
    if w.endswith("s") and len(w) > 4 and w[-2] in "aeiou":
        return w[:-1]
    return None


# ── Extractor AST ──────────────────────────────────────────────────────────────

@dataclass
class StrToken:
    """String literal encontrado en contexto estructural."""
    value:    str     # valor original del string
    context:  str     # "dict_key" | "subscript" | "path_arg" | "command" | "assignment"
    filepath: Path
    line:     int


class StructuralFinder(ast.NodeVisitor):
    """Recorre el AST y recolecta strings en contextos estructurales."""

    def __init__(self, filepath: Path, source_lines: list[str]) -> None:
        self.filepath     = filepath
        self.source_lines = source_lines
        self.tokens: list[StrToken] = []

    def _line_has_noqa(self, lineno: int) -> bool:
        """True si la línea fuente contiene # noqa (supresión explícita)."""
        try:
            return "# noqa" in self.source_lines[lineno - 1]
        except IndexError:
            return False

    def _add(self, node: ast.Constant, context: str) -> None:
        if not isinstance(node.value, str):
            return
        if self._line_has_noqa(node.lineno):
            return
        val = node.value.strip()
        # Ignorar: muy corto, número, prose (contiene espacios o puntuación de frase)
        if len(val) < _MIN_WORD_LEN:
            return
        if re.search(r'[.!?]$|^\d', val):
            return
        # Ignorar strings con muchos espacios (frases completas)
        if val.count(" ") > 3:
            return
        self.tokens.append(StrToken(
            value=val, context=context, filepath=self.filepath, line=node.lineno
        ))

    def visit_Dict(self, node: ast.Dict) -> None:
        """Claves de dict literal: {"configuracion": ..., "usuario": ...}"""
        for key in node.keys:
            if isinstance(key, ast.Constant):
                self._add(key, "dict_key")
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        """Acceso por clave: config["configuracion"], COMMAND_MAP["init"]"""
        sl = node.slice
        if isinstance(sl, ast.Constant):
            self._add(sl, "subscript")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Llamadas: Path("ruta"), open("archivo"), add_parser("nombre")"""
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name in _PATH_FUNCS:
            for arg in node.args:
                if isinstance(arg, ast.Constant):
                    self._add(arg, "path_arg")
        elif func_name in _CMD_FUNCS:
            for arg in node.args[:1]:   # primer argumento = nombre
                if isinstance(arg, ast.Constant):
                    self._add(arg, "command")

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Asignaciones cuyo target contiene hints de clave/ruta."""
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            name_lower = target.id.lower()
            if not any(hint in name_lower for hint in _KEY_HINTS):
                continue
            if isinstance(node.value, ast.Constant):
                self._add(node.value, "assignment")
            elif isinstance(node.value, (ast.List, ast.Tuple)):
                for elt in node.value.elts:
                    if isinstance(elt, ast.Constant):
                        self._add(elt, "assignment")
        self.generic_visit(node)


def _collect_tokens(filepath: Path) -> list[StrToken]:
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree   = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []
    lines  = source.splitlines()
    finder = StructuralFinder(filepath, lines)
    finder.visit(tree)
    return finder.tokens


# ── Detección de conflictos ────────────────────────────────────────────────────

@dataclass
class Conflict:
    kind:     str           # "ACCENT_CONFLICT" | "PLURAL_CONFLICT"
    severity: str           # "MEDIUM"
    canonical: str          # forma normalizada (sin acento, singular)
    variants: list[str]     # variantes encontradas
    occurrences: list[tuple[Path, int, str, str]]  # (file, line, variant, context)

    @property
    def message(self) -> str:
        vs = " / ".join(f'"{v}"' for v in sorted(set(self.variants)))
        if self.kind == "ACCENT_CONFLICT":
            return f'Misma palabra con y sin tilde: {vs}'
        return f'Singular/plural como clave/ruta: {vs}'

    @property
    def fix(self) -> str:
        if self.kind == "ACCENT_CONFLICT":
            canon = _strip_accents(self.canonical)
            return f'Normaliza a una sola forma: "{canon}" (ASCII) o "{self.canonical}" (con tilde) — usa siempre la misma'
        return f'Decide una sola forma para "{self.canonical}" y úsala en todos los contextos'


def _find_accent_conflicts(tokens: list[StrToken]) -> list[Conflict]:
    """Detecta la misma palabra usada con y sin tilde en contextos estructurales equivalentes."""
    # canonical (sin acento, lowercase) → {variant → [(file, line, context)]}
    index: dict[str, dict[str, list[tuple[Path, int, str]]]] = defaultdict(lambda: defaultdict(list))

    for tok in tokens:
        for word in _tokenize(tok.value):
            if not _has_accent(word) and _strip_accents(word) == word:
                # sin acento — registrar de todas formas
                canon = word.lower()
            else:
                canon = _strip_accents(word.lower())
            # sólo palabras que contienen o pueden tener acento español
            if not re.search(r'[aeiouns]', canon):
                continue
            variant = word.lower()
            index[canon][variant].append((tok.filepath, tok.line, tok.context))

    conflicts = []
    for canon, variants_map in index.items():
        # Conflicto sólo si hay 2+ variantes DISTINTAS (una con acento, otra sin)
        accent_variants   = [v for v in variants_map if _has_accent(v)]
        noaccent_variants = [v for v in variants_map if not _has_accent(v)]
        if not (accent_variants and noaccent_variants):
            continue
        # Sólo reportar si aparecen en contextos equivalentes (ambos como clave o ruta)
        structural_ctxs = {"dict_key", "subscript", "path_arg", "command", "assignment"}
        all_occs = []
        for v, occs in variants_map.items():
            for (fp, ln, ctx) in occs:
                if ctx in structural_ctxs:
                    all_occs.append((fp, ln, v, ctx))
        if len(all_occs) < 2:
            continue
        # Verificar que AMBAS variantes (con y sin acento) tengan al menos 1 ocurrencia estructural
        has_struct_accent   = any(v for (_, _, v, _) in all_occs if _has_accent(v))
        has_struct_noaccent = any(v for (_, _, v, _) in all_occs if not _has_accent(v))
        if not (has_struct_accent and has_struct_noaccent):
            continue
        # Deduplica ocurrencias por (file, line, variant)
        seen: set[tuple] = set()
        deduped = []
        for occ in all_occs:
            key = (occ[0], occ[1], occ[2])
            if key not in seen:
                seen.add(key)
                deduped.append(occ)
        conflicts.append(Conflict(
            kind="ACCENT_CONFLICT",
            severity="MEDIUM",
            canonical=canon,
            variants=list(variants_map.keys()),
            occurrences=deduped,
        ))

    return conflicts


def _find_plural_conflicts(tokens: list[StrToken]) -> list[Conflict]:
    """Detecta singular/plural del mismo concepto como clave/ruta/comando.

    Solo reporta cuando AMBAS formas (singular y plural) aparecen en el mismo archivo.
    """
    structural_ctxs = {"dict_key", "subscript", "path_arg", "command"}

    # (canonical_root, filepath) → {variant → [(file, line, context)]}
    index: dict[tuple[str, str], dict[str, list[tuple[Path, int, str]]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for tok in tokens:
        if tok.context not in structural_ctxs:
            continue
        for word in _tokenize(tok.value):
            word_nc = _strip_accents(word.lower())
            root    = _plural_root(word_nc) or word_nc
            key     = (root, str(tok.filepath))
            index[key][word_nc].append((tok.filepath, tok.line, tok.context))

    conflicts = []
    for (root, _fpath), variants_map in index.items():
        if len(variants_map) < 2:
            continue
        if root in _PLURAL_WHITELIST:
            continue
        singular_forms = [v for v in variants_map if v == root]
        plural_forms   = [v for v in variants_map if v != root]
        if not (singular_forms and plural_forms):
            continue
        # Contextos compartidos
        ctx_singular = {ctx for v in singular_forms for (_, _, ctx) in variants_map[v]}
        ctx_plural   = {ctx for v in plural_forms   for (_, _, ctx) in variants_map[v]}
        shared_ctx   = ctx_singular & ctx_plural
        if not shared_ctx:
            continue
        all_occs = []
        for v, occs in variants_map.items():
            for (fp, ln, ctx) in occs:
                if ctx in shared_ctx:
                    all_occs.append((fp, ln, v, ctx))
        seen: set[tuple] = set()
        deduped = []
        for occ in all_occs:
            key2 = (occ[0], occ[1], occ[2])
            if key2 not in seen:
                seen.add(key2)
                deduped.append(occ)
        conflicts.append(Conflict(
            kind="PLURAL_CONFLICT",
            severity="MEDIUM",
            canonical=root,
            variants=list(variants_map.keys()),
            occurrences=deduped,
        ))

    return conflicts


# ── Escáner principal ──────────────────────────────────────────────────────────

def _iter_py_files(root: Path) -> Iterator[Path]:
    for p in sorted(root.rglob("*.py")):
        if p.name in _IGNORE_FILES:
            continue
        if any(part in _IGNORE_DIRS for part in p.parts):
            continue
        yield p


def scan(root: Path) -> tuple[list[Conflict], list[Conflict]]:
    """Escanea root y devuelve (accent_conflicts, plural_conflicts)."""
    all_tokens: list[StrToken] = []
    for py_file in _iter_py_files(root):
        all_tokens.extend(_collect_tokens(py_file))

    accent   = _find_accent_conflicts(all_tokens)
    plural   = _find_plural_conflicts(all_tokens)
    return accent, plural


# ── Salida ─────────────────────────────────────────────────────────────────────

_CYAN   = "\033[36m"
_YELLOW = "\033[33m"
_BOLD   = "\033[1m"
_RESET  = "\033[0m"


def _print_conflict(c: Conflict, root: Path) -> None:
    icon  = "🟡"
    color = _YELLOW
    print(f"\n{color}{_BOLD}[{c.kind}]{_RESET}  {icon} {c.message}")
    print(f"  {_CYAN}Canónico:{_RESET} {c.canonical}")
    print(f"  {_CYAN}Arreglo:{_RESET}  {c.fix}")
    for fp, ln, variant, ctx in sorted(c.occurrences, key=lambda x: (str(x[0]), x[1])):
        try:
            rel = fp.relative_to(root)
        except ValueError:
            rel = fp
        print(f"    {rel}:{ln}  [{ctx}]  \"{variant}\"")


def _to_dict(c: Conflict) -> dict:
    return {
        "kind":      c.kind,
        "severity":  c.severity,
        "canonical": c.canonical,
        "variants":  sorted(set(c.variants)),
        "message":   c.message,
        "fix":       c.fix,
        "occurrences": [
            {"file": str(fp), "line": ln, "variant": v, "context": ctx}
            for fp, ln, v, ctx in c.occurrences
        ],
    }


# ── Self-tests ─────────────────────────────────────────────────────────────────

def _run_tests() -> int:
    """Devuelve 0 si todos los tests pasan, 1 si alguno falla."""

    def _write(code: str) -> Path:
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        )
        f.write(code + "\n")
        f.close()
        return Path(f.name)

    cases = [
        # ── ACCENT_CONFLICT ───────────────────────────────────────────────────
        (
            "Conflicto tilde en claves de dict",
            """
x = {"configuracion": 1}
y = {"configuración": 2}
""",
            ["ACCENT_CONFLICT"],
            [],
        ),
        (
            "Conflicto tilde path_arg",
            """
from pathlib import Path
a = Path("analisis")
b = Path("análisis")
""",
            ["ACCENT_CONFLICT"],
            [],
        ),
        (
            "Sin conflicto — sólo prose en print",
            """
print("configuración correcta")
print("configuracion")
""",
            [],
            ["ACCENT_CONFLICT"],
        ),
        (
            "Sin conflicto — un solo variant",
            """
x = {"usuario": 1}
y = {"usuario": 2}
""",
            [],
            ["ACCENT_CONFLICT"],
        ),
        # ── PLURAL_CONFLICT ───────────────────────────────────────────────────
        (
            "Conflicto singular/plural en dict_key",
            """
a = {"usuario": "x"}
b = {"usuarios": "y"}
""",
            ["PLURAL_CONFLICT"],
            [],
        ),
        (
            "Conflicto singular/plural en subscript",
            """
x = config["proyecto"]
y = config["proyectos"]
""",
            ["PLURAL_CONFLICT"],
            [],
        ),
        (
            "Sin conflicto plural — contextos distintos (prose)",
            """
x = {"usuario": 1}
print("los usuarios están listos")
""",
            [],
            ["PLURAL_CONFLICT"],
        ),
    ]

    passed = 0
    failed = 0

    for desc, code, expected, unexpected in cases:
        f1 = _write(code)
        f2 = _write(code)   # dos archivos para simular escenario cross-file
        try:
            tokens = _collect_tokens(f1) + _collect_tokens(f2)
            accent  = _find_accent_conflicts(tokens)
            plural  = _find_plural_conflicts(tokens)
            all_kinds = {c.kind for c in accent + plural}

            ok = True
            for kind in expected:
                if kind not in all_kinds:
                    print(f"  ❌ FAIL [{desc}]: esperaba {kind}, no encontrado")
                    ok = False
            for kind in unexpected:
                if kind in all_kinds:
                    print(f"  ❌ FAIL [{desc}]: {kind} no debería reportarse")
                    ok = False
            if ok:
                print(f"  ✅ PASS [{desc}]")
                passed += 1
            else:
                failed += 1
        finally:
            f1.unlink(missing_ok=True)
            f2.unlink(missing_ok=True)

    total = passed + failed
    print(f"  {passed}/{total} tests pasaron")
    return 0 if failed == 0 else 1


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]

    if "--test" in args:
        sys.exit(_run_tests())

    as_json      = "--json"    in args
    summary      = "--summary" in args
    show_plural  = "--plural"  in args
    path_arg     = next((a for a in args if not a.startswith("--")), None)

    if path_arg:
        root = Path(path_arg)
    else:
        here = Path(__file__).resolve()
        root = here.parent.parent   # .bago/

    if not root.exists():
        print(f"❌ Ruta no encontrada: {root}", file=sys.stderr)
        sys.exit(1)

    if not as_json:
        print(f"🔍 Escaneando: {root}\n")

    accent_cs, plural_cs = scan(root)
    all_conflicts = accent_cs + (plural_cs if show_plural else [])

    if as_json:
        print(json.dumps(
            {"root": str(root), "conflicts": [_to_dict(c) for c in all_conflicts],
             "plural_suppressed": len(plural_cs) if not show_plural else 0},
            ensure_ascii=False, indent=2,
        ))
        sys.exit(0 if not all_conflicts else 1)

    if not summary:
        for c in sorted(all_conflicts, key=lambda x: x.kind):
            _print_conflict(c, root)
        if all_conflicts:
            print()

    # Resumen
    accent_n  = len(accent_cs)
    plural_n  = len(plural_cs) if show_plural else 0
    total     = accent_n + plural_n
    print("── Resumen " + "─" * 48)
    if accent_n:
        print(f"  ACCENT_CONFLICT   {accent_n} conflictos")
    if show_plural and plural_n:
        print(f"  PLURAL_CONFLICT   {plural_n} conflictos")
    elif not show_plural and plural_cs:
        sup = len(plural_cs)
        print(f"  PLURAL_CONFLICT   {sup} posibles (usa --plural para ver)")
    if total == 0 and not plural_cs:
        print("  Total: 0  ✅ Sin conflictos ortográficos.")
    elif total == 0:
        print(f"  ✅ Sin conflictos de acento. {len(plural_cs)} plural posibles (--plural).")
    else:
        print(f"\n  Total: {total} conflictos  ⚠️  Revisar consistencia ortográfica.")

    sys.exit(0 if not accent_cs else 1)


if __name__ == "__main__":
    main()
