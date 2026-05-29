#!/usr/bin/env python3
"""
bago_security_audit.py — Auditoría forense de seguridad BAGO
Escanea tokens expuestos, configuración comprometida, y credenciales en riesgo.

Uso: python bago_security_audit.py [--fix]
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Patterns de tokens sensibles
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

# Archivos y directorios a excluir
EXCLUDE_DIRS = {"node_modules", "__pycache__", ".git", "_ARCHIVO_BAGO", "temp", "tmp"}
EXCLUDE_EXTS = {".exe", ".dll", ".bin", ".zip", ".jpg", ".png", ".mp3", ".mp4"}

REPORT = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "findings": [],
    "risks": [],
    "recommendations": [],
    "score": 100,
}


def add_finding(severity: str, category: str, detail: str, file: str = "", fixable: bool = False):
    REPORT["findings"].append({
        "severity": severity,
        "category": category,
        "detail": detail,
        "file": str(file),
        "fixable": fixable,
    })
    if severity == "CRITICAL":
        REPORT["score"] -= 25
    elif severity == "HIGH":
        REPORT["score"] -= 15
    elif severity == "MEDIUM":
        REPORT["score"] -= 5
    elif severity == "LOW":
        REPORT["score"] -= 1


def scan_file(path: Path) -> list[dict]:
    """Escanea un archivo en busca de tokens expuestos."""
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings
    for token_type, pattern in TOKEN_PATTERNS.items():
        for match in pattern.finditer(text):
            # Ignorar test fixtures
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            line = text[line_start:line_end]
            if "noqa" in line.lower() or "test" in line.lower() or "fixture" in line.lower() or "example" in line.lower():
                continue
            findings.append({
                "type": token_type,
                "file": str(path),
                "line": line.strip(),
                "start": match.start(),
            })
    return findings


def scan_directory(root: Path, max_size: int = 500_000) -> list[dict]:
    """Escanea recursivamente un directorio."""
    findings = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in EXCLUDE_EXTS:
            continue
        if path.stat().st_size > max_size:
            continue
        findings.extend(scan_file(path))
    return findings


def check_git_config():
    """Verifica configuración de git."""
    try:
        name = subprocess.check_output(["git", "config", "--global", "user.name"], text=True, stderr=subprocess.DEVNULL).strip()
        email = subprocess.check_output(["git", "config", "--global", "user.email"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        name = email = ""

    if not name or name in {"BAGO Sync", "root", "admin", "user", "test"}:
        add_finding("HIGH", "git_config", f"user.name sospechoso o genérico: '{name}'", fixable=True)
    if not email or email in {"bago@amtechnologies.es", "root@localhost", "admin@localhost", "user@example.com"}:
        add_finding("HIGH", "git_config", f"user.email sospechoso o genérico: '{email}'", fixable=True)
    if "credential.helper" in subprocess.check_output(["git", "config", "--global", "--list"], text=True, stderr=subprocess.DEVNULL):
        cred_helper = subprocess.check_output(["git", "config", "--global", "credential.helper"], text=True, stderr=subprocess.DEVNULL).strip()
        if "manager" not in cred_helper.lower():
            add_finding("MEDIUM", "git_config", f"credential.helper no es GCM: {cred_helper}")


def check_credential_manager():
    """Verifica credenciales almacenadas en Windows Credential Manager."""
    try:
        output = subprocess.check_output(["cmdkey", "/list"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return
    github_creds = [line for line in output.splitlines() if "github" in line.lower()]
    if github_creds:
        add_finding("MEDIUM", "credential_manager", f"{len(github_creds)} credenciales de GitHub en Windows Credential Manager")


def check_file_permissions(path: Path):
    """Verifica permisos de archivos sensibles."""
    if not path.exists():
        return
    try:
        mode = path.stat().st_mode
        if mode & 0o077:
            add_finding("HIGH", "file_permissions", f"Archivo {path} tiene permisos de grupo/otros (mode {oct(mode)})", str(path), fixable=True)
    except Exception:
        pass


def check_secrets_file():
    """Verifica ~/.bago_secrets.json."""
    secrets = Path.home() / ".bago_secrets.json"
    if secrets.exists():
        check_file_permissions(secrets)
        try:
            data = json.loads(secrets.read_text(encoding="utf-8"))
            for key, value in data.items():
                if isinstance(value, str) and len(value) > 20:
                    # Verificar si el token parece activo (no revocado)
                    add_finding("CRITICAL", "secrets_file", f"Token '{key}' almacenado en texto plano en {secrets}", str(secrets))
        except json.JSONDecodeError:
            add_finding("HIGH", "secrets_file", f"{secrets} contiene JSON inválido", str(secrets))


def check_windows_defender():
    """Verifica estado de Windows Defender."""
    try:
        output = subprocess.check_output(
            ["powershell", "-Command", "Get-MpComputerStatus | Select-Object RealTimeProtectionEnabled, AntivirusEnabled"],
            text=True, stderr=subprocess.DEVNULL,
        )
        if "False" in output:
            add_finding("HIGH", "antivirus", "Windows Defender desactivado o protección en tiempo real desactivada")
    except Exception:
        add_finding("MEDIUM", "antivirus", "No se pudo verificar estado de Windows Defender")


def check_firewall():
    """Verifica estado del firewall."""
    try:
        output = subprocess.check_output(["netsh", "advfirewall", "show", "currentprofile"], text=True, stderr=subprocess.DEVNULL)
        if "State                                 OFF" in output:
            add_finding("HIGH", "firewall", "Firewall de Windows desactivado para el perfil actual")
    except Exception:
        pass


def check_recent_logins():
    """Verifica inicios de sesión recientes sospechosos."""
    try:
        output = subprocess.check_output(
            ["powershell", "-Command", "Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4624; StartTime=(Get-Date).AddDays(-7)} -MaxEvents 20 | Select-Object TimeCreated, @{N='Type';E={$_.Properties[8].Value}}, @{N='User';E={$_.Properties[5].Value}}, @{N='IP';E={$_.Properties[18].Value}}"],
            text=True, stderr=subprocess.DEVNULL,
        )
        if output.strip():
            add_finding("LOW", "logins", "Revisa inicios de sesión recientes en logs de Windows")
    except Exception:
        pass


def check_browser_extensions():
    """Verifica extensiones de navegador instaladas recientemente."""
    brave_ext = Path.home() / "AppData/Local/BraveSoftware/Brave-Browser/User Data/Default/Extensions"
    if brave_ext.exists():
        recent = [d for d in brave_ext.rglob("*") if d.is_dir() and d.stat().st_mtime > (datetime.now().timestamp() - 7*86400)]
        if len(recent) > 5:
            add_finding("MEDIUM", "browser_extensions", f"{len(recent)} extensiones de Brave modificadas/instaladas en los últimos 7 días")


def generate_report(output_path: Path | None = None):
    """Genera informe de auditoría."""
    REPORT["score"] = max(0, REPORT["score"])
    findings_by_severity = {}
    for f in REPORT["findings"]:
        findings_by_severity.setdefault(f["severity"], []).append(f)

    print("=" * 70)
    print("  BAGO SECURITY AUDIT REPORT")
    print(f"  Generado: {REPORT['timestamp']}")
    print("=" * 70)
    print(f"\n  Puntuación de seguridad: {REPORT['score']}/100")
    if REPORT["score"] >= 80:
        print("  Estado: 🟢 BUENO")
    elif REPORT["score"] >= 50:
        print("  Estado: 🟡 MODERADO")
    else:
        print("  Estado: 🔴 CRÍTICO")

    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        if sev in findings_by_severity:
            print(f"\n  [{sev}] — {len(findings_by_severity[sev])} hallazgos")
            for f in findings_by_severity[sev]:
                file_info = f"  → {f['file']}" if f["file"] else ""
                print(f"    • {f['category']}: {f['detail']}{file_info}")

    print("\n" + "=" * 70)
    print("  RECOMENDACIONES INMEDIATAS:")
    print("=" * 70)
    if "CRITICAL" in findings_by_severity or "HIGH" in findings_by_severity:
        print("  1. REVOCAR TODOS LOS TOKENS EXPUESTOS en GitHub Settings → Tokens")
        print("  2. CAMBIAR CONTRASEÑAS de GitHub, Microsoft, y OpenAI")
        print("  3. HABILITAR 2FA en TODAS las cuentas críticas")
        print("  4. REVISAR sesiones activas y cerrar las desconocidas")
        print("  5. ESCANEAR con antivirus actualizado")
        print("  6. RESTAURAR git config: git config --global user.name 'Tu Nombre'")
        print("  7. RESTAURAR git config: git config --global user.email 'tu@email.com'")
    else:
        print("  No se detectaron riesgos críticos. Mantén buenas prácticas.")

    if output_path:
        output_path.write_text(json.dumps(REPORT, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n  Informe guardado en: {output_path}")


def apply_fixes():
    """Aplica correcciones automáticas donde sea seguro hacerlo."""
    fixes_applied = []
    # Restaurar git config si está comprometida
    try:
        name = subprocess.check_output(["git", "config", "--global", "user.name"], text=True, stderr=subprocess.DEVNULL).strip()
        if name in {"BAGO Sync", "root", "admin", "user", "test"} or not name:
            subprocess.run(["git", "config", "--global", "user.name", "Marc Valls"], check=False)
            fixes_applied.append("Restaurado git user.name a 'Marc Valls'")
    except Exception:
        pass

    try:
        email = subprocess.check_output(["git", "config", "--global", "user.email"], text=True, stderr=subprocess.DEVNULL).strip()
        if email in {"bago@amtechnologies.es", "root@localhost", "admin@localhost", "user@example.com"} or not email:
            subprocess.run(["git", "config", "--global", "user.email", "marcvallssanvictor@gmail.com"], check=False)
            fixes_applied.append("Restaurado git user.email a 'marcvallssanvictor@gmail.com'")
    except Exception:
        pass

    # Ajustar permisos de .bago_secrets.json
    secrets = Path.home() / ".bago_secrets.json"
    if secrets.exists():
        try:
            os.chmod(secrets, 0o600)
            fixes_applied.append(f"Permisos de {secrets} ajustados a 600")
        except Exception:
            pass

    if fixes_applied:
        print("\n  Correcciones aplicadas:")
        for f in fixes_applied:
            print(f"    ✓ {f}")
    else:
        print("\n  No se encontraron correcciones aplicables automáticamente.")


def main():
    parser = argparse.ArgumentParser(description="Auditoría de seguridad BAGO")
    parser.add_argument("--fix", action="store_true", help="Aplica correcciones automáticas")
    parser.add_argument("--output", type=Path, help="Guarda informe JSON en ruta especificada")
    args = parser.parse_args()

    print("🔍 Iniciando auditoría de seguridad BAGO...")
    print("   Escaneando tokens expuestos, configuración y credenciales...\n")

    # Escaneo del framework y home
    home = Path.home()
    bago_fw = Path("E:/bago_fw")

    for scan_root in [home, bago_fw]:
        if scan_root.exists():
            findings = scan_directory(scan_root)
            for f in findings:
                add_finding("CRITICAL", "exposed_token", f"Token {f['type']} expuesto en línea: {f['line'][:60]}...", f["file"])

    check_git_config()
    check_credential_manager()
    check_secrets_file()
    check_windows_defender()
    check_firewall()
    check_recent_logins()
    check_browser_extensions()

    generate_report(args.output)

    if args.fix:
        print("\n" + "=" * 70)
        apply_fixes()

    sys.exit(0 if REPORT["score"] >= 50 else 1)


if __name__ == "__main__":
    main()
