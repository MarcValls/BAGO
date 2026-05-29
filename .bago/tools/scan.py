#!/usr/bin/env python3
"""

bago scan — análisis unificado de código con modelo de hallazgos canónico.

Ejecuta todos los linters disponibles sobre el directorio objetivo,
agrega los resultados en un modelo Finding unificado y los persiste.

Uso:
    bago scan                          → escanea .bago/tools/ con todos los linters disponibles
    bago scan <ruta>                   → escanea directorio específico
    bago scan --severity error         → filtra por severidad mínima
    bago scan --source flake8          → solo un linter
    bago scan --rule E302              → filtra por regla
    bago scan --file <ruta>            → filtra por archivo
    bago scan --summary                → solo resumen sin detalle
    bago scan --json                   → output JSON completo
    bago scan --last                   → muestra el último scan guardado
    bago scan --autofixable            → muestra solo hallazgos con autofix disponible
    bago scan --lang py|js|go|auto|java|csharp|ruby|php|swift|kotlin|shell|terraform|yaml
    bago scan --test                   → tests integrados
"""

import argparse, json, subprocess, sys
import sys
from pathlib import Path
from typing import Optional

TOOLS_DIR = Path(__file__).parent
sys.path.insert(0, str(TOOLS_DIR))
import findings_engine as fe

BAGO_ROOT    = Path(__file__).parent.parent
SEVERITY_ORD = {"error": 0, "warning": 1, "info": 2, "hint": 3}
SEV_COLOR    = {"error":"\033[31m","warning":"\033[33m","info":"\033[36m","hint":"\033[2m"}
BOLD  = "\033[1m"; RESET = "\033[0m"; DIM = "\033[2m"; GREEN = "\033[32m"


def _detect_lang(target: str) -> str:
    """Auto-detect dominant language from file extensions and manifests in target."""
    p = Path(target)
    if not p.is_dir():
        suf = Path(target).suffix.lower()
        EXT_MAP = {
            ".py": "py", ".js": "js", ".ts": "js", ".go": "go",
            ".rs": "rust", ".java": "java", ".cs": "csharp",
            ".rb": "ruby", ".php": "php", ".swift": "swift",
            ".kt": "kotlin", ".kts": "kotlin",
            ".sh": "shell", ".bash": "shell",
            ".tf": "terraform", ".hcl": "terraform",
            ".yml": "yaml", ".yaml": "yaml",
        }
        return EXT_MAP.get(suf, "py")

    # Manifest-based detection (deterministic, takes priority)
    if (p / "pom.xml").exists() or (p / "build.gradle").exists() or (p / "build.gradle.kts").exists():
        # Use next() to avoid scanning the full tree unnecessarily
        return "kotlin" if next(p.rglob("*.kt"), None) is not None else "java"
    if any(p.glob("*.csproj")) or any(p.glob("*.sln")):
        return "csharp"
    if (p / "Gemfile").exists():
        return "ruby"
    if (p / "composer.json").exists():
        return "php"
    if (p / "Package.swift").exists():
        return "swift"

    # File-extension counting fallback
    counts = {
        "py": 0, "js": 0, "go": 0, "rust": 0, "java": 0,
        "csharp": 0, "ruby": 0, "php": 0, "swift": 0, "kotlin": 0,
        "shell": 0, "terraform": 0, "yaml": 0,
    }
    for f in p.rglob("*"):
        suf = f.suffix.lower()
        if suf == ".py":                counts["py"]        += 1
        elif suf in (".js", ".ts"):     counts["js"]        += 1
        elif suf == ".go":              counts["go"]        += 1
        elif suf == ".rs":              counts["rust"]      += 1
        elif suf == ".java":            counts["java"]      += 1
        elif suf == ".cs":              counts["csharp"]    += 1
        elif suf == ".rb":              counts["ruby"]      += 1
        elif suf == ".php":             counts["php"]       += 1
        elif suf == ".swift":           counts["swift"]     += 1
        elif suf in (".kt", ".kts"):    counts["kotlin"]    += 1
        elif suf in (".sh", ".bash"):   counts["shell"]     += 1
        elif suf in (".tf", ".hcl"):    counts["terraform"] += 1
        elif suf in (".yml", ".yaml"):  counts["yaml"]      += 1
    dominant = max(counts, key=lambda k: counts[k])
    return dominant if counts[dominant] > 0 else "py"


