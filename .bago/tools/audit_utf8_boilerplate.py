#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_utf8_boilerplate.py — Detecta y opcionalmente migra el bloque UTF-8 duplicado.

Uso:
  python tools/audit_utf8_boilerplate.py --report           → JSON con archivos afectados
  python tools/audit_utf8_boilerplate.py --fix --dry-run    → muestra cambios sin aplicar
  python tools/audit_utf8_boilerplate.py --fix             → aplica migración segura

Política de migración:
  - Solo toca archivos en tools/ que contengan el bloque y NO importen bago_utils.
  - Reemplaza el bloque por `from bago_utils import ...` si el archivo usa funciones
    comunes (load_json, save_json, etc.); de lo contrario inserta un comentario
    indicando que debe importar bago_utils en el futuro.
  - Nunca modifica bago_utils.py ni archivos fuera de tools/.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ── self-utf8 (necesario para este propio script) ────────────────────────────

import argparse
import json
import re
from datetime import datetime, timezone


TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent
REPORT_PATH = ROOT / "state" / "audits" / "EVIDENCE-AUDIT-UTF8-BOILERPLATE.json"

# Patrones para detectar el bloque (permite variaciones menores)
_UTF8_BLOCK_RE = re.compile(
    r"""
    ^import\s+os\s*\n
    import\s+sys\s*\n\n
    for\s+_\w+\s+in\s+\(\s*sys\.stdout\s*,\s*sys\.stderr\s*\):\s*\n
    \s+try:\s*\n
    \s+_\w+\.reconfigure\(encoding=["']utf-8["'](?:,\s*errors=["']replace["'])?\)\s*\n
    \s+except\s+Exception:\s*\n
    \s+pass\s*\n
    """,
    re.MULTILINE | re.VERBOSE,
)

_SIMPLE_UTF8_RE = re.compile(
    r"for\s+_\w+\s+in\s+\(\s*sys\.stdout\s*,\s*sys\.stderr\s*\):\s*\n"
    r"\s+try:\s*\n"
    r"\s+_\w+\.reconfigure\(encoding=\"utf-8\"",
    re.MULTILINE,
)


def has_utf8_boilerplate(text: str) -> bool:
    return bool(_SIMPLE_UTF8_RE.search(text))


def already_imports_bago_utils(text: str) -> bool:
    return bool(re.search(r"from\s+bago_utils\s+import|import\s+bago_utils", text))


def detect_affected_files() -> list[dict]:
    affected = []
    for py_file in sorted(TOOLS_DIR.glob("*.py")):
        text = py_file.read_text(encoding="utf-8")
        if py_file.name == "bago_utils.py":
            continue
        if has_utf8_boilerplate(text):
            affected.append(
                {
                    "file": f"tools/{py_file.name}",
                    "imports_bago_utils": already_imports_bago_utils(text),
                    "size": py_file.stat().st_size,
                }
            )
    return affected


def generate_report(affected: list[dict]) -> dict:
    return {
        "evidence_id": "EVIDENCE-AUDIT-UTF8-BOILERPLATE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool": "audit_utf8_boilerplate.py",
        "total_tools": len(list(TOOLS_DIR.glob("*.py"))),
        "affected_count": len(affected),
        "affected_files": affected,
        "recommendation": (
            "Migrar archivos afectados importando bago_utils.py al inicio. "
            "Si un archivo ya importa bago_utils, el bloque UTF-8 puede eliminarse "
            "porque bago_utils.py ya lo ejecuta al importarse."
        ),
    }


def fix_file(py_file: Path, dry_run: bool) -> dict:
    text = py_file.read_text(encoding="utf-8")
    if not has_utf8_boilerplate(text):
        return {"file": str(py_file), "action": "none", "reason": "no boilerplate"}

    if already_imports_bago_utils(text):
        # Caso seguro: solo eliminar el bloque, bago_utils ya lo cubre
        new_text = _UTF8_BLOCK_RE.sub("", text, count=1)
        if new_text == text:
            # Fallback por si el regex complejo no coincidió
            # Eliminamos líneas manualmente
            lines = text.splitlines(keepends=True)
            new_lines = []
            skip_until = -1
            for i, line in enumerate(lines):
                if skip_until >= 0 and i <= skip_until:
                    continue
                    # Saltar esta línea y las siguientes del bloque
                    skip_until = i
                    # Buscar hasta 'pass'
                    for j in range(i + 1, len(lines)):
                        if lines[j].strip() == "pass":
                            skip_until = j
                            break
                    continue
                    skip_until = i
                    for j in range(i + 1, len(lines)):
                        if lines[j].strip() == "pass":
                            skip_until = j
                            break
                    continue
                if "reconfigure(encoding=\"utf-8\"" in line:
                    continue
                new_lines.append(line)
            new_text = "".join(new_lines)
        action = "removed_boilerplate_only"
    else:
        # Caso complejo: insertar import de bago_utils al inicio y eliminar bloque
        new_text = _UTF8_BLOCK_RE.sub("", text, count=1)
        if new_text == text:
            lines = text.splitlines(keepends=True)
            new_lines = []
            skip_until = -1
            for i, line in enumerate(lines):
                if skip_until >= 0 and i <= skip_until:
                    continue
                    skip_until = i
                    for j in range(i + 1, len(lines)):
                        if lines[j].strip() == "pass":
                            skip_until = j
                            break
                    continue
                    skip_until = i
                    for j in range(i + 1, len(lines)):
                        if lines[j].strip() == "pass":
                            skip_until = j
                            break
                    continue
                if "reconfigure(encoding=\"utf-8\"" in line:
                    continue
                new_lines.append(line)
            new_text = "".join(new_lines)
        # Insertar import bago_utils tras la docstring/shebang
        new_text = _insert_bago_utils_import(new_text)
        action = "replaced_with_bago_utils_import"

    if not dry_run:
        py_file.write_text(new_text, encoding="utf-8")
    return {"file": str(py_file), "action": action, "dry_run": dry_run}


def _insert_bago_utils_import(text: str) -> str:
    lines = text.splitlines(keepends=True)
    insert_idx = 0
    # Buscar shebang / docstring inicial
    for i, line in enumerate(lines):
        if line.startswith("#") or line.startswith('"""') or line.startswith("'''"):
            insert_idx = i + 1
        else:
            break
    # Buscar from __future__ import annotations e insertar DESPUÉS
    for i, line in enumerate(lines):
        if "from __future__ import annotations" in line:
            insert_idx = i + 1
            break
    lines.insert(insert_idx, "\nfrom bago_utils import load_json, save_json, timestamp_iso\n")
    return "".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditoría de boilerplate UTF-8 duplicado")
    parser.add_argument("--report", action="store_true", help="Generar reporte JSON")
    parser.add_argument("--fix", action="store_true", help="Aplicar correcciones")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin escribir")
    args = parser.parse_args()

    affected = detect_affected_files()

    if args.report or not args.fix:
        report = generate_report(affected)
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Reporte guardado en: {REPORT_PATH}")
        print(f"Afectados: {report['affected_count']} / {report['total_tools']}")
        for item in affected:
            status = "OK" if item["imports_bago_utils"] else "PENDING"
            print(f"  [{status}] {item['file']}")

    if args.fix:
        print("\nAplicando correcciones...")
        results = []
        for item in affected:
            py_file = TOOLS_DIR / Path(item["file"]).name
            res = fix_file(py_file, dry_run=args.dry_run)
            results.append(res)
            print(f"  {res['action']:40s} {Path(res['file']).name}")
        if args.dry_run:
            print("\n(modo dry-run; no se escribió nada)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
