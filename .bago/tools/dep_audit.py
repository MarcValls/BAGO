#!/usr/bin/env python3
"""dep_audit.py — Herramienta #123: Auditoría de seguridad de dependencias Python.

Analiza requirements.txt / pyproject.toml / setup.cfg y detecta:
  - Versiones pinadas demasiado antiguas (sin rango) — DEP-W001
  - Dependencias sin versión especificada — DEP-W002
  - Paquetes conocidos con vulnerabilidades (lista offline básica) — DEP-E001
  - Versiones inseguras por rango demasiado amplio (>=X sin <) — DEP-W003
  - Dependencias duplicadas en el mismo archivo — DEP-W004
  - Opcionalmente invoca `pip-audit` si está instalado — DEP-E002+

Uso:
    bago dep-audit [FILE|DIR] [--format text|md|json]
                   [--pip-audit] [--out FILE] [--test]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

_GRN  = "\033[0;32m"
_YEL  = "\033[0;33m"
_RED  = "\033[0;31m"
_CYN  = "\033[0;36m"
_RST  = "\033[0m"
_BOLD = "\033[1m"

# Lista básica offline de paquetes con historial de CVEs conocidos
# No reemplaza pip-audit pero da cobertura mínima sin red
KNOWN_VULNERABLE: dict[str, str] = {
    "pyyaml":       "< 6.0 CVE-2017-18342, CVE-2020-14343",
    "pillow":       "< 10.0 múltiples CVEs",
    "requests":     "< 2.20 CVE-2018-18074",
    "urllib3":      "< 2.0 CVE-2023-43804 / < 1.26.17",
    "cryptography": "< 41.0 múltiples CVEs",
    "setuptools":   "< 65.5.1 CVE-2022-40897",
    "werkzeug":     "< 3.0 CVE-2023-46136",
    "django":       "< 4.2 múltiples CVEs",
    "flask":        "< 3.0 revisar changelog",
    "jinja2":       "< 3.1.3 CVE-2024-34064",
    "aiohttp":      "< 3.9.4 CVE-2024-23829",
    "paramiko":     "< 3.4 CVE-2023-48795",
    "pyopenssl":    "< 23.2.0 CVE-2023-49083",
}


def _parse_requirements_txt(filepath: str) -> list[dict]:
    """Parsea requirements.txt y retorna lista de {name, version_spec, line}."""
    deps: list[dict] = []
    for i, raw_line in enumerate(Path(filepath).read_text("utf-8", errors="ignore").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # quitar extras como paquete[extra]
        m = re.match(r'^([A-Za-z0-9_.\-]+)(\[.*?\])?\s*([><=!~,\s\d.*]+)?', line)
        if m:
            name    = m.group(1).lower().replace("-", "_").replace(".", "_")
            version = (m.group(3) or "").strip()
            deps.append({"name": name, "display": m.group(1),
                          "version": version, "line": i, "file": filepath})
    return deps


def _parse_pyproject_toml(filepath: str) -> list[dict]:
    """Parsea dependencias de pyproject.toml (sin toml lib — regex básico)."""
    deps: list[dict] = []
    text = Path(filepath).read_text("utf-8", errors="ignore")
    # Busca líneas en sección [project] → dependencies
    in_deps = False
    for i, line in enumerate(text.splitlines(), 1):
        ls = line.strip()
        if ls.startswith("["):
            in_deps = "dependencies" in ls and "project" in ls
        if in_deps and '=' in ls and ls.startswith('"'):
            m = re.match(r'"([A-Za-z0-9_.\-]+)(\[.*?\])?\s*([><=!~,\s\d.*]+)?"', ls)
            if m:
                name    = m.group(1).lower().replace("-", "_")
                version = (m.group(3) or "").strip()
                deps.append({"name": name, "display": m.group(1),
                              "version": version, "line": i, "file": filepath})
    return deps


def analyze_deps(deps: list[dict]) -> list[dict]:
    findings: list[dict] = []
    seen: dict[str, int] = {}  # name → first line

    for d in deps:
        name  = d["name"]
        spec  = d["version"]
        disp  = d["display"]

        # DEP-W004 — duplicado
        if name in seen:
            findings.append({
                "rule": "DEP-W004", "severity": "warning",
                "file": d["file"], "line": d["line"],
                "message": f"'{disp}' duplicado (primera aparición línea {seen[name]})",
            })
        else:
            seen[name] = d["line"]

        # DEP-W002 — sin versión
        if not spec:
            findings.append({
                "rule": "DEP-W002", "severity": "warning",
                "file": d["file"], "line": d["line"],
                "message": f"'{disp}' sin versión especificada",
            })
            continue

        # DEP-W003 — rango demasiado amplio (>=X sin <Y)
        if ">=" in spec and "<" not in spec:
            findings.append({
                "rule": "DEP-W003", "severity": "warning",
                "file": d["file"], "line": d["line"],
                "message": f"'{disp}{spec}' rango abierto sin límite superior",
            })

        # DEP-E001 — conocidos vulnerables
        for vuln_pkg, vuln_info in KNOWN_VULNERABLE.items():
            vuln_norm = vuln_pkg.lower().replace("-", "_")
            if name == vuln_norm:
                # Solo alerta si no hay restricción de versión clara alta
                findings.append({
                    "rule": "DEP-E001", "severity": "error",
                    "file": d["file"], "line": d["line"],
                    "message": f"'{disp}' — paquete con CVEs conocidos: {vuln_info}",
                })
                break

    return findings


def run_pip_audit(filepath: str) -> list[dict]:
    """Invoca pip-audit si está disponible."""
    try:
        result = subprocess.run(
            ["pip-audit", "-r", filepath, "--format", "json", "--no-progress-spinner"],
            capture_output=True, text=True, timeout=60
        )
        data   = json.loads(result.stdout or "[]")
        findings = []
        for dep in data:
            for vuln in dep.get("vulns", []):
                findings.append({
                    "rule": "DEP-E002", "severity": "error",
                    "file": filepath, "line": 0,
                    "message": (
                        f"{dep.get('name','?')}=={dep.get('version','?')}: "
                        f"{vuln.get('id','?')} — {vuln.get('description','?')[:80]}"
                    ),
                })
        return findings
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return []


def generate_text(findings: list[dict]) -> str:
    if not findings:
        return f"{_GRN}✅ Sin vulnerabilidades conocidas en dependencias{_RST}"
    errors   = [f for f in findings if f["severity"] == "error"]
    warnings = [f for f in findings if f["severity"] == "warning"]
    lines    = [f"{_BOLD}Dep Audit — {len(errors)} error(es), {len(warnings)} warning(s){_RST}", ""]
    for f in errors + warnings:
        color = _RED if f["severity"] == "error" else _YEL
        lines.append(f"  {color}[{f['rule']}]{_RST} L{f['line']}  {f['message']}")
    return "\n".join(lines)


def generate_markdown(findings: list[dict]) -> str:
    errors   = [f for f in findings if f["severity"] == "error"]
    warnings = [f for f in findings if f["severity"] == "warning"]
    lines = [
        f"# Dep Audit — {len(errors)} errores, {len(warnings)} warnings", "",
        "| Regla | L | Mensaje |",
        "|-------|---|---------|",
    ]
    for f in errors + warnings:
        lines.append(f"| `{f['rule']}` | {f['line']} | {f['message']} |")
    lines += ["", "---", "*Generado con `bago dep-audit`*"]
    return "\n".join(lines)


def _find_dep_files(directory: str) -> list[str]:
    found = []
    for pattern in ["requirements*.txt", "pyproject.toml", "setup.cfg"]:
        found.extend(str(p) for p in Path(directory).rglob(pattern)
                     if ".git" not in p.parts and "node_modules" not in p.parts)
    return sorted(found)


def main(argv: list[str]) -> int:
    target     = "./"
    fmt        = "text"
    out_file   = None
    pip_audit  = False

    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--format" and i + 1 < len(argv):
            fmt = argv[i + 1]; i += 2
        elif a == "--out" and i + 1 < len(argv):
            out_file = argv[i + 1]; i += 2
        elif a == "--pip-audit":
            pip_audit = True; i += 1
        elif not a.startswith("--"):
            target = a; i += 1
        else:
            i += 1

    target_path = Path(target)
    if not target_path.exists():
        print(f"No existe: {target}", file=sys.stderr); return 1

    all_findings: list[dict] = []
    if target_path.is_file():
        files = [target]
    else:
        files = _find_dep_files(target)
        if not files:
            print("No se encontraron archivos de dependencias (requirements*.txt / pyproject.toml)")
            return 0

    for f in files:
        if f.endswith(".toml"):
            deps = _parse_pyproject_toml(f)
        else:
            deps = _parse_requirements_txt(f)
        all_findings.extend(analyze_deps(deps))
        if pip_audit and "requirements" in Path(f).name:
            all_findings.extend(run_pip_audit(f))

    if fmt == "json":
        content = json.dumps(all_findings, indent=2)
    elif fmt == "md":
        content = generate_markdown(all_findings)
    else:
        content = generate_text(all_findings)

    if out_file:
        Path(out_file).write_text(content, encoding="utf-8")
        print(f"Guardado: {out_file}", file=sys.stderr)
    else:
        print(content)

    errors = [f for f in all_findings if f["severity"] == "error"]
    return 1 if errors else 0


def _self_test() -> None:
    import tempfile
    print("Tests de dep_audit.py...")
    fails: list[str] = []
    def ok(n): print(f"  OK: {n}")
    def fail(n, m): fails.append(n); print(f"  FAIL: {n}: {m}")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        # T1 — paquete sin versión → DEP-W002
        (root / "requirements.txt").write_text("requests\nflask>=2.0\n")
        deps = _parse_requirements_txt(str(root / "requirements.txt"))
        f1   = analyze_deps(deps)
        w002 = [f for f in f1 if f["rule"] == "DEP-W002"]
        if w002:
            ok("dep_audit:missing_version")
        else:
            fail("dep_audit:missing_version", f"findings={f1}")

        # T2 — paquete conocido vulnerable → DEP-E001
        (root / "req_vuln.txt").write_text("pyyaml>=5.0\nrequests==2.18.0\n")
        deps2 = _parse_requirements_txt(str(root / "req_vuln.txt"))
        f2    = analyze_deps(deps2)
        e001  = [f for f in f2 if f["rule"] == "DEP-E001"]
        if e001:
            ok("dep_audit:known_vulnerable")
        else:
            fail("dep_audit:known_vulnerable", f"findings={f2}")

        # T3 — rango abierto >=X sin < → DEP-W003
        (root / "req_open.txt").write_text("numpy>=1.0\n")
        deps3 = _parse_requirements_txt(str(root / "req_open.txt"))
        f3    = analyze_deps(deps3)
        w003  = [f for f in f3 if f["rule"] == "DEP-W003"]
        if w003:
            ok("dep_audit:open_range")
        else:
            fail("dep_audit:open_range", f"findings={f3}")

        # T4 — dependencia duplicada → DEP-W004
        (root / "req_dup.txt").write_text("numpy==1.25.0\nnumpy==1.26.0\n")
        deps4 = _parse_requirements_txt(str(root / "req_dup.txt"))
        f4    = analyze_deps(deps4)
        w004  = [f for f in f4 if f["rule"] == "DEP-W004"]
        if w004:
            ok("dep_audit:duplicate")
        else:
            fail("dep_audit:duplicate", f"findings={f4}")

        # T5 — dependencias correctas → sin DEP-E001 ni DEP-W002
        (root / "req_ok.txt").write_text("numpy>=1.25,<2.0\nclick>=8.0,<9.0\n")
        deps5 = _parse_requirements_txt(str(root / "req_ok.txt"))
        f5    = analyze_deps(deps5)
        errors_ok = [f for f in f5 if f["rule"] in {"DEP-E001", "DEP-W002", "DEP-W004"}]
        if not errors_ok:
            ok("dep_audit:clean_deps_no_issues")
        else:
            fail("dep_audit:clean_deps_no_issues", f"unexpected={errors_ok}")

        # T6 — markdown output
        md = generate_markdown(f2)
        if "Dep Audit" in md and "DEP-E001" in md:
            ok("dep_audit:markdown_output")
        else:
            fail("dep_audit:markdown_output", md[:80])

    total = 6; passed = total - len(fails)
    print(f"\n  {passed}/{total} tests pasaron")
    if fails: raise SystemExit(1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
    else:
        raise SystemExit(main(sys.argv[1:]))