def run_scan(target: str, sources: Optional[list] = None,
             lang: str = "auto", dry_run: bool = False) -> "fe.FindingsDB":
    db = fe.FindingsDB()
    db.meta["target"] = target

    if lang == "auto":
        lang = _detect_lang(target)

    db.meta["lang"] = lang

    if lang == "py":
        # Always run BAGO's own lint (no external deps)
        bago_findings = fe.run_bago_lint(target)
        db.add(bago_findings)
        db.meta["sources"].append("bago")

        linters = sources or ["flake8", "pylint", "mypy", "bandit"]

        if "flake8" in linters:
            findings, err = fe.run_linter(
                [sys.executable, "-m", "flake8", "--max-line-length=120",
                 "--format=%(path)s:%(row)d:%(col)d: %(code)s %(text)s", target],
                fe.parse_flake8, cwd=str(BAGO_ROOT.parent)
            )
            if not err:
                db.add(findings); db.meta["sources"].append("flake8")

        if "pylint" in linters:
            findings, err = fe.run_linter(
                [sys.executable, "-m", "pylint", "--output-format=json",
                 "--disable=C0114,C0115,C0116,R0903", target],
                fe.parse_pylint, cwd=str(BAGO_ROOT.parent)
            )
            if not err:
                db.add(findings); db.meta["sources"].append("pylint")

        if "mypy" in linters:
            findings, err = fe.run_linter(
                [sys.executable, "-m", "mypy", "--ignore-missing-imports",
                 "--no-error-summary", target],
                fe.parse_mypy, cwd=str(BAGO_ROOT.parent)
            )
            if not err:
                db.add(findings); db.meta["sources"].append("mypy")

        if "bandit" in linters:
            findings, err = fe.run_linter(
                [sys.executable, "-m", "bandit", "-r", "-f", "json", "-q", target],
                fe.parse_bandit, cwd=str(BAGO_ROOT.parent)
            )
            if not err:
                db.add(findings); db.meta["sources"].append("bandit")

    elif lang in ("js", "ts"):
        findings, err = fe.run_linter(
            ["npx", "--yes", "eslint", "--format=json", target],
            fe.parse_eslint, cwd=str(BAGO_ROOT.parent)
        )
        if not err:
            db.add(findings); db.meta["sources"].append("eslint")
        else:
            # fallback: try eslint without npx
            findings, err2 = fe.run_linter(
                ["eslint", "--format=json", target],
                fe.parse_eslint, cwd=str(BAGO_ROOT.parent)
            )
            if not err2:
                db.add(findings); db.meta["sources"].append("eslint")

        # Always run BAGO's own AST-based JS linter (no eslint required)
        ast_findings = fe.run_js_ast_scan(target)
        if ast_findings:
            db.add(ast_findings); db.meta["sources"].append("bago_ast")

    elif lang == "go":
        findings, err = fe.run_linter(
            ["golangci-lint", "run", "--out-format=json", target],
            fe.parse_golangci, cwd=str(BAGO_ROOT.parent)
        )
        if not err:
            db.add(findings); db.meta["sources"].append("golangci")

    elif lang == "rust":
        findings, err = fe.run_linter(
            ["cargo", "clippy", "--message-format=json", "--manifest-path",
             str(Path(target) / "Cargo.toml")],
            fe.parse_clippy, cwd=str(BAGO_ROOT.parent)
        )
        if not err:
            db.add(findings); db.meta["sources"].append("clippy")

    elif lang == "java":
        findings, err = fe.run_linter(
            ["checkstyle", "-f", "xml", "-r", target],
            fe.parse_checkstyle, cwd=str(BAGO_ROOT.parent)
        )
        if not err:
            db.add(findings); db.meta["sources"].append("checkstyle")

    elif lang == "csharp":
        findings, err = fe.run_linter(
            ["dotnet", "build", "--nologo", "/p:TreatWarningsAsErrors=false", target],
            fe.parse_dotnet_build, cwd=str(BAGO_ROOT.parent)
        )
        if not err:
            db.add(findings); db.meta["sources"].append("dotnet")

    elif lang == "ruby":
        findings, err = fe.run_linter(
            ["rubocop", "--format=json", target],
            fe.parse_rubocop, cwd=str(BAGO_ROOT.parent)
        )
        if not err:
            db.add(findings); db.meta["sources"].append("rubocop")

    elif lang == "php":
        findings, err = fe.run_linter(
            ["phpcs", "--report=json", target],
            fe.parse_phpcs, cwd=str(BAGO_ROOT.parent)
        )
        if not err:
            db.add(findings); db.meta["sources"].append("phpcs")
        findings2, err2 = fe.run_linter(
            ["phpstan", "analyse", "--error-format=json", "--no-progress", target],
            fe.parse_phpstan, cwd=str(BAGO_ROOT.parent)
        )
        if not err2:
            db.add(findings2); db.meta["sources"].append("phpstan")

    elif lang == "swift":
        findings, err = fe.run_linter(
            ["swiftlint", "lint", "--reporter=json", "--path", target],
            fe.parse_swiftlint, cwd=str(BAGO_ROOT.parent)
        )
        if not err:
            db.add(findings); db.meta["sources"].append("swiftlint")

    elif lang == "kotlin":
        # Expand glob here so subprocess receives actual file paths (shell won't expand it)
        kt_files = [str(f) for f in Path(target).rglob("*.kt")]
        if kt_files:
            findings, err = fe.run_linter(
                ["ktlint", "--reporter=json"] + kt_files,
                fe.parse_ktlint, cwd=str(BAGO_ROOT.parent)
            )
            if not err:
                db.add(findings); db.meta["sources"].append("ktlint")

    elif lang == "shell":
        shell_files = (
            [str(f) for f in Path(target).rglob("*.sh")]
            + [str(f) for f in Path(target).rglob("*.bash")]
        )
        if shell_files:
            findings, err = fe.run_linter(
                ["shellcheck", "--format=json"] + shell_files,
                fe.parse_shellcheck, cwd=str(BAGO_ROOT.parent)
            )
            if not err:
                db.add(findings); db.meta["sources"].append("shellcheck")

    elif lang == "terraform":
        findings, err = fe.run_linter(
            ["tflint", "--format=json", "--chdir", target],
            fe.parse_tflint, cwd=str(BAGO_ROOT.parent)
        )
        if not err:
            db.add(findings); db.meta["sources"].append("tflint")

    elif lang == "yaml":
        findings, err = fe.run_linter(
            ["yamllint", "-f", "parsable", target],
            fe.parse_yamllint, cwd=str(BAGO_ROOT.parent)
        )
        if not err:
            db.add(findings); db.meta["sources"].append("yamllint")

    if not dry_run:
        db.save()
    return db


