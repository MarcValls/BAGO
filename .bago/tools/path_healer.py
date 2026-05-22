#!/usr/bin/env python3
from __future__ import annotations

"""path_healer.py — Reparador automático de rutas rotas con memoria dinámica."""

import sys as _sys

if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(_sys.stderr, "reconfigure"):
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Optional

import _healer_memory as memory_mod
from _healer_discovery import (
    PathRef,
    ScanReport,
    build_patterns_for_file,
    build_replacement,
    build_stem_index,
    discover_path_vars,
    scan_all,
    scan_file,
)
from _healer_memory import BAGO_ROOT, REPO_ROOT, STATE_DIR, TOOLS_DIR, Memory

_COLOR = sys.stdout.isatty() and sys.platform != "win32"


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


OK = lambda text: _c("1;32", text)  # noqa: E731
WARN = lambda text: _c("1;33", text)  # noqa: E731
ERR = lambda text: _c("1;31", text)  # noqa: E731
DIM = lambda text: _c("2", text)  # noqa: E731
CYAN = lambda text: _c("1;36", text)  # noqa: E731


def fix_file(refs: list[PathRef], dry_run: bool, backup: bool, mem: Memory) -> int:
    if not refs:
        return 0

    py_file = refs[0].file
    fixable = [ref for ref in refs if ref.found_at is not None and ref.broken]
    if not fixable:
        return 0

    try:
        original = py_file.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"  {ERR('✗')} No se puede leer {py_file}: {exc}")
        return 0

    text = original
    applied = 0
    for ref in sorted(fixable, key=lambda item: item.line_no, reverse=True):
        replacement = build_replacement(ref)
        if replacement == ref.fragment:
            continue

        new_text = text.replace(ref.fragment, replacement, 1)
        if new_text == text:
            print(f"  {WARN('⚠')} No reemplazado: {py_file.name}:{ref.line_no} {ref.fragment!r:.60}")
            continue

        rel_file = str(py_file.relative_to(REPO_ROOT)) if py_file.is_relative_to(REPO_ROOT) else str(py_file)
        print(f"  {CYAN('→')} {py_file.name}:{ref.line_no}")
        print(f"       {DIM('old:')} {ref.fragment[:80]}")
        print(f"       {OK('new:')} {replacement[:80]}")

        if not dry_run:
            text = new_text
            ref.fixed = True
            applied += 1
            mem.record_heal(rel_file, ref.stem, ref.line_no, ref.fragment, replacement)

    if not dry_run and applied > 0:
        bak = py_file.with_suffix(py_file.suffix + ".healer.bak")
        if backup:
            shutil.copy2(str(py_file), str(bak))
        try:
            py_file.write_text(text, encoding="utf-8")
        except OSError as exc:
            print(f"  {ERR('✗')} No se puede escribir {py_file}: {exc}")
            if backup and bak.exists():
                shutil.copy2(str(bak), str(py_file))
            return 0

    return applied


def fix_all(report: ScanReport, dry_run: bool, backup: bool, max_fixes: int, mem: Memory) -> int:
    by_file: dict[Path, list[PathRef]] = {}
    for ref in report.refs:
        if ref.broken and ref.found_at is not None:
            by_file.setdefault(ref.file, []).append(ref)

    total = 0
    for _, file_refs in sorted(by_file.items()):
        if total >= max_fixes:
            break
        batch = file_refs[: max_fixes - total]
        total += fix_file(batch, dry_run=dry_run, backup=backup, mem=mem)

    report.fixed = total
    return total


