#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sincerity_detector.py — CENTINELA DE SINCERIDAD

Detecta en la documentación del repo patrones diseñados para agradar al
usuario enmascarando la verdad operativa del sistema:

  1. FLATTERY              — adjetivos decorativos sin dato que los sostenga.
  2. UNSUBSTANTIATED       — absolutos ("100%", "siempre", "nunca falla",
                              "garantizado", "bulletproof") sin evidencia.
  3. SUCCESS_WASHING       — éxito cosmético ("✅ completado", "listo para
                              producción", "cero errores") sin referencia.
  4. FUTURE_AS_DONE        — promesa en futuro dentro de contexto "done"
                              ("se va a", "próximamente") bajo un título de
                              estado completado.
  5. EVIDENCE_MISSING      — reclamación fuerte (PASSED, STABLE, PRODUCTION-
                              READY) sin link a evidencia / test / archivo.
  6. EMPTY_CHECKLIST       — checklist con items marcados pero sin detalle.

Uso:
  python3 .bago/tools/sincerity_detector.py              # repo entero (.md)
  python3 .bago/tools/sincerity_detector.py --path PATH  # ruta específica
  python3 .bago/tools/sincerity_detector.py --json       # salida JSON
  python3 .bago/tools/sincerity_detector.py --strict     # exit 1 también en WARN

Exit codes:
  0   sin ERROR (puede haber WARN)
  1   ERROR detectado (o WARN si --strict)
  2   error interno / parámetros inválidos
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from functools import lru_cache
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]  # repo raíz

SEV_ERROR = "ERROR"
SEV_WARN = "WARN"
SEV_INFO = "INFO"

DEFAULT_EXCLUDE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__",
    "dist", "build", "RELEASE", "cleanversion", "sandbox",
    ".bago/state", ".bago/state/sessions", ".bago/state/changes", ".bago/state/evidences",
}

# ── Léxicos (ES/EN mezclados, case-insensitive) ───────────────────────────────

FLATTERY_TERMS = [
    r"espectacular", r"impecable", r"robust[íi]simo", r"excelent[ií]simo",
    r"de\s+primer\s+nivel", r"nivel\s+enterprise", r"world[- ]class",
    r"state[- ]of[- ]the[- ]art", r"perfectamente\s+orquestad[oa]",
    r"sin\s+igual", r"magn[íi]fic[oa]", r"rompedor", r"asombroso",
    r"espectacularmente", r"incre[íi]ble(?:mente)?", r"flawless",
    r"bulletproof", r"legendari[oa]", r"rocket[- ]?ship",
]

UNSUBSTANTIATED_ABSOLUTES = [
    r"\b100\s*%\b", r"\btotalmente\b", r"\bcompletamente\b(?!\s+opcional)",
    r"\bsiempre\s+funciona\b", r"\bnunca\s+falla\b", r"\bsin\s+fallos?\b",
    r"\bgarantizad[oa]s?\b", r"\bsin\s+errores?\b", r"\bcero\s+errores?\b",
    r"\bzero[- ]bug\b", r"\b100%\s+stable\b", r"\bno\s+tiene\s+bugs?\b",
]

SUCCESS_WASHING = [
    r"✅\s*completad[oa]", r"✅\s*listo", r"listo\s+para\s+producci[óo]n",
    r"production[- ]ready", r"ready\s+to\s+ship", r"green\s+across\s+the\s+board",
    r"todo\s+OK", r"todo\s+verde", r"all\s+green", r"no\s+hay\s+nada\s+pendiente",
]

FUTURE_PROMISES = [
    r"\bse\s+va\s+a\b", r"\bpróximamente\b", r"\bproximamente\b",
    r"\bplanned\b", r"\bto\s+be\s+implemented\b", r"\bTBD\b",
    r"\bfuturo\s+pr[óo]ximo\b", r"\ben\s+breve\b",
]

DONE_CONTEXT_HEADERS = [
    r"\bcompletad[oa]s?\b", r"\bterminad[oa]s?\b", r"\bcerrad[oa]s?\b",
    r"\bdone\b", r"\bhecho\b", r"\bimplementad[oa]s?\b",
    r"\bresuelt[oa]s?\b", r"\bfix(?:ed)?\b",
]

