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
    # bago validate/health/sincerity actualizan knowledge_index.promoted_count,
    # lo que deja global_state.json sucio tras cada ejecución del guard.
    # Lo auto-stageamos y commiteamos aquí para que clean_tree pase.
    _gs_path = ROOT / ".bago" / "state" / "global_state.json"
    try:
        import subprocess as _sp
        _diff = _sp.run(
            ["git", "diff", "--name-only", str(_gs_path)],
            capture_output=True, text=True, cwd=ROOT
        )
        if _gs_path.name in _diff.stdout:
            _sp.run(["git", "add", str(_gs_path)], cwd=ROOT, check=True)
            _sp.run(
                ["git", "commit", "-m",
                 "chore(state): auto-sync global_state (pre-push guard)\n\n"
                 "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"],
                cwd=ROOT, check=True, capture_output=True
            )
            print("  OK   global_state.json auto-commiteado")
    except Exception as _e:
        print(f"  WARN global_state auto-stage: {_e}")

    checks = [
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