def filter_findings(findings: list, severity: Optional[str], source: Optional[str],
                    rule: Optional[str], file_filter: Optional[str],
                    autofixable_only: bool) -> list:
    out = findings
    if severity:
        ord_min = SEVERITY_ORD.get(severity, 3)
        out = [f for f in out if SEVERITY_ORD.get(f.severity, 3) <= ord_min]
    if source:
        out = [f for f in out if f.source == source]
    if rule:
        out = [f for f in out if f.rule == rule]
    if file_filter:
        out = [f for f in out if file_filter in f.file]
    if autofixable_only:
        out = [f for f in out if f.autofixable]
    return out


def render_findings(db: fe.FindingsDB, findings: list, summary_only: bool, as_json: bool):
    if as_json:
        print(json.dumps({
            "scan_id":  db.scan_id,
            "summary":  db._summary(),
            "findings": [f.to_dict() for f in findings],
        }, indent=2, ensure_ascii=False))
        return

    s = db._summary()
    print(f"\n  {BOLD}BAGO Scan{RESET}  [{db.scan_id}]")
    print(f"  Target: {DIM}{db.meta.get('target','')}{RESET}")
    print(f"  Sources: {', '.join(db.meta.get('sources', []))}\n")

    # Summary table
    total = s["total"]
    af    = s["autofixable"]
    errs  = s["by_severity"].get("error", 0)
    warns = s["by_severity"].get("warning", 0)
    infos = s["by_severity"].get("info", 0)
    hints = s["by_severity"].get("hint", 0)

    print(f"  {BOLD}Resumen{RESET}")
    print(f"    Total:       {total}")
    print(f"    {SEV_COLOR['error']}Errores:{RESET}     {errs}")
    print(f"    {SEV_COLOR['warning']}Warnings:{RESET}    {warns}")
    print(f"    {SEV_COLOR['info']}Info:{RESET}        {infos}")
    print(f"    {SEV_COLOR['hint']}Hints:{RESET}       {hints}")
    print(f"    {GREEN}Autofixable:{RESET} {af}")

    if s["top_files"]:
        print(f"\n  {BOLD}Top archivos afectados:{RESET}")
        for fpath, count in s["top_files"][:5]:
            short = fpath.replace(str(BAGO_ROOT.parent) + "/", "")
            print(f"    {count:4d}  {short}")

    if summary_only:
        print()
        return

    # Detail
    if not findings:
        print(f"\n  {GREEN}✓ Sin hallazgos con los filtros aplicados{RESET}\n")
        return

    print(f"\n  {BOLD}Hallazgos ({len(findings)}){RESET}\n")
    cur_file = None
    for f in sorted(findings, key=lambda x: (x.file, x.line)):
        if f.file != cur_file:
            short = f.file.replace(str(BAGO_ROOT.parent) + "/", "")
            print(f"  {BOLD}{short}{RESET}")
            cur_file = f.file
        color = SEV_COLOR.get(f.severity, RESET)
        fix_mark = f"  {GREEN}[autofix]{RESET}" if f.autofixable else ""
        print(f"    {color}{f.severity:8s}{RESET} L{f.line:4d}  {DIM}[{f.rule}]{RESET}  {f.message}{fix_mark}")
        if f.fix_suggestion:
            print(f"             {DIM}→ {f.fix_suggestion}{RESET}")
    print()


