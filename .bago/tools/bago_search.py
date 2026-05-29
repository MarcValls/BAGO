#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bago_search.py — Búsqueda semántica por palabra clave, sinónimos y metáforas.

Uso:
    python .bago/tools/bago_search.py <palabra_clave> [directorio] [opciones]

Opciones:
    --synonyms          Amplía búsqueda con sinónimos en español/inglés
    --metaphors         Busca metáforas y expresiones relacionadas
    --regex             Trata la palabra clave como regex
    --ext EXT1,EXT2    Filtra por extensiones (default: py,ts,tsx,js,md,json,yaml)
    --max N             Máximo resultados por archivo (default: 10)
    --context C         Líneas de contexto alrededor del match (default: 2)
    --files             Solo nombres de archivo
    --json              Salida en JSON para piping

Códigos de salida: 0 = encontrado, 1 = sin resultados, 2 = error
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Iterable

# ── BAGO shared utils ──
from bago_utils import get_repo_root

ROOT = get_repo_root()

EXCLUDE_DIRS = {"node_modules", "dist", "build", ".next", ".git", ".bago", "out",
                "coverage", ".turbo", "__pycache__", ".pytest_cache", ".mypy_cache",
                "venv", ".venv", "env", ".env"}

DEFAULT_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".yaml", ".yml",
                ".sql", ".css", ".scss", ".html", ".xml", ".toml", ".ini", ".cfg"}

# ── Thesaurus básico (español ↔ inglés) ──
_SYNONYMS: dict[str, list[str]] = {
    # Español
    "inicio": ["start", "comienzo", "principio", "arranque", "boot"],
    "fin": ["end", "final", "terminar", "close", "shutdown", "exit"],
    "error": ["bug", "fallo", "excepción", "exception", "crash", "traceback"],
    "config": ["configuración", "settings", "opciones", "prefs", "properties"],
    "dato": ["data", "información", "info", "payload", "content"],
    "usuario": ["user", "cliente", "account", "login", "session"],
    "red": ["network", "net", "conexión", "socket", "http", "api"],
    "seguridad": ["security", "auth", "safe", "guard", "encrypt", "hash"],
    "archivo": ["file", "documento", "blob", "path", "stream"],
    "base": ["database", "db", "storage", "repo", "sql", "cache"],
    "vista": ["view", "ui", "template", "render", "display", "screen"],
    "control": ["controller", "handler", "manager", "router", "dispatcher"],
    "modelo": ["model", "entity", "schema", "dto", "struct"],
    "servicio": ["service", "worker", "job", "task", "process", "daemon"],
    "test": ["prueba", "spec", "assert", "check", "verify", "unit"],
    "log": ["registro", "trace", "audit", "event", "history", "journal"],
    "sync": ["sincronizar", "replicar", "mirror", "push", "pull", "merge"],
    "buscar": ["search", "find", "query", "filter", "lookup", "seek"],
    "crear": ["create", "new", "add", "insert", "build", "generate"],
    "borrar": ["delete", "remove", "drop", "clear", "destroy", "purge"],
    "actualizar": ["update", "modify", "edit", "patch", "change", "refresh"],
    "leer": ["read", "get", "fetch", "load", "parse", "consume"],
    "escribir": ["write", "save", "store", "dump", "output", "emit"],
    "analizar": ["analyze", "parse", "inspect", "scan", "diagnose", "debug"],
    "conectar": ["connect", "link", "bind", "attach", "join", "hook"],
    "desconectar": ["disconnect", "unlink", "detach", "close", "release"],
    "esperar": ["wait", "sleep", "delay", "pause", "idle", "pending"],
    "notificar": ["notify", "alert", "warn", "signal", "event", "message"],
    "validar": ["validate", "check", "verify", "assert", "sanity", "guard"],
    "convertir": ["convert", "transform", "map", "cast", "serialize", "parse"],
    "comprimir": ["compress", "zip", "pack", "archive", "minify", "gzip"],
    "cifrar": ["encrypt", "encode", "hash", "cipher", "obfuscate", "sign"],
    "descifrar": ["decrypt", "decode", "verify", "decipher", "unwrap"],
}

