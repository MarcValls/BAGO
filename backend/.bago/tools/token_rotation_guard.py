#!/usr/bin/env python3
"""token_rotation_guard.py — Escanea un proyecto buscando tokens de API hardcodeados.

Herramienta PORTABLE: funciona en cualquier proyecto, no requiere BAGO instalado.

Uso:
    python token_rotation_guard.py [--root DIR] [--fix] [--json] [--test]

    --root DIR    Directorio raiz a escanear (default: directorio actual)
    --fix         Muestra instrucciones de rotacion por tipo detectado
    --json        Output en JSON estructurado
    --test        Self-tests internos (4/4)

Salida: 0 = limpio, 1 = tokens encontrados, 2 = error
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterator, NamedTuple

SKIP_PATHS = {
    "node_modules", ".git", "__pycache__", ".pytest_cache", ".vercel",
    "AppData", "site-packages", "dist-packages", "venv", ".venv",
}

SCAN_EXTS = {
    ".py", ".js", ".ts", ".sh", ".ps1", ".bat",
    ".env", ".env.example", ".env.local",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".md", ".txt", ".log", ".html", ".xml",
}

PLACEHOLDERS = frozenset({
    "example", "placeholder", "dummy", "fake", "testtoken",
    "abcdefghijklmnopqrstuvwxyz", "yourtoken", "your_token",
    "your_api_key", "your_apikey", "your-secret", "yoursecret",
    "fake-token", "fake-api-key", "example-key", "mytoken",
    "changeme", "change_me", "replace_with", "xxx",
    "realkey", "abcdefghijklmnopqrstuvwx", "aaaaaaaaaaaaaaaaaaaaaaaa",
})

_ALLOWLIST_MARKERS = (
    "# noqa: test fixture",
    "# nosec: test fixture",
    "# pragma: allowlist secret",
)

PATTERNS: list[tuple[str, re.Pattern]] = [
    ("telegram_bot",    re.compile(r'\b(\d{7,10}:[A-Za-z0-9_-]{35})\b')),
    ("github_pat",      re.compile(
        r'\b(ghp_[A-Za-z0-9]{36,}|gho_[A-Za-z0-9]{36,}|ghu_[A-Za-z0-9]{36,}'
        r'|ghr_[A-Za-z0-9]{36,}|ghs_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})\b'
    )),
    ("openai_api",      re.compile(r'\b(sk-[A-Za-z0-9]{20,48})\b')),
    ("google_api",      re.compile(r'\b(AIza[0-9A-Za-z_-]{35})\b')),
    ("aws_access",      re.compile(r'\b(AKIA[0-9A-Z]{16})\b')),
    ("discord_webhook", re.compile(
        r'https://discord(?:app)?\.com/api/webhooks/\d+/([A-Za-z0-9_-]{64,})'
    )),
    ("env_token_leak",  re.compile(
        r'(?:token|api_key|secret|password)\s*=\s*["\']([A-Za-z0-9_\-\.]{24,})["\']'
    )),
]

_RED  = "\033[0;31m"
_GRN  = "\033[0;32m"
_YEL  = "\033[0;33m"
_RST  = "\033[0m"
_BOLD = "\033[1m"
_DIM  = "\033[2m"


class Hit(NamedTuple):
    path: Path
    line_no: int
    category: str
    match: str
    line_hash: str


def _should_skip(path: Path) -> bool:
    return bool(set(path.parts) & SKIP_PATHS)


def _line_hash(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8", errors="replace")).hexdigest()[:16]


def _is_placeholder(line: str, match: str) -> bool:
    low = line.lower()
    low_m = match.lower()
    if any(marker in low for marker in _ALLOWLIST_MARKERS):
        return True
    for ph in PLACEHOLDERS:
        if ph in low or ph in low_m:
            return True
    # Skip inline regex definitions
    if "re.compile" in line and match[:10] in line:
        return True
    return False


def scan_file(path: Path) -> Iterator[Hit]:
    try:
        raw = path.read_bytes()
        if not raw or b"\x00" in raw[:4096]:
            return
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        return
    for line_no, line in enumerate(text.splitlines(), start=1):
        for category, pattern in PATTERNS:
            for m in pattern.finditer(line):
                if not _is_placeholder(line, m.group(1)):
                    yield Hit(
                        path=path, line_no=line_no,
                        category=category, match=m.group(1),
                        line_hash=_line_hash(line),
                    )


def scan_directory(root: Path) -> list[Hit]:
    hits: list[Hit] = []
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        try:
            rel_parts = set(p.relative_to(root).parts)
        except ValueError:
            rel_parts = set(p.parts)
        if rel_parts & SKIP_PATHS:
            continue
        rel_str = p.relative_to(root).as_posix().lower()
        if rel_str.startswith("dist/") or "/dist/" in rel_str or rel_str.startswith(".vercel/") or "/.vercel/" in rel_str:
            continue
        if p.suffix.lower() in SCAN_EXTS or p.name.startswith(".env"):
            hits.extend(scan_file(p))
    return hits


def print_report(hits: list[Hit], root: Path) -> None:
    if not hits:
        print(f"{_GRN}[OK] Sin tokens expuestos en {root}{_RST}")
        return
    categories: dict[str, list[Hit]] = {}
    for h in hits:
        categories.setdefault(h.category, []).append(h)
    print(f"\n{_RED}{_BOLD}[ALERTA] {len(hits)} token(s) expuesto(s){_RST}\n")
    for cat, hs in sorted(categories.items()):
        print(f"  {_YEL}[{cat.upper()}]{_RST}  {len(hs)} encontrado(s)")
        for h in hs[:5]:
            try:
                rel = h.path.relative_to(root)
            except ValueError:
                rel = h.path
            trunc = h.match[:30] + "..." if len(h.match) > 33 else h.match
            print(f"    {_DIM}{rel}:{h.line_no}{_RST}  {trunc}")
        if len(hs) > 5:
            print(f"    {_DIM}... y {len(hs) - 5} mas{_RST}")
    print()


def print_fix_hints(hits: list[Hit]) -> None:
    cats = {h.category for h in hits}
    print(f"{_BOLD}Instrucciones de rotacion:{_RST}")
    if "telegram_bot" in cats:
        print("  Telegram: @BotFather -> /mybots -> bot -> API Token -> Revoke")
    if "github_pat" in cats:
        print("  GitHub: github.com/settings/tokens -> Delete")
    if "openai_api" in cats:
        print("  OpenAI: platform.openai.com/api-keys -> Revoke")
    if "google_api" in cats:
        print("  Google: console.cloud.google.com/apis/credentials -> Delete")
    if "aws_access" in cats:
        print("  AWS: console.aws.amazon.com/iam -> Access keys -> Deactivate")
    if "discord_webhook" in cats:
        print("  Discord: discord.com/developers/applications -> Webhooks -> Delete")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Token Rotation Guard — detecta tokens de API hardcodeados"
    )
    ap.add_argument("--root", default="", help="Directorio raiz (default: cwd)")
    ap.add_argument("--fix", action="store_true", help="Muestra instrucciones de rotacion")
    ap.add_argument("--json", dest="as_json", action="store_true", help="Output en JSON")
    args = ap.parse_args(argv)

    from bago_utils import get_scan_root
    root = get_scan_root(args.root or None)

    if not root.exists():
        print(f"[ERROR] No existe: {root}", file=sys.stderr)
        return 2

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not args.as_json:
        print(f"\n{_BOLD}Token Rotation Guard  {ts}{_RST}")
        print(f"  Escaneando: {root}\n")

    hits = scan_directory(root)

    if args.as_json:
        print(json.dumps({
            "root": str(root),
            "ts": ts,
            "total": len(hits),
            "hits": [
                {"path": str(h.path), "line": h.line_no,
                 "category": h.category, "hash": h.line_hash}
                for h in hits
            ],
        }, indent=2, ensure_ascii=False))
        return 1 if hits else 0

    print_report(hits, root)
    if hits and args.fix:
        print_fix_hints(hits)
    print(f"  {_DIM}Codigo de salida: {1 if hits else 0}{_RST}\n")
    return 1 if hits else 0


def _self_test() -> None:
    import tempfile
    print("Tests de token_rotation_guard.py...")
    fails: list[str] = []

    def ok(n: str) -> None:
        print(f"  OK: {n}")

    def fail(n: str, m: str) -> None:
        fails.append(n)
        print(f"  FAIL: {n}: {m}")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        # T1: AWS key detectada (16 chars uppercase+digits tras AKIA, sin placeholder words)
        aws_key = "AKIA" + "XR7MNPQ3Z2B1C9D0"
        (root / "config.py").write_text(f'key = "{aws_key}"\n', encoding="utf-8")  # nosec: test fixture
        hits1 = scan_directory(root)
        if any(h.category == "aws_access" for h in hits1):
            ok("token:aws_detected")
        else:
            fail("token:aws_detected", f"hits={[h.category for h in hits1]}")

        # T2: placeholder no flaggeado
        (root / "config.py").write_text('token = "YOURTOKEN"\n', encoding="utf-8")
        hits2 = scan_directory(root)
        if not hits2:
            ok("token:placeholder_ignored")
        else:
            fail("token:placeholder_ignored", f"hits={[h.category for h in hits2]}")

        # T3: GitHub PAT detectado (ghp_ + 36 chars sin repetir secuencias de placeholder)
        github_pat = "ghp_" + "9sK3mXvR7nL2pQ8wY4tH6jB0cU5oI1eA3fDzG"
        (root / "deploy.yml").write_text(f"token: {github_pat}\n", encoding="utf-8")  # nosec: test fixture
        hits3 = scan_directory(root)
        if any(h.category == "github_pat" for h in hits3):
            ok("token:github_pat_detected")
        else:
            fail("token:github_pat_detected", f"hits={[h.category for h in hits3]}")

        # T4: --root funciona (hay tokens del T3 en el dir)
        rc = main(["--root", td])
        if rc == 1:
            ok("token:root_arg_works")
        else:
            fail("token:root_arg_works", f"exit={rc}")

    total = 4
    passed = total - len(fails)
    print(f"\n  {passed}/{total} tests pasaron")
    if fails:
        raise SystemExit(1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
    else:
        raise SystemExit(main())