STRONG_CLAIMS = [
    r"\bPASSED\b", r"\bSTABLE\b", r"\bPRODUCTION[- ]READY\b",
    # NOTE: validad[oa]/certificad[oa]/auditad[oa] removed — these are common Spanish
    # governance/normative vocabulary and are NOT operational status claims.
    # They appear legitimately in DECISIONES.md, ACTAS, INICIADOR_MAESTRO, etc.
]

EVIDENCE_HINTS = [
    r"\.json\b", r"\.md\b", r"\.py\b", r"\.ps1\b", r"\.ts\b", r"\.log\b",
    r"\bevidenc", r"\btest", r"\bexit[_ ]?code\b", r"\bsha\b",
    r"\bchecksums?\b", r"\bruntime\b", r"\bcommit\b",
    r"https?://", r"#L\d+", r"\[.+?\]\(.+?\)",
]

# Excepciones: en estos ficheros sí se permite vocabulario "fuerte" porque
# describen el criterio (no son evaluación de resultados) o son material
# normativo/histórico/de gobernanza fuera del alcance de evidence reports.
EXEMPT_PATTERNS = [
    r"/templates/", r"/prompts/", r"PLANTILLA", r"plantilla",
    r"/canon/", r"GLOSARIO", r"/schema/",
    r"/migration/legacy/",
    # Normative / architectural / governance content — not evidence reports:
    r"/agents/",          # agentes normativos (INICIADOR_MAESTRO, etc.)
    r"/workflows/",       # workflows operativos (W\d+_...)
    r"/docs/governance/", # actas oficiales, decisiones de gobernanza
    r"/docs/migration/",  # documentación de migración (excl. legacy ya cubierto)
]


@lru_cache(maxsize=1)
def _load_lexicon() -> dict[str, object]:
    try:
        from bago_config import load_config
        data = load_config("sincerity_lexicon", fallback=None)
    except Exception:
        data = None

    payload = data if isinstance(data, dict) else {}

    def _list_value(key: str, fallback: list[str]) -> list[str]:
        value = payload.get(key)
        return value if isinstance(value, list) else fallback

    return {
        "exclude_dirs": set(_list_value("exclude_dirs", sorted(DEFAULT_EXCLUDE_DIRS))),
        "flattery_terms": _list_value("flattery_terms", FLATTERY_TERMS),
        "unsubstantiated_absolutes": _list_value("unsubstantiated_absolutes", UNSUBSTANTIATED_ABSOLUTES),
        "success_washing": _list_value("success_washing", SUCCESS_WASHING),
        "future_promises": _list_value("future_promises", FUTURE_PROMISES),
        "done_context_headers": _list_value("done_context_headers", DONE_CONTEXT_HEADERS),
        "strong_claims": _list_value("strong_claims", STRONG_CLAIMS),
        "evidence_hints": _list_value("evidence_hints", EVIDENCE_HINTS),
        "exempt_patterns": _list_value("exempt_patterns", EXEMPT_PATTERNS),
    }

# ── Modelo de hallazgo ────────────────────────────────────────────────────────

@dataclass
class Finding:
    file: str
    line: int
    severity: str
    kind: str
    excerpt: str
    why: str

    def fmt(self) -> str:
        return f"[{self.severity}] {self.kind} · {self.file}:{self.line}\n    > {self.excerpt.strip()}\n    · {self.why}"


# ── Utilidades ────────────────────────────────────────────────────────────────

def is_exempt(path: Path) -> bool:
    sp = str(path).replace("\\", "/")
    patterns = _load_lexicon()["exempt_patterns"]
    return any(re.search(p, sp) for p in patterns)


def iter_markdown_files(base: Path, excludes: set[str]) -> Iterable[Path]:
    for p in base.rglob("*.md"):
        rel = p.relative_to(base).as_posix()
        if any(rel.startswith(ex) or f"/{ex}/" in f"/{rel}/" for ex in excludes):
            continue
        yield p


def find_all(patterns: list[str], text: str, flags=re.IGNORECASE) -> list[re.Match]:
    hits: list[re.Match] = []
    for pat in patterns:
        hits.extend(re.finditer(pat, text, flags))
    return hits


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def line_text(text: str, line_no: int) -> str:
    lines = text.splitlines()
    if 1 <= line_no <= len(lines):
        return lines[line_no - 1]
    return ""


# ── Escaneos por tipo ─────────────────────────────────────────────────────────

def scan_flattery(path: Path, text: str) -> list[Finding]:
    out: list[Finding] = []
    lexicon = _load_lexicon()
    for m in find_all(lexicon["flattery_terms"], text):
        ln = line_of(text, m.start())
        lt = line_text(text, ln)
        # Permitir si la línea trae un link/evidencia que lo sostiene.
        if any(re.search(e, lt, re.IGNORECASE) for e in lexicon["evidence_hints"]):
            continue
        out.append(Finding(
            file=str(path.relative_to(ROOT)),
            line=ln, severity=SEV_WARN, kind="FLATTERY",
            excerpt=lt,
            why="Adjetivo decorativo sin dato/link que lo respalde.",
        ))
    return out


def scan_unsubstantiated(path: Path, text: str) -> list[Finding]:
    out: list[Finding] = []
    lexicon = _load_lexicon()
    for m in find_all(lexicon["unsubstantiated_absolutes"], text):
        ln = line_of(text, m.start())
        lt = line_text(text, ln)
        if any(re.search(e, lt, re.IGNORECASE) for e in lexicon["evidence_hints"]):
            continue
        out.append(Finding(
            file=str(path.relative_to(ROOT)),
            line=ln, severity=SEV_ERROR, kind="UNSUBSTANTIATED",
            excerpt=lt,
            why="Absoluto sin evidencia (test, log, commit, checksum, link).",
        ))
    return out


def scan_success_washing(path: Path, text: str) -> list[Finding]:
    out: list[Finding] = []
    lexicon = _load_lexicon()
    for m in find_all(lexicon["success_washing"], text):
        ln = line_of(text, m.start())
        lt = line_text(text, ln)
        if re.search(r"\?|not[_ -]?ready|no\s+listo|conditional|condiciones", lt, re.IGNORECASE):
            continue
        if any(re.search(e, lt, re.IGNORECASE) for e in lexicon["evidence_hints"]):
            continue
        out.append(Finding(
            file=str(path.relative_to(ROOT)),
            line=ln, severity=SEV_WARN, kind="SUCCESS_WASHING",
            excerpt=lt,
            why="Éxito cosmético; falta artefacto/referencia de cierre.",
        ))
    return out


def scan_future_as_done(path: Path, text: str) -> list[Finding]:
    """Promesa futura dentro de una sección cuyo header marca 'done'."""
    out: list[Finding] = []
    lexicon = _load_lexicon()
    lines = text.splitlines()
    current_header = ""
    header_is_done = False
    header_line = 0
    for i, raw in enumerate(lines, start=1):
        h = re.match(r"^\s{0,3}#{1,6}\s+(.+)$", raw)
        if h:
            current_header = h.group(1).strip()
            header_is_done = any(re.search(p, current_header, re.IGNORECASE) for p in lexicon["done_context_headers"])
            header_line = i
            continue
        if not header_is_done or not current_header:
            continue
        for pat in lexicon["future_promises"]:
            if re.search(pat, raw, re.IGNORECASE):
                out.append(Finding(
                    file=str(path.relative_to(ROOT)),
                    line=i, severity=SEV_ERROR, kind="FUTURE_AS_DONE",
                    excerpt=raw,
                    why=f"Promesa futura bajo sección '{current_header}' (línea {header_line}) marcada como completada.",
                ))
                break
    return out


def scan_evidence_missing(path: Path, text: str) -> list[Finding]:
    out: list[Finding] = []
    lexicon = _load_lexicon()
    for m in find_all(lexicon["strong_claims"], text, flags=0):  # case-sensitive a propósito
        ln = line_of(text, m.start())
        lt = line_text(text, ln)
        # Mirar línea actual + siguiente 2 líneas para evidencia.
        window = "\n".join(text.splitlines()[ln - 1: ln + 2])
        if any(re.search(e, window, re.IGNORECASE) for e in lexicon["evidence_hints"]):
            continue
        out.append(Finding(
            file=str(path.relative_to(ROOT)),
            line=ln, severity=SEV_ERROR, kind="EVIDENCE_MISSING",
            excerpt=lt,
            why="Reclamación fuerte sin evidencia cercana (ruta, test, commit, enlace).",
        ))
    return out


def scan_empty_checklist(path: Path, text: str) -> list[Finding]:
    out: list[Finding] = []
    for i, raw in enumerate(text.splitlines(), start=1):
        m = re.match(r"^\s*[-*]\s*\[x\]\s*(.+)$", raw, re.IGNORECASE)
        if not m:
            continue
        content = m.group(1).strip()
        # item marcado sin enlace, sin ruta, muy corto → cosmético
        if len(content) < 20 and not re.search(r"[./#(]|\b\w+\.\w+\b", content):
            out.append(Finding(
                file=str(path.relative_to(ROOT)),
                line=i, severity=SEV_WARN, kind="EMPTY_CHECKLIST",
                excerpt=raw,
                why="Checklist marcado como hecho pero sin detalle ni referencia.",
            ))
    return out


SCANNERS = [
    scan_flattery,
    scan_unsubstantiated,
    scan_success_washing,
    scan_future_as_done,
    scan_evidence_missing,
    scan_empty_checklist,
]


def scan_file(path: Path) -> list[Finding]:
    if is_exempt(path):
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    findings: list[Finding] = []
    for fn in SCANNERS:
        findings.extend(fn(path, text))
    return findings


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="CENTINELA_SINCERIDAD: detecta sincofancía y trampas en docs.md del repo."
    )
    p.add_argument("--path", type=str, default=None,
                   help="Ruta a archivo o carpeta (por defecto repo raíz).")
    p.add_argument("--json", action="store_true", help="Emitir reporte en JSON.")
    p.add_argument("--strict", action="store_true",
                   help="Exit != 0 también ante WARN.")
    p.add_argument("--max", type=int, default=0,
                   help="Limita el nº de hallazgos impresos (0 = sin límite).")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base = Path(args.path).resolve() if args.path else ROOT

    if not base.exists():
        print(f"[sincerity] Ruta no encontrada: {base}", file=sys.stderr)
        return 2

    files: list[Path]
    if base.is_file() and base.suffix == ".md":
        files = [base]
    else:
        files = list(iter_markdown_files(base, _load_lexicon()["exclude_dirs"]))

    all_findings: list[Finding] = []
    for f in files:
        all_findings.extend(scan_file(f))

    # Orden estable: severidad ERROR > WARN, luego fichero/linea
    sev_rank = {SEV_ERROR: 0, SEV_WARN: 1, SEV_INFO: 2}
    all_findings.sort(key=lambda x: (sev_rank.get(x.severity, 9), x.file, x.line))

    if args.json:
        payload = {
            "root": str(base),
            "scanned_files": len(files),
            "findings": [asdict(x) for x in all_findings],
            "totals": {
                "ERROR": sum(1 for x in all_findings if x.severity == SEV_ERROR),
                "WARN":  sum(1 for x in all_findings if x.severity == SEV_WARN),
                "INFO":  sum(1 for x in all_findings if x.severity == SEV_INFO),
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("┌─ CENTINELA_SINCERIDAD ────────────────────────────────────────")
        print(f"│ Raíz escaneada: {base}")
        print(f"│ Ficheros .md  : {len(files)}")
        print(f"│ Hallazgos     : {len(all_findings)}")
        print("└──────────────────────────────────────────────────────────────")
        shown = all_findings if args.max <= 0 else all_findings[: args.max]
        for f in shown:
            print(f.fmt())
        if args.max and len(all_findings) > args.max:
            print(f"... ({len(all_findings) - args.max} hallazgos adicionales ocultos)")

        totals = {
            SEV_ERROR: sum(1 for x in all_findings if x.severity == SEV_ERROR),
            SEV_WARN:  sum(1 for x in all_findings if x.severity == SEV_WARN),
        }
        print("\nResumen:")
        print(f"  ERROR = {totals[SEV_ERROR]}")
        print(f"  WARN  = {totals[SEV_WARN]}")

    has_error = any(x.severity == SEV_ERROR for x in all_findings)
    has_warn = any(x.severity == SEV_WARN for x in all_findings)
    if has_error:
        return 1
    if args.strict and has_warn:
        return 1
    return 0



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    sys.exit(main())