def run_tests():
    import tempfile, shutil
    print("Ejecutando tests de scan.py...")
    errors = 0
    def ok(n): print(f"  OK: {n}")
    def fail(n, m):
        nonlocal errors; errors += 1; print(f"  FAIL: {n} — {m}")

    # T1: run_bago_lint finds utcnow issues in tools
    tmp = Path(tempfile.mkdtemp())
    (tmp / "sample.py").write_text(
        "import datetime\nts = datetime.datetime.utcnow()\n" # noqa: BAGO-W001
    )
    findings = fe.run_bago_lint(str(tmp))
    if any(f.rule == "BAGO-W001" for f in findings):
        ok("scan:bago_lint_detects_utcnow")
    else:
        fail("scan:bago_lint_detects_utcnow", str(findings))
    shutil.rmtree(tmp)

    # T2: filter_findings by severity
    f1 = fe.Finding(id="A",severity="error",file="a.py",line=1,col=0,rule="E1",source="flake8",message="e")
    f2 = fe.Finding(id="B",severity="info",file="b.py",line=2,col=0,rule="I1",source="bago",message="i")
    filtered = filter_findings([f1,f2],"error",None,None,None,False)
    if len(filtered)==1 and filtered[0].id=="A":
        ok("scan:filter_severity")
    else:
        fail("scan:filter_severity", str(filtered))

    # T3: filter_findings by source
    filtered2 = filter_findings([f1,f2],None,"bago",None,None,False)
    if len(filtered2)==1 and filtered2[0].source=="bago":
        ok("scan:filter_source")
    else:
        fail("scan:filter_source", str(filtered2))

    # T4: filter_findings autofixable
    f3 = fe.Finding(id="C",severity="warning",file="c.py",line=3,col=0,rule="W1",
                    source="flake8",message="w",autofixable=True)
    filtered3 = filter_findings([f1,f2,f3],None,None,None,None,True)
    if len(filtered3)==1 and filtered3[0].id=="C":
        ok("scan:filter_autofixable")
    else:
        fail("scan:filter_autofixable", str(filtered3))

    # T5: FindingsDB.save creates file
    import importlib.util as ilu
    spec = ilu.spec_from_file_location("fe2", Path(__file__).parent/"findings_engine.py")
    m = ilu.module_from_spec(spec); spec.loader.exec_module(m)
    tmp2 = Path(tempfile.mkdtemp())
    m.FINDINGS_DIR = tmp2
    db = m.FindingsDB("SCAN-TESTX")
    db.add([f1,f2,f3])
    path = db.save()
    if path.exists() and json.loads(path.read_text())["summary"]["total"] == 3:
        ok("scan:db_save_creates_file")
    else:
        fail("scan:db_save_creates_file", str(path))
    shutil.rmtree(tmp2)

    total=5; passed=total-errors
    print(f"\n  {passed}/{total} tests pasaron")
    if errors: raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(prog="bago scan", add_help=False)
    parser.add_argument("target", nargs="?", default=str(BAGO_ROOT / "tools"))
    parser.add_argument("--severity",    default=None)
    parser.add_argument("--source",      default=None)
    parser.add_argument("--rule",        default=None)
    parser.add_argument("--file",        dest="file_filter", default=None)
    parser.add_argument("--summary",     action="store_true")
    parser.add_argument("--json",        action="store_true")
    parser.add_argument("--last",        action="store_true")
    parser.add_argument("--autofixable", action="store_true")
    parser.add_argument("--purge",       action="store_true",
                        help="Elimina SCAN files más antiguos de --days días (default 30)")
    parser.add_argument("--days",        type=int, default=30,
                        help="Antigüedad en días para --purge (default: 30)")
    parser.add_argument("--dry-run",     action="store_true",
                        help="Escanea sin escribir SCAN file (solo muestra conteo)")
    parser.add_argument("--top",         type=int, default=None,
                        help="Muestra solo los N hallazgos más importantes")
    parser.add_argument("--quiet",       action="store_true",
                        help="Suprime la línea de progreso 'Escaneando...'")
    parser.add_argument("--lang",        default="auto",
                        choices=["auto","py","js","ts","go","rust",
                                 "java","csharp","ruby","php",
                                 "swift","kotlin","shell","terraform","yaml"],
                        help="Lenguaje a analizar (default: auto-detección)")
    parser.add_argument("--test",        action="store_true")
    parser.add_argument("--format",      choices=["text", "json", "csv"], default=None,
                        help="Formato de salida: text (default), json, csv")
    parser.add_argument("--output",      default=None, metavar="FILE",
                        help="Escribe output a FILE en lugar de stdout (requiere --format csv o json)")
    parser.add_argument("--stats",       action="store_true",
                        help="Muestra resumen estadístico: total, por severidad y por fuente")
    parser.add_argument("--since",       default=None, metavar="DATE",
                        help="Usa hallazgos de scans desde DATE (YYYY-MM-DD) en lugar del último scan")
    args = parser.parse_args()

    if args.test:
        run_tests(); return

    if args.purge:
        import datetime as _dt
        cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=args.days)
        deleted = []
        for f in sorted(fe.FINDINGS_DIR.glob("SCAN-*.json")):
            mtime = _dt.datetime.fromtimestamp(f.stat().st_mtime, tz=_dt.timezone.utc)
            if mtime < cutoff:
                f.unlink()
                deleted.append(f.name)
        if deleted:
            print(f"🗑  Eliminados {len(deleted)} SCAN files con >  {args.days} días:")
            for name in deleted:
                print(f"   · {name}")
        else:
            print(f"✅ Sin SCAN files con > {args.days} días — nada que limpiar.")
        return

    since_date = getattr(args, "since", None)

    if args.last or since_date:
        if since_date:
            # Load all scan files with timestamp >= since_date and merge findings
            import datetime as _dt
            try:
                cutoff = _dt.date.fromisoformat(since_date)
            except ValueError:
                print(f"ERROR: --since fecha inválida '{since_date}' (usa YYYY-MM-DD)", file=sys.stderr)
                raise SystemExit(1)
            all_scans = sorted(fe.FINDINGS_DIR.glob("SCAN-*.json"))
            merged = []
            latest_db = None
            for sf in all_scans:
                # SCAN-YYYYMMDD_HHMMSS → extract date part
                stem = sf.stem  # e.g. SCAN-20260101_120000
                try:
                    date_part = stem.split("-", 1)[1].split("_")[0]  # YYYYMMDD
                    scan_date = _dt.date(int(date_part[:4]), int(date_part[4:6]), int(date_part[6:8]))
                except Exception:
                    continue
                if scan_date >= cutoff:
                    try:
                        d = fe.FindingsDB.load(stem)
                        merged.extend(d.findings)
                        latest_db = d
                    except Exception:
                        pass
            if latest_db is None:
                if not getattr(args, "quiet", False):
                    print(f"Sin scans desde {since_date}.")
                db = fe.FindingsDB()
                db.findings = []
            else:
                db = latest_db
                db.findings = merged
        else:
            db = fe.FindingsDB.latest()
            if db is None:
                print("Sin scans guardados. Ejecuta 'bago scan' primero.")
                raise SystemExit(1)
    else:
        lang = "js" if args.lang == "ts" else args.lang
        if not getattr(args, "quiet", False):
            print(f"  Escaneando {args.target} ... [lang={lang}]")
        dry = getattr(args, "dry_run", False)
        db = run_scan(args.target, lang=lang, dry_run=dry)

    if getattr(args, "dry_run", False):
        n = len(db.findings)
        print(f"(dry-run) {n} hallazgos encontrados — SCAN file no escrito")
        return

    findings = filter_findings(
        db.findings,
        args.severity, args.source, args.rule,
        args.file_filter, args.autofixable
    )
    if args.top is not None:
        sev_order = {"error": 0, "warning": 1, "info": 2, "hint": 3}
        findings = sorted(findings, key=lambda f: sev_order.get(f.severity, 9))[:args.top]

    fmt = getattr(args, "format", None)
    out_path = getattr(args, "output", None)

    if getattr(args, "stats", False):
        from collections import Counter
        sev_counts = Counter(f.severity for f in findings)
        src_counts = Counter(f.source   for f in findings)
        total = len(findings)
        if args.json:
            import json as _json
            print(_json.dumps({
                "total": total,
                "by_severity": dict(sev_counts),
                "by_source":   dict(src_counts),
            }, indent=2))
        else:
            print(f"\n  Scan stats  (scan_id={db.scan_id})\n")
            print(f"  Total hallazgos: {total}\n")
            print(f"  Por severidad:")
            for sev in ("error", "warning", "info", "hint"):
                n = sev_counts.get(sev, 0)
                if n:
                    print(f"    {sev:10s} {n:>5}")
            print(f"\n  Por fuente:")
            for src, n in src_counts.most_common():
                print(f"    {src:20s} {n:>5}")
            print()
        return

    def _write(content: str):
        if out_path:
            from pathlib import Path as _Path
            _Path(out_path).write_text(content, encoding="utf-8")
            print(f"✅ Guardado: {out_path}")
        else:
            print(content, end="")

    if fmt == "csv":
        import csv as _csv, io as _io
        buf = _io.StringIO()
        w = _csv.writer(buf)
        w.writerow(["file", "line", "col", "severity", "rule", "source", "message"])
        for f in findings:
            w.writerow([f.file, f.line, f.col, f.severity, f.rule, f.source, f.message])
        _write(buf.getvalue())
        return
    elif fmt == "json":
        args.json = True

    render_findings(db, findings, args.summary, args.json)

if __name__ == "__main__":
    main()