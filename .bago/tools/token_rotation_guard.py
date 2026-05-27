#!/usr/bin/env python3
"""
BAGO Token Rotation Guard
─────────────────────────────────────────────────────────────────
Escanea el árbol de BAGO buscando tokens de API hardcodeados.
Ignora ejemplos/demo (placeholders conocidos).

Uso:
    python token_rotation_guard.py [scan|clean|audit] [--fix] [--delete-secrets]

Salida: 0 = limpio, 1 = secrets encontrados, 2 = error
─────────────────────────────────────────────────────────────────
"""

import re
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Iterator, NamedTuple

# ── Config ───────────────────────────────────────────────────────────────────
HOME = Path.home()
BAGO_ROOTS = [
    Path("E:/bago_fw"),
    Path("E:/.bago"),
    Path("E:/tmp"),
    Path("E:/bago-knowledge"),
    Path(__file__).resolve().parents[3],
]

SKIP_PATHS = {
    "node_modules", ".git", "__pycache__", ".pytest_cache",
    "NVIDIA", "npm-cache", "pagefile.sys", "System Volume Information",
    "AppData", "ProgramData", "site-packages", "dist-packages",
}

SCAN_FILES = {
    ".py", ".js", ".ts", ".sh", ".ps1", ".bat",
    ".env", ".env.example", ".env.local",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".md", ".txt", ".log", ".html", ".xml",
}

# Known placeholder / example strings to EXCLUDE (case-insensitive)
PLACEHOLDERS = {
    "example", "EXAMPLE", "placeholder", "PLACEHOLDER",
    "dummy", "DUMMY", "fake", "FAKE", "testtoken", "TESTTOKEN",
    "abcdefghijklmnopqrstuvwxyz", "yourtoken", "YOUR_TOKEN",
    "your_api_key", "your_apikey", "your-secret", "yoursecret",
    "fake-token", "fake-api-key", "example-key", "mytoken",
    "changeme", "CHANGE_ME", "replace_with", "xxx",
    "REALKEY", "AbCdEfGhIjKlMnOpQrStUvWx",
}

# ── Regex secret hunters ────────────────────────────────────────────────────────
PATTERNS = [
    ("telegram_bot", re.compile(r'\b(\d{7,10}:[A-Za-z0-9_-]{35})\b')),
    ("github_pat",    re.compile(r'\b(ghp_[A-Za-z0-9]{36}|gho_[A-Za-z0-9]{36}|ghu_[A-Za-z0-9]{36}|ghr_[A-Za-z0-9]{36}|ghs_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,})\b')),
    ("openai_api",    re.compile(r'\b(sk-[A-Za-z0-9]{20,48})\b')),
    ("google_api",    re.compile(r'\b(AIza[0-9A-Za-z_-]{35})\b')),
    ("aws_access",    re.compile(r'\b(AKIA[0-9A-Z]{16})\b')),
    ("discord_webhook",re.compile(r'https://discord(?:app)?\.com/api/webhooks/\d+/([A-Za-z0-9_-]{64,})')),
    ("env_token_leak",re.compile(r'(?:token|api_key|secret|password)\s*=\s*["\']([A-Za-z0-9_\-\.]{24,})["\']')),
]

class Hit(NamedTuple):
    path: Path
    line_no: int
    category: str
    match: str
    line_hash: str

def _should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & SKIP_PATHS:
        return True
    for s in SKIP_PATHS:
        if s in path.parts:
            return True
    return False

def _line_hash(line: str) -> str:
    return hashlib.sha256(line.encode('utf-8', errors='replace')).hexdigest()[:16]

def _is_placeholder(line: str, match: str) -> bool:
    """Return True if this is a known demo/example string."""
    low = line.lower()
    low_match = match.lower()
    for ph in PLACEHOLDERS:
        if ph.lower() in low or ph.lower() in low_match:
            return True
    # Exclude lines that look like compile/regex definitions
    if 're.compile' in line and match[:10] in line:
        return True
    return False

def scan_file(path: Path) -> Iterator[Hit]:
    try:
        raw = path.read_bytes()
        if not raw or b'\x00' in raw[:4096]:
            return
        text = raw.decode('utf-8', errors='replace')
    except Exception:
        return

    for line_no, line in enumerate(text.splitlines(), start=1):
        for category, pattern in PATTERNS:
            for m in pattern.finditer(line):
                if _is_placeholder(line, m.group(1)):
                    continue
                yield Hit(
                    path=path,
                    line_no=line_no,
                    category=category,
                    match=m.group(1),
                    line_hash=_line_hash(line),
                )

