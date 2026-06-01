#!/usr/bin/env python3
"""
bago_security_audit.py - Auditoria forense de seguridad para BAGO 4.1.5

Escanea el repositorio (o una ruta dada) en busca de tokens/credenciales
expuestos y revisa la configuracion de git y de secretos locales.

Portado desde BAGO 3.x y adaptado a 4.1.5:
- Raiz de escaneo parametrizable (--root); por defecto, la raiz del repo.
- Sin rutas ni identidades hardcodeadas.
- Salida ASCII-safe (sin emojis) para consolas Windows (cp1252).

Uso:
    python .bago/tools/bago_security_audit.py
    python .bago/tools/bago_security_audit.py --root C:\\ruta --output report.json
    python .bago/tools/bago_security_audit.py --home   # escanea tambien el HOME
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Patrones de tokens sensibles
TOKEN_PATTERNS = {
    "github_pat_classic": re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    "github_pat_fine": re.compile(r"github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}"),
    "openai_sk": re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    "openai_sk_proj": re.compile(r"sk-proj-[a-zA-Z0-9_-]+"),
    "anthropic_key": re.compile(r"sk-ant-[a-zA-Z0-9_-]+"),
    "telegram_bot": re.compile(r"[0-9]{9,10}:[a-zA-Z0-9_-]{35}"),
    "generic_bearer": re.compile(r"Bearer\s+[a-zA-Z0-9\-_]{20,}"),
    "generic_api_key": re.compile(r"(?i)(api[_-]?key|apikey)\s*=\s*['\"][a-zA-Z0-9]{16,}['\"]"),
}

EXCLUDE_DIRS = {"node_modules", "__pycache__", ".git", "dist", "build", ".venv", "venv", "temp", "tmp"}
EXCLUDE_EXTS = {".exe", ".dll", ".bin", ".zip", ".jpg", ".png", ".mp3", ".mp4", ".ico", ".so", ".pyc"}

REPORT: dict = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "findings": [],
    "score": 100,
}


def _repo_root() -> Path:
    # .bago/tools/ -> repo root es parents[2]
    return Path(__file__).resolve().parents[2]


def add_finding(severity: str, category: str, detail: str, file: str = "") -> None:
    REPORT["findings"].append({
        "severity": severity,
        "category": category,
        "detail": detail,
        "file": str(file),
    })
    REPORT["score"] -= {"CRITICAL": 25, "HIGH": 15, "MEDIUM": 5, "LOW": 1}.get(severity, 0)


def scan_file(path: Path) -> list[dict]:
    findings: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings
    for token_type, pattern in TOKEN_PATTERNS.items():
        for match in pattern.finditer(text):
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            line = text[line_start:line_end if line_end != -1 else None]
            low = line.lower()
            if any(tok in low for tok in ("noqa", "test", "fixture", "example")):
                continue
            # Descartar placeholders de documentacion (sk-ant-x..., <token>, XXXX, your_key)
            if any(ph in low for ph in ("...", "xxxx", "<", "your_", "placeholder", "tu_", "set anthropic", "set openai", "set ")):
                continue
            findings.append({"type": token_type, "file": str(path), "line": line.strip()})
    return findings


def scan_directory(root: Path, max_size: int = 500_000) -> list[dict]:
    findings: list[dict] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in EXCLUDE_EXTS:
            continue
        try:
            if path.stat().st_size > max_size:
                continue
        except OSError:
            continue
        findings.extend(scan_file(path))
    return findings


def check_git_config() -> None:
    try:
        listing = subprocess.check_output(
            ["git", "config", "--global", "--list"], text=True, stderr=subprocess.DEVNULL
        )
    except Exception:
        return
    if "credential.helper" in listing:
        try:
            helper = subprocess.check_output(
                ["git", "config", "--global", "credential.helper"], text=True, stderr=subprocess.DEVNULL
            ).strip()
            if helper and "manager" not in helper.lower():
                add_finding("MEDIUM", "git_config", f"credential.helper no es GCM: {helper}")
        except Exception:
            pass


def check_secrets_file(root: Path) -> None:
    candidates = [
        Path.home() / ".bago_secrets.json",
        root / ".bago" / "credentials.json",
        root / ".bago" / "session-credentials.json",
    ]
    for secrets in candidates:
        if not secrets.exists():
            continue
        try:
            mode = secrets.stat().st_mode
            if os.name != "nt" and (mode & 0o077):
                add_finding("HIGH", "file_permissions",
                            f"{secrets} accesible por grupo/otros (mode {oct(mode)})", str(secrets))
        except OSError:
            pass
        try:
            data = json.loads(secrets.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            add_finding("HIGH", "secrets_file", f"{secrets} contiene JSON invalido", str(secrets))
            continue
        except Exception:
            continue
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and len(value) > 20:
                    add_finding("CRITICAL", "secrets_file",
                                f"Posible token '{key}' en texto plano (revisa que este en .gitignore)", str(secrets))


def check_git_tracked_secrets(root: Path) -> None:
    """Avisa si algun archivo de DATOS con secretos esta rastreado por git.

    Solo marca ficheros de datos (.json/.env/.yaml/.ini/...) cuyo nombre sugiere
    secretos; el codigo fuente (p.ej. credential_manager.py) NO se marca.
    """
    secret_exts = {".json", ".env", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".toml"}
    try:
        tracked = subprocess.check_output(
            ["git", "-C", str(root), "ls-files"], text=True, stderr=subprocess.DEVNULL
        )
    except Exception:
        return
    for line in tracked.splitlines():
        name = line.rsplit("/", 1)[-1].lower()
        suffix = ("." + name.rsplit(".", 1)[-1]) if "." in name else ""
        is_data = suffix in secret_exts or name == ".env"
        if is_data and ("credential" in name or "secret" in name or name == ".env"):
            add_finding("CRITICAL", "git_tracked_secret",
                        f"Archivo de secretos rastreado por git: {line}", line)


def generate_report(output_path: Path | None = None) -> None:
    REPORT["score"] = max(0, REPORT["score"])
    by_sev: dict[str, list] = {}
    for f in REPORT["findings"]:
        by_sev.setdefault(f["severity"], []).append(f)

    print("=" * 70)
    print("  BAGO SECURITY AUDIT REPORT")
    print(f"  Generado: {REPORT['timestamp']}")
    print("=" * 70)
    print(f"\n  Puntuacion de seguridad: {REPORT['score']}/100")
    if REPORT["score"] >= 80:
        print("  Estado: [BUENO]")
    elif REPORT["score"] >= 50:
        print("  Estado: [MODERADO]")
    else:
        print("  Estado: [CRITICO]")

    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        if sev in by_sev:
            print(f"\n  [{sev}] - {len(by_sev[sev])} hallazgos")
            for f in by_sev[sev]:
                info = f"  -> {f['file']}" if f["file"] else ""
                print(f"    - {f['category']}: {f['detail']}{info}")

    if not REPORT["findings"]:
        print("\n  No se detectaron hallazgos. Mantiene buenas practicas.")
    else:
        print("\n" + "=" * 70)
        print("  RECOMENDACIONES:")
        print("=" * 70)
        print("  - Revoca cualquier token expuesto en su proveedor (GitHub/OpenAI/...).")
        print("  - Verifica que credentials.json y secretos esten en .gitignore.")
        print("  - Usa Windows Credential Manager o variables de entorno, no texto plano.")

    if output_path:
        output_path.write_text(json.dumps(REPORT, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n  Informe guardado en: {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditoria de seguridad BAGO 4.1.5")
    parser.add_argument("--root", type=Path, default=_repo_root(),
                        help="Raiz a escanear (por defecto, la raiz del repo).")
    parser.add_argument("--home", action="store_true",
                        help="Escanea tambien el directorio HOME del usuario.")
    parser.add_argument("--output", type=Path, help="Guarda el informe JSON en la ruta indicada.")
    args = parser.parse_args()

    print("Iniciando auditoria de seguridad BAGO...")
    roots = [args.root]
    if args.home:
        roots.append(Path.home())
    for root in roots:
        if root.exists():
            print(f"   Escaneando: {root}")
            for f in scan_directory(root):
                add_finding("CRITICAL", "exposed_token",
                            f"Token {f['type']} expuesto: {f['line'][:60]}...", f["file"])

    check_git_config()
    check_secrets_file(args.root)
    check_git_tracked_secrets(args.root)

    generate_report(args.output)
    return 0 if REPORT["score"] >= 50 else 1


if __name__ == "__main__":
    sys.exit(main())