# ── Metáforas comunes en código ──
_METAPHORS: dict[str, list[str]] = {
    "inicio": ["bootstrap", "ignite", "spark", "seed", "root", "kernel", "origin"],
    "fin": ["terminate", "kill", "halt", "cease", "expire", "die", "end_of_life"],
    "error": ["glitch", "fault", "panic", "break", "rupture", "burn", "smoke"],
    "config": ["blueprint", "recipe", "manifest", "contract", "schema", "spec"],
    "dato": ["grain", "atom", "packet", "chunk", "blob", "token", "record"],
    "usuario": ["persona", "actor", "subject", "principal", "identity", "profile"],
    "red": ["web", "mesh", "fabric", "highway", "pipe", "tunnel", "bridge"],
    "seguridad": ["shield", "wall", "vault", "lock", "gate", "fence", "armor"],
    "archivo": ["scroll", "ledger", "reel", "tape", "document", "sheet"],
    "base": ["vault", "warehouse", "store", "ledger", "repository", "tomb"],
    "vista": ["canvas", "stage", "window", "lens", "portal", "mask"],
    "control": ["helm", "wheel", "switch", "lever", "knob", "pilot"],
    "modelo": ["mold", "template", "pattern", "prototype", "blueprint", "骨架"],
    "servicio": ["engine", "motor", "pump", "boiler", "furnace", "turbine"],
    "test": ["trial", "ordeal", "proof", "checkup", "audit", "inspection"],
    "log": ["diary", "chronicle", "annals", "footprints", "trail", "scent"],
    "sync": ["harmonize", "tune", "align", "calibrate", "match", "resonate"],
    "buscar": ["hunt", "scout", "probe", "survey", "patrol", "scan"],
    "crear": ["forge", "craft", "mint", "spawn", "birth", "bloom"],
    "borrar": ["erase", "wipe", "scrub", "sanitize", "annihilate", "vanish"],
    "actualizar": ["evolve", "mutate", "upgrade", "refine", "polish", "heal"],
    "leer": ["consume", "digest", "ingest", "perceive", "sense", "absorb"],
    "escribir": ["inscribe", "etch", "commit", "burn", "stamp", "seal"],
    "analizar": ["dissect", "probe", "sift", "decipher", "unravel", "autopsy"],
    "conectar": ["fuse", "graft", "wed", "mesh", "solder", "couple"],
    "desconectar": ["sever", "cut", "unplug", "divorce", "detach", "isolate"],
    "esperar": ["hibernate", "lurk", "standby", "queue", "bide", "rest"],
    "notificar": ["whisper", "shout", "ring", "pulse", "beacon", "flare"],
    "validar": ["bless", "certify", "sanctify", "clear", "approve", "stamp"],
    "convertir": ["transmute", "morph", "forge", "render", "distill", "brew"],
    "comprimir": ["squeeze", "crush", "condense", "shrink", "collapse", "implode"],
    "cifrar": ["cloak", "veil", "shroud", "mask", "tangle", "scramble"],
    "descifrar": ["reveal", "unveil", "expose", "untangle", "clarify", "decode"],
}

def _color(code: int, s: str) -> str:
    return f"\033[{code}m{s}\033[0m"

GREEN = lambda s: _color(32, s)
YELLOW = lambda s: _color(33, s)
CYAN = lambda s: _color(36, s)
DIM = lambda s: _color(2, s)
BOLD = lambda s: _color(1, s)
HIGHLIGHT = lambda s: _color(93, s)

def _expand_terms(base_terms: list[str], use_synonyms: bool, use_metaphors: bool) -> list[str]:
    """Expande términos con sinónimos y metáforas."""
    expanded = set(base_terms)
    for term in list(expanded):
        low = term.lower()
        if use_synonyms and low in _SYNONYMS:
            expanded.update(_SYNONYMS[low])
        if use_metaphors and low in _METAPHORS:
            expanded.update(_METAPHORS[low])
    return list(expanded)

def _build_pattern(terms: list[str], use_regex: bool) -> re.Pattern:
    if use_regex:
        return re.compile(terms[0], re.IGNORECASE)
    # Escapar y unir con OR
    escaped = [re.escape(t) for t in terms]
    combined = "|".join(escaped)
    return re.compile(combined, re.IGNORECASE)

def _should_exclude(path: Path, root: Path) -> bool:
    try:
        parts = set(path.relative_to(root).parts)
        return bool(parts & EXCLUDE_DIRS)
    except ValueError:
        return False

def _search_file(path: Path, pattern: re.Pattern, max_matches: int, context_lines: int) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (PermissionError, OSError):
        return []
    lines = text.splitlines()
    results = []
    for i, line in enumerate(lines, 1):
        m = pattern.search(line)
        if not m:
            continue
        start = max(0, i - 1 - context_lines)
        end = min(len(lines), i + context_lines)
        ctx = [(j + 1, lines[j]) for j in range(start, end)]
        results.append({
            "line": i,
            "text": line.rstrip(),
            "match": m.group(0),
            "context": ctx,
        })
        if len(results) >= max_matches:
            break
    return results

def _collect_files(root: Path, exts: set[str]) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in exts:
            continue
        if _should_exclude(p, root):
            continue
        yield p

def _highlight(line: str, pattern: re.Pattern) -> str:
    def repl(m: re.Match) -> str:
        return HIGHLIGHT(m.group(0))
    try:
        return pattern.sub(repl, line)
    except Exception:
        return line

def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    keyword = args[0]
    search_dir = ROOT
    use_synonyms = "--synonyms" in args
    use_metaphors = "--metaphors" in args
    use_regex = "--regex" in args
    files_only = "--files" in args
    json_out = "--json" in args
    max_matches = 10
    context_lines = 2
    exts = DEFAULT_EXTS.copy()

    # Parse directory argument if provided (first non-flag after keyword)
    for arg in args[1:]:
        if arg.startswith("-"):
            continue
        candidate = Path(arg)
        if candidate.exists() and candidate.is_dir():
            search_dir = candidate.resolve()
            break

    # Parse --ext
    for i, arg in enumerate(args):
        if arg == "--ext" and i + 1 < len(args):
            exts = set(f"." + e.lstrip(".") for e in args[i + 1].split(","))
    # Parse --max
    for i, arg in enumerate(args):
        if arg == "--max" and i + 1 < len(args):
            try:
                max_matches = int(args[i + 1])
            except ValueError:
                pass
    # Parse --context
    for i, arg in enumerate(args):
        if arg == "--context" and i + 1 < len(args):
            try:
                context_lines = int(args[i + 1])
            except ValueError:
                pass

    base_terms = [keyword]
    if not use_regex:
        # Also add normalized versions
        base_terms.append(keyword.lower())
        if keyword.lower() != keyword:
            base_terms.append(keyword)

    terms = _expand_terms(base_terms, use_synonyms, use_metaphors)
    pattern = _build_pattern(terms, use_regex)

    matches_by_file: list[dict] = []
    total_matches = 0

    for fpath in _collect_files(search_dir, exts):
        file_results = _search_file(fpath, pattern, max_matches, context_lines)
        if file_results:
            total_matches += len(file_results)
            matches_by_file.append({
                "file": str(fpath.relative_to(search_dir)),
                "absolute": str(fpath),
                "count": len(file_results),
                "matches": file_results,
            })

    if not matches_by_file:
        if not json_out:
            print(DIM("Sin resultados."))
        else:
            print(json.dumps({"results": [], "total": 0, "terms": terms}, ensure_ascii=False))
        return 1

    if json_out:
        print(json.dumps({
            "results": matches_by_file,
            "total": total_matches,
            "terms": terms,
            "pattern": pattern.pattern,
        }, ensure_ascii=False, indent=2))
        return 0

    if files_only:
        for entry in matches_by_file:
            print(CYAN(entry["file"]))
        return 0

    # Pretty print
    print(BOLD(f"🔍 BAGO Search: {keyword}") + DIM(f"  ({total_matches} matches en {len(matches_by_file)} archivos)"))
    if use_synonyms or use_metaphors:
        print(DIM(f"   Términos expandidos: {', '.join(terms[:12])}" + ("…" if len(terms) > 12 else "")))
    print()

    for entry in matches_by_file:
        print(CYAN(entry["file"]) + DIM(f"  ({entry['count']} matches)"))
        for m in entry["matches"]:
            print(f"  {DIM(str(m['line']).rjust(4))}  {_highlight(m['text'], pattern)}")
            if context_lines > 0:
                for ctx_line_num, ctx_line in m["context"]:
                    if ctx_line_num == m["line"]:
                        continue
                    print(f"      {DIM(str(ctx_line_num).rjust(4))}  {DIM(ctx_line.rstrip())}")
        print()

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