def scan_directory(root: Path) -> Iterator[Hit]:
    if not root.exists():
        return
    for p in root.rglob('*'):
        if p.is_dir() or _should_skip(p):
            continue
        if p.suffix.lower() in SCAN_FILES or p.name.startswith('.env'):
            yield from scan_file(p)

class Actions:
    @staticmethod
    def print_report(hits: list[Hit]):
        if not hits:
            print("\n  ✅  SIN SECRETS EXPUESTOS  —  árbol BAGO limpio\n")
            return
        categories: dict[str, list[Hit]] = {}
        for h in hits:
            categories.setdefault(h.category, []).append(h)
        print(f"\n  🔴  {len(hits)} SECRETS EXPUESTOS ENCONTRADOS\n")
        print("  ═" + "═" * 78)
        for cat, hs in sorted(categories.items()):
            print(f"\n  ⚠️  {cat.upper()}  ({len(hs)} encontrados)")
            print("  ─" + "─" * 78)
            for h in hs:
                match_trunc = h.match[:30] + "..." if len(h.match) > 33 else h.match
                rel = str(h.path.relative_to(Path('E:/').resolve()))
                print(f"    📁 {rel}")
                print(f"       línea {h.line_no}  →  {match_trunc}")
        print("\n  ═" + "═" * 78)

    @staticmethod
    def write_evidence(hits: list[Hit]):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        ev_path = Path("E:/bago_fw/.bago/state/evidences")
        ev_path.mkdir(parents=True, exist_ok=True)
        out = {
            "ts": datetime.now().isoformat(),
            "tool": "token_rotation_guard",
            "severity": "CRITICAL" if hits else "OK",
            "total_hits": len(hits),
            "hits": [
                {
                    "path": str(h.path),
                    "relative": str(h.path.relative_to(Path('E:/').resolve())),
                    "line": h.line_no,
                    "category": h.category,
                    "match_sha256": h.line_hash,
                }
                for h in hits
            ],
        }
        fpath = ev_path / f"TOKEN_AUDIT_{ts}.json"
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"  📝  Evidencia guardada: {fpath}")

    @staticmethod
    def delete_found(hits: list[Hit]):
        unique_paths = sorted({h.path for h in hits if h.path.exists()})
        if not unique_paths:
            return
        print(f"\n  🗑️  Archivos eliminados ({len(unique_paths)}):")
        for p in unique_paths:
            try:
                p.unlink()
                print(f"    ✅ {p}")
            except Exception as e:
                print(f"    ❌ {p} — {e}")

def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="BAGO Token Rotation Guard")
    ap.add_argument("action", nargs="?", default="scan", choices=["scan", "clean", "audit"])
    ap.add_argument("--fix", action="store_true", help="Muestra instrucciones de rotación")
    ap.add_argument("--delete-secrets", action="store_true", help="[PELIGROSO] Borra archivos con secrets")
    args = ap.parse_args()

    roots = list(dict.fromkeys(BAGO_ROOTS))
    hits: list[Hit] = []
    scanned = 0

    print(f"\n  🔐 BAGO Token Rotation Guard  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Escaneando {len(roots)} raíces (filters de ejemplo activos)...\n")

    for root in roots:
        if not root.exists():
            continue
        for hit in scan_directory(root):
            hits.append(hit)
        scanned += sum(1 for _ in root.rglob('*') if _.is_file())

    Actions.print_report(hits)
    Actions.write_evidence(hits)

    if hits and args.fix:
        print("\n  ⚡  INSTRUCCIONES DE ROTACIÓN:")
        cats = {h.category for h in hits}
        if "telegram_bot" in cats:
            print("    → Telegram: @BotFather → /mybots → bot → API Token → Revoke")
        if "github_pat" in cats:
            print("    → GitHub: github.com/settings/tokens → Delete")
        if "openai_api" in cats:
            print("    → OpenAI: platform.openai.com/api-keys → Revoke")
        if "google_api" in cats:
            print("    → Google: console.cloud.google.com/apis/credentials → Delete")
        if "aws_access" in cats:
            print("    → AWS: console.aws.amazon.com/iam → Access keys → Deactivate")

    if args.delete_secrets and hits:
        Actions.delete_found(hits)

    print(f"  📊  Archivos escaneados (aprox): {scanned}")
    print(f"  🏁  Código de salida: {1 if hits else 0}\n")
    return 1 if hits else 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  🛑 Cancelado por usuario")
        sys.exit(130)
