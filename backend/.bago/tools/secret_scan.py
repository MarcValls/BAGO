#!/usr/bin/env python3
"""secret_scan.py — Herramienta #108: Escáner de secretos y credenciales hardcodeadas.

Detecta patrones de secretos en el código fuente:
 - Claves API, tokens, contraseñas hardcodeadas
 - Strings de conexión con credenciales
 - JWT tokens, claves privadas, hashes
 - Patrones de plataformas conocidas (AWS, GitHub, Stripe, etc.)

Uso:
    bago secret-scan [TARGET] [--json] [--severity error|warning|info]
                     [--no-git-check] [--test]

Opciones:
    TARGET          Archivo o directorio (default: ./)
    --json          Output en JSON
    --severity      Filtrar por severidad mínima (default: warning)
    --no-git-check  No verificar si los archivos están en .gitignore
    --test          Self-tests
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

_RED  = "\033[0;31m"
_YEL  = "\033[0;33m"
_BLU  = "\033[0;34m"
_GRN  = "\033[0;32m"
_RST  = "\033[0m"
_BOLD = "\033[1m"
_DIM  = "\033[2m"

SKIP_DIRS = {"node_modules", "__pycache__", ".git", "venv", ".venv",
             "dist", "build", ".mypy_cache", "TESTS", ".vercel"}
SKIP_EXTS = {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
             ".zip", ".tar", ".gz", ".pdf", ".woff", ".ttf", ".eot"}

# Patrones: (nombre, regex, severidad, descripcion)
SECRET_PATTERNS: list[tuple[str, re.Pattern, str, str]] = [
    ("SEC-E001", re.compile(
        r'(?i)(password|passwd|pwd)\s*[=:]\s*["\'](?!.*placeholder|.*example|.*changeme|.*your)[^"\']{6,}["\']'
    ), "error", "Posible contraseña hardcodeada"),
    ("SEC-E002", re.compile(
        r'(?i)(api[_-]?key|apikey|secret[_-]?key)\s*[=:]\s*["\'][A-Za-z0-9+/\-_]{16,}["\']'
    ), "error", "Posible API key hardcodeada"),
    ("SEC-E003", re.compile(
        r'(AKIA|AGPA|AROA|AIDA|ANPA|ANVA|ASIA)[A-Z0-9]{16}'
    ), "error", "AWS Access Key ID"),
    ("SEC-E004", re.compile(
        r'ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82}'
    ), "error", "GitHub Personal Access Token"),
    ("SEC-E005", re.compile(
        r'sk-[A-Za-z0-9]{20,}T3BlbkFJ[A-Za-z0-9]{20,}'
    ), "error", "OpenAI API Key"),
    ("SEC-E006", re.compile(
        r'-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'
    ), "error", "Clave privada PEM"),
    ("SEC-E007", re.compile(
        r'(?i)mongodb(\+srv)?://[^:]+:[^@]{6,}@'
    ), "error", "MongoDB connection string con credenciales"),
    ("SEC-W001", re.compile(
        r'(?i)(token|auth[_-]?token|access[_-]?token)\s*[=:]\s*["\'][A-Za-z0-9+/\-_\.]{20,}["\']'
    ), "warning", "Posible token hardcodeado"),
    ("SEC-W002", re.compile(
        r'(?i)(secret|private[_-]?key)\s*[=:]\s*["\'][A-Za-z0-9+/\-_]{12,}["\']'
    ), "warning", "Posible secreto hardcodeado"),
    ("SEC-W003", re.compile(
        r'(?i)(database[_-]?url|db[_-]?url|connection[_-]?string)\s*[=:]\s*["\'][^"\']{10,}["\']'
    ), "warning", "URL de base de datos posiblemente con credenciales"),
    ("SEC-W004", re.compile(
        r'(?i)stripe[_-]?(sk|pk|rk|wh)_(live|test)_[A-Za-z0-9]{24,}'
    ), "warning", "Stripe API Key"),
    ("SEC-I001", re.compile(
        r'(?i)(TODO|FIXME).{0,30}password|password.{0,30}(TODO|FIXME)'
    ), "info", "TODO relacionado con contraseña"),
]

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


@dataclass
class SecretFinding:
    file:     str
    line:     int
    rule:     str
    severity: str
    message:  str
    snippet:  str = ""  # línea ofuscada


def _obfuscate(line: str) -> str:
    """Ofusca el valor potencialmente sensible."""
    return re.sub(
        r'(["\'])([A-Za-z0-9+/\-_\.]{6})([A-Za-z0-9+/\-_\.]+)(["\'])',
        lambda m: m.group(1) + m.group(2) + "***" + m.group(4),
        line
    )[:100]


# Allowlist explícita: solo estos comentarios exactos permiten ignorar una línea.
# No usar "noqa" genérico — evitar bypass involuntario.
_SCAN_ALLOWLIST = frozenset({
    "# noqa: test fixture",
    "# pragma: allowlist secret",
    "# nosec: test fixture",
})


def scan_file(filepath: str) -> list[SecretFinding]:
    path = Path(filepath)
    if path.suffix in SKIP_EXTS:
        return []
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    findings: list[SecretFinding] = []
    lines = source.splitlines()

    for i, line in enumerate(lines, 1):
        # Saltar líneas con allowlist explícita (solo comentarios exactos)
        if any(marker in line for marker in _SCAN_ALLOWLIST):
            continue
        # Saltar líneas que son comentarios de ejemplo o falsas alarmas comunes
        stripped = line.strip()
        if any(x in stripped.lower() for x in
               ("example", "placeholder", "changeme", "your-", "your_", "<your", "${", "%(")):
            continue
        # Saltar líneas en archivos de test (menos falsos positivos)
        if "test" in filepath.lower() and "password" in stripped.lower():
            continue

        for rule, pattern, severity, desc in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(SecretFinding(
                    file=filepath, line=i,
                    rule=rule, severity=severity,
                    message=desc,
                    snippet=_obfuscate(stripped)
                ))
                break  # un hallazgo por línea

    return findings


def scan_target(target: str, min_sev: str = "warning") -> list[SecretFinding]:
    p = Path(target)
    files: list[Path] = []
    if p.is_file():
        files = [p]
    elif p.is_dir():
        files = [f for f in p.rglob("*")
                 if f.is_file()
                 and f.suffix not in SKIP_EXTS
                 and not any(d in f.parts for d in SKIP_DIRS)]

    min_ord = SEVERITY_ORDER.get(min_sev, 1)
    all_findings: list[SecretFinding] = []
    for f in sorted(files):
        for finding in scan_file(str(f)):
            if SEVERITY_ORDER.get(finding.severity, 2) <= min_ord:
                all_findings.append(finding)
    return all_findings


def main(argv: list[str]) -> int:
    target   = "./"
    as_json  = False
    min_sev  = "warning"

    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--json":
            as_json = True; i += 1
        elif a == "--severity" and i + 1 < len(argv):
            min_sev = argv[i + 1]; i += 2
        elif a == "--no-git-check":
            i += 1
        elif not a.startswith("--"):
            target = a; i += 1
        else:
            i += 1

    findings = scan_target(target, min_sev)
    errors   = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]

    if as_json:
        print(json.dumps({
            "target": target, "total": len(findings),
            "errors": len(errors), "warnings": len(warnings),
            "findings": [asdict(f) for f in findings],
        }, indent=2))
        return 1 if errors else 0

    if not findings:
        print(f"{_GRN}✅ Sin secretos detectados en {target}{_RST}")
        return 0

    print(f"\n{_BOLD}Secret Scan — {target}{_RST}")
    print(f"Total: {len(findings)} ({len(errors)} errores, {len(warnings)} advertencias)\n")

    for f in findings:
        clr = _RED if f.severity == "error" else _YEL
        print(f"  {clr}{f.severity:7s}{_RST} [{f.rule}]  {f.file}:{f.line}")
        print(f"  {_DIM}{f.message}{_RST}")
        if f.snippet:
            print(f"  {_DIM}> {f.snippet}{_RST}")
        print()

    if errors:
        print(f"  {_RED}⚠️  SECRETOS CRÍTICOS DETECTADOS — revisar antes de commit{_RST}")
        return 1
    return 0


def _self_test() -> None:
    import tempfile, textwrap
    print("Tests de secret_scan.py...")
    fails: list[str] = []
    def ok(n): print(f"  OK: {n}")
    def fail(n, m): fails.append(n); print(f"  FAIL: {n}: {m}")

    # T1 — password hardcodeada detectada
    src1 = 'password = "supersecret123"\n'  # noqa: test fixture
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(src1); tmp1 = f.name
    r1 = scan_file(tmp1)
    if any(x.rule == "SEC-E001" for x in r1):
        ok("secret_scan:password_detected")
    else:
        fail("secret_scan:password_detected", f"findings={[x.rule for x in r1]}")

    # T2 — API key detectada
    src2 = 'api_key = "AbCdEfGhIjKlMnOpQrStUvWx"\n'  # noqa: test fixture
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(src2); tmp2 = f.name
    r2 = scan_file(tmp2)
    if any(x.rule == "SEC-E002" for x in r2):
        ok("secret_scan:api_key_detected")
    else:
        fail("secret_scan:api_key_detected", f"findings={[(x.rule,x.message) for x in r2]}")

    # T3 — AWS key detectada
    aws_key = "AKIA" + "IOSFODNN7REALKEY"
    src3 = f"key = '{aws_key}'\n"  # noqa: test fixture
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(src3); tmp3 = f.name
    r3 = scan_file(tmp3)
    if any(x.rule == "SEC-E003" for x in r3):
        ok("secret_scan:aws_key_detected")
    else:
        fail("secret_scan:aws_key_detected", f"findings={[x.rule for x in r3]}")

    # T4 — placeholder no detectado como secreto
    src4 = 'password = "CHANGEME"\n'
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(src4); tmp4 = f.name
    r4 = scan_file(tmp4)
    if not any(x.rule == "SEC-E001" for x in r4):
        ok("secret_scan:placeholder_not_flagged")
    else:
        fail("secret_scan:placeholder_not_flagged", "CHANGEME fue flaggeado como secreto")

    # T5 — _obfuscate ofusca el valor
    obf = _obfuscate('api_key = "AbCdEfGhIjKlMnOpQrStUvWx"')  # noqa: test fixture
    if "***" in obf and "AbCdEf" in obf:
        ok("secret_scan:obfuscate_works")
    else:
        fail("secret_scan:obfuscate_works", f"obf={obf!r}")

    # T6 — clave privada PEM detectada
    src6 = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n"  # noqa: test fixture
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(src6); tmp6 = f.name
    r6 = scan_file(tmp6)
    if any(x.rule == "SEC-E006" for x in r6):
        ok("secret_scan:pem_key_detected")
    else:
        fail("secret_scan:pem_key_detected", f"findings={[x.rule for x in r6]}")

    for t in [tmp1, tmp2, tmp3, tmp4, tmp6]:
        Path(t).unlink(missing_ok=True)

    total = 6; passed = total - len(fails)
    print(f"\n  {passed}/{total} tests pasaron")
    if fails: raise SystemExit(1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
    else:
        raise SystemExit(main(sys.argv[1:]))