def print_report(report: ScanReport, json_out: bool = False) -> None:
    if json_out:
        data = {
            "files_scanned": report.files_scanned,
            "broken": report.broken,
            "fixed": report.fixed,
            "missing": report.missing,
            "refs": [
                {
                    "file": str(ref.file),
                    "line": ref.line_no,
                    "stem": ref.stem,
                    "var": ref.var_name,
                    "fragment": ref.fragment,
                    "found_at": str(ref.found_at) if ref.found_at else None,
                    "fixed": ref.fixed,
                    "broken": ref.broken,
                }
                for ref in report.refs
                if ref.broken
            ],
        }
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    print("\n  BAGO Path Healer")
    print(f"  {'─' * 52}")
    print(f"  Archivos escaneados : {report.files_scanned}")
    print(f"  Referencias rotas   : {WARN(str(report.broken)) if report.broken else OK('0')}")
    print(f"  Reparadas           : {OK(str(report.fixed))}")
    print(f"  No encontradas      : {ERR(str(report.missing)) if report.missing else '0'}")

    broken_refs = [ref for ref in report.refs if ref.broken]
    if not broken_refs:
        print(f"\n  {OK('✅ Sin rutas rotas detectadas')}\n")
        return

    pending = [ref for ref in broken_refs if not ref.fixed and ref.found_at]
    missing = [ref for ref in broken_refs if not ref.found_at]
    fixed = [ref for ref in broken_refs if ref.fixed]

    def _rel(path: Path) -> str:
        try:
            return str(path.relative_to(REPO_ROOT))
        except ValueError:
            return str(path)

    if pending:
        print(f"\n  {WARN('⚠')} Pendientes ({len(pending)}):")
        for ref in pending:
            print(f"     {_rel(ref.file)}:{ref.line_no}  {DIM(ref.stem)}  →  {_rel(ref.found_at)}")

    if missing:
        print(f"\n  {ERR('✗')} No encontrados ({len(missing)}):")
        for ref in missing:
            print(f"     {_rel(ref.file)}:{ref.line_no}  {ERR(ref.stem + '.py')}")

    if fixed:
        print(f"\n  {OK('✅')} Reparadas ({len(fixed)}):")
        for ref in fixed:
            print(f"     {_rel(ref.file)}:{ref.line_no}  {ref.stem}")

    print()


def watch_mode(interval: int, max_fixes: int, backup: bool) -> None:
    print(f"\n  👁  Path Healer — daemon (intervalo: {interval}s)")
    print(f"  Raíz vigilada: {BAGO_ROOT}\n")
    mem = Memory.load()
    try:
        while True:
            ts = time.strftime("%H:%M:%S")
            report = scan_all(mem)
            broken_fixable = [ref for ref in report.refs if ref.broken and ref.found_at]
            if broken_fixable:
                print(f"  [{ts}] {WARN(f'{len(broken_fixable)} rutas rotas')} — reparando…")
                fix_all(report, dry_run=False, backup=backup, max_fixes=max_fixes, mem=mem)
                mem.last_scan = time.strftime("%Y-%m-%dT%H:%M:%S")
                mem.save()
                print(f"  [{ts}] {OK(f'{report.fixed} reparadas')}")
            else:
                print(f"  [{ts}] {OK('✓')} Sin rutas rotas  ({report.files_scanned} archivos)")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n  Daemon detenido.")


def _self_test() -> int:
    results: list[tuple[str, bool, str]] = []

    results.append(("anchor_found", (TOOLS_DIR / "tool_registry.py").exists(), str(TOOLS_DIR)))

    mem = Memory.load()
    results.append(("memory_loads", isinstance(mem, Memory), f"stems={len(mem.stem_index)}"))

    idx = build_stem_index(mem)
    results.append(("stem_index_size", len(idx) > 30, f"{len(idx)} entries"))

    fake_source = "TOOLS_DIR = Path(__file__).parent\nBAGO_ROOT = Path(__file__).parent.parent\n"
    fake_file = TOOLS_DIR / "fake_test_xyz.py"
    path_vars = discover_path_vars(fake_source, fake_file)
    results.append(("discover_path_vars_tools_dir", path_vars.get("TOOLS_DIR") == TOOLS_DIR, str(path_vars.get("TOOLS_DIR"))))
    results.append(("discover_path_vars_bago_root", path_vars.get("BAGO_ROOT") == BAGO_ROOT, str(path_vars.get("BAGO_ROOT"))))

    patterns = build_patterns_for_file({"TOOLS_DIR": TOOLS_DIR})
    results.append(("patterns_generated", len(patterns) >= 2, f"{len(patterns)} patterns"))

    test_line = 'str(TOOLS_DIR / "secret_scan.py")'
    detected: list[str] = []
    for pattern, _, _ in patterns:
        for match in pattern.finditer(test_line):
            groups = [group for group in match.groups() if group and re.match(r"^[a-zA-Z0-9_\-]+$", group)]
            if groups:
                detected.append(groups[-1])
    results.append(("pattern_detects_stem", "secret_scan" in detected, f"detected={detected}"))

    test_mem_file = STATE_DIR / "_test_healer_memory.json"
    old_mem_file = memory_mod.MEMORY_FILE
    memory_mod.MEMORY_FILE = test_mem_file
    try:
        Memory(stem_index={"test_stem": ".bago/tools/test_stem.py"}).save()
        reloaded = Memory.load()
    finally:
        memory_mod.MEMORY_FILE = old_mem_file
        test_mem_file.unlink(missing_ok=True)
    results.append(("memory_roundtrip", reloaded.stem_index.get("test_stem") == ".bago/tools/test_stem.py", ""))

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n  BAGO Path Healer — Self-tests ({passed}/{len(results)} pasaron)\n")
    for name, ok, detail in results:
        print(f"  {'✅' if ok else '❌'}  {name}  {detail}")
    return 0 if passed == len(results) else 1


def main(argv: Optional[list[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    parser = argparse.ArgumentParser(
        description="BAGO Path Healer — detecta y repara rutas rotas (memoria dinámica)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--scan", action="store_true", help="Solo detecta, no modifica")
    parser.add_argument("--file", metavar="PATH", help="Repara solo este archivo")
    parser.add_argument("--report", action="store_true", help="Salida JSON para CI")
    parser.add_argument("--watch", action="store_true", help="Daemon de vigilancia continua")
    parser.add_argument("--interval", type=int, default=15, help="Segundos entre ciclos (--watch)")
    parser.add_argument("--max-fixes", type=int, default=100, help="Límite de fixes por ejecución")
    parser.add_argument("--no-backup", action="store_true", help="No crear .healer.bak")
    parser.add_argument("--forget", action="store_true", help="Borra memoria y re-indexa")
    parser.add_argument("--test", action="store_true", help="Ejecuta self-tests")
    args = parser.parse_args(argv)

    if args.test:
        return _self_test()

    mem = Memory.load()
    if args.forget:
        mem = Memory()
        mem.save()
        print(f"  {OK('✓')} Memoria borrada — se re-indexará en el próximo escaneo")

    if args.watch:
        watch_mode(interval=args.interval, max_fixes=args.max_fixes, backup=not args.no_backup)
        return 0

    backup = not args.no_backup
    if args.file:
        target = Path(args.file)
        if not target.is_absolute():
            target = REPO_ROOT / args.file
        if not target.exists():
            print(f"  {ERR('✗')} No encontrado: {target}")
            return 1
        refs = scan_file(target, build_stem_index(mem), mem)
        report = ScanReport(
            files_scanned=1,
            refs_found=len(refs),
            broken=sum(1 for ref in refs if ref.broken),
            missing=sum(1 for ref in refs if ref.broken and not ref.found_at),
            refs=refs,
        )
        if not args.scan:
            fix_file([ref for ref in refs if ref.broken], dry_run=False, backup=backup, mem=mem)
            mem.last_scan = time.strftime("%Y-%m-%dT%H:%M:%S")
            mem.save()
        print_report(report, json_out=args.report)
        return 0

    if not args.report:
        print(f"\n  Escaneando {BAGO_ROOT}…")

    report = scan_all(mem)
    if not args.scan:
        fix_all(report, dry_run=False, backup=backup, max_fixes=args.max_fixes, mem=mem)
        mem.last_scan = time.strftime("%Y-%m-%dT%H:%M:%S")
        mem.save()

    print_report(report, json_out=args.report)
    return 0 if report.missing == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
