#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pre_push_guard.py - Gate de sincronizacion remota BAGO.

Bloquea pushes que puedan publicar un BAGO roto:
  - arbol de trabajo sucio
  - rama local por detras/divergida del upstream
  - validadores canónicos en KO
  - sincerity estricto con hallazgos
  - suite de integracion con referencias muertas

Uso:
  python3 .bago/tools/pre_push_guard.py
  python3 .bago/tools/pre_push_guard.py --remote
  python3 .bago/tools/pre_push_guard.py --test
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(cmd: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        result = subprocess.run(
            cmd,
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        return result.returncode, (result.stdout + result.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"


def check(name: str, cmd: list[str], timeout: int = 120) -> bool:
    rc, out = run(cmd, timeout=timeout)
    if rc == 0:
        print(f"  OK   {name}")
        return True
    print(f"  FAIL {name} (exit={rc})")
    if out:
        for line in out.splitlines()[:20]:
            print(f"       {line}")
    return False


def git_output(args: list[str]) -> tuple[int, str]:
    return run(["git", *args], timeout=30)


def check_clean_tree() -> bool:
    rc, out = git_output(["status", "--porcelain"])
    if rc != 0:
        print("  FAIL git status")
        print(out)
        return False
    if out.strip():
        print("  FAIL working tree limpio")
        for line in out.splitlines()[:30]:
            print(f"       {line}")
        return False
    print("  OK   working tree limpio")
    return True


def upstream_name() -> str | None:
    rc, out = git_output(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    return out.strip() if rc == 0 and out.strip() else None


def check_remote_state(fetch: bool) -> bool:
    upstream = upstream_name()
    if not upstream:
        print("  WARN upstream no configurado; primer push debe usar: git push -u origin main")
        return True

    if fetch:
        rc, out = git_output(["fetch", "--prune"])
        if rc != 0:
            print("  FAIL git fetch --prune")
            print(out)
            return False

    rc, out = git_output(["rev-list", "--left-right", "--count", f"HEAD...{upstream}"])
    if rc != 0:
        print(f"  FAIL comparar con {upstream}")
        print(out)
        return False
    ahead_s, behind_s = out.split()[:2]
    ahead, behind = int(ahead_s), int(behind_s)
    if behind:
        print(f"  FAIL rama local por detras de {upstream}: ahead={ahead} behind={behind}")
        print("       Ejecuta fetch/rebase o merge antes de publicar.")
        return False
    print(f"  OK   remote sync ({upstream}, ahead={ahead}, behind={behind})")
    return True


def _auto_commit_runtime_state() -> None:
    """Commit runtime state files modified by bago commands (both doors).

    NOTE: global_state.json is now gitignored (.gitignore) — this function
    only commits other tracked runtime files (e.g. docs/COMMANDS.md auto-regen).
    """
    import subprocess as _sp
    # global_state.json is gitignored — skip it
    # Nothing else to auto-commit for now
    pass


def check_secrets() -> bool:
    """Scan tracked/staged files for known secret patterns."""
    import re
    import subprocess as _sp

    SECRET_PATTERNS = [
        # Telegram bot tokens: 123456789:AAB...
        (r"\d{8,12}:AA[A-Za-z0-9_-]{30,}", "Telegram bot token"),
        # WhatsApp Green API instance IDs (7-digit numbers in API URLs)
        (r"https?://\d{4,5}\.api\.greenapi\.com", "WhatsApp Green API URL"),
        # ngrok URLs
        (r"https://[a-z0-9-]+\.ngrok[-a-z]*\.(io|app|dev|free\.app)", "ngrok URL"),
        # Private phone numbers in international format inside JSON
        (r'["\']phone["\']\s*:\s*["\'][+]?\d{9,15}["\']', "Phone number in JSON"),
        # Email inside whatsapp_daemon structure
        (r'["\']email["\']\s*:\s*["\'][^"\'@]+@[^"\']+["\']', "Email in config"),
    ]

    # Get list of files staged for this commit / tracked files that changed
    result = _sp.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=ROOT
    )
    staged = result.stdout.strip().splitlines()

    # Also check files that are tracked and differ from HEAD
    result2 = _sp.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True, text=True, cwd=ROOT
    )
    staged += result2.stdout.strip().splitlines()
    staged = list(set(staged))  # deduplicate

    found_secrets: list[tuple[str, str, str]] = []
    for rel_path in staged:
        abs_path = ROOT / rel_path
        if not abs_path.exists() or abs_path.stat().st_size > 1_000_000:
            continue
        try:
            text = abs_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pattern, label in SECRET_PATTERNS:
            if re.search(pattern, text):
                found_secrets.append((rel_path, label, pattern))

    if found_secrets:
        print("  FAIL secrets detectados en archivos rastreados:")
        for path, label, _ in found_secrets:
            print(f"       ❌ {path} → {label}")
        print("       💡 Verifica: bago setup --clean-history")
        return False

    print("  OK   secret scan — sin secretos detectados")
    return True


def check_orphans() -> bool:
    """Check for new orphan modules (not in baseline)."""
    orphan_tool = ROOT / ".bago" / "tools" / "orphan_detector.py"
    if not orphan_tool.exists():
        print("  SKIP orphan check (orphan_detector.py no encontrado)")
        return True
    rc, out = run([sys.executable, str(orphan_tool), "--strict"], timeout=30)
    if rc == 0:
        print(f"  OK   orphan check — {out.strip()}")
        return True
    print("  FAIL orphan check — nuevos módulos sin registrar:")
    for line in out.splitlines()[:10]:
        print(f"       {line}")
    print("       💡 Ejecuta: bago orphans --baseline  o  bago orphans --fix")
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gate pre-push BAGO")
    parser.add_argument("--remote", action="store_true", help="Ejecuta git fetch --prune antes de comparar upstream.")
    parser.add_argument("--test", action="store_true", help="Self-test ligero.")
    args = parser.parse_args(argv)

    if args.test:
        assert ROOT.exists()
        assert (ROOT / "bago").exists()
        print("  1/1 tests pasaron")
        return 0

    print("BAGO pre-push guard")
    print("=" * 44)

    # ── Auto-sync README antes del clean-tree check ─────────────────────────
    try:
        import importlib.util as _ilu, sys as _sys
        _rs_path = ROOT / ".bago" / "tools" / "readme_sync.py"
        if _rs_path.exists():
            _spec = _ilu.spec_from_file_location("readme_sync", str(_rs_path))
            _rs   = _ilu.module_from_spec(_spec)
            if str(_rs_path.parent) not in _sys.path:
                _sys.path.insert(0, str(_rs_path.parent))
            _spec.loader.exec_module(_rs)
            _rs.sync(auto_stage=True, verbose=True)
    except Exception as _e:
        print(f"  WARN readme_sync: {_e}")

    # ── Auto-stage global_state.json si fue modificado por runs anteriores ───
    # global_state.json es ahora gitignored — solo notificamos
    _auto_commit_runtime_state()

    checks = [
        check_secrets(),
        check_orphans(),
        check_clean_tree(),
        check_remote_state(fetch=args.remote),
        check("bago validate", [sys.executable, "bago", "validate"], timeout=120),
        check("bago health", [sys.executable, "bago", "health"], timeout=120),
        check("bago sincerity --strict", [sys.executable, "bago", "sincerity", "--strict"], timeout=120),
        check("bago stability", [sys.executable, "bago", "stability"], timeout=120),
        check("tool_guardian --test", [sys.executable, ".bago/tools/tool_guardian.py", "--test"], timeout=120),
        check("integration_tests", [sys.executable, ".bago/tools/integration_tests.py"], timeout=240),
    ]

    if all(checks):
        print("\nDECISION: GO - push permitido.")
        return 0
    print("\nDECISION: KO - push bloqueado.")
    return 1


if __name__ == "__main__":
    _code = main()
    try:
        import importlib.util as _ilu
        _ep = __import__("pathlib").Path(__file__).parent / "bago_sac_engine.py"
        _spec = _ilu.spec_from_file_location("bago_sac_engine", str(_ep))
        _mod = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_mod)
        _mod.sac_suggest("bago pre-push", exit_code=_code)
    except Exception:
        pass
    raise SystemExit(_code)
