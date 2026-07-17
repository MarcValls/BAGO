"""Smoke tests for the FASE 12 translator layer.

Cubre R10 (cobertura de tests para node_control_translator.py).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ["python", "-m", "bago_core.launcher"]

def _run_node(*args: str) -> tuple[int, str, str]:
    result = subprocess.run(
        [*LAUNCHER, "node", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr

def test_translator_list_human() -> None:
    rc, out, _ = _run_node("translator", "list")
    assert rc == 0, "translator list failed"
    assert "BAGO TRANSLATOR PIECES" in out
    assert "translator.openai.gpt-4o" in out
    assert "translator.anthropic.claude-3-5-sonnet" in out

def test_translator_list_json() -> None:
    rc, out, _ = _run_node("translator", "list", "--json")
    assert rc == 0
    payload = json.loads(out)
    assert payload["count"] >= 4
    families = {t["model_family"] for t in payload["translators"]}
    assert {"openai", "anthropic", "ollama"}.issubset(families)

def test_translator_show_human() -> None:
    rc, out, _ = _run_node("translator", "show", "translator.openai.gpt-4o")
    assert rc == 0
    assert "translator.openai.gpt-4o" in out
    assert "supports." in out

def test_translator_show_json() -> None:
    rc, out, _ = _run_node("translator", "show", "translator.anthropic.claude-3-5-sonnet", "--json")
    assert rc == 0
    payload = json.loads(out)
    assert payload["piece_id"] == "translator.anthropic.claude-3-5-sonnet"
    assert payload["model_family"] == "anthropic"

def test_translator_show_missing() -> None:
    rc, _, err = _run_node("translator", "show", "translator.does.not.exist")
    assert rc == 2
    assert "no encontrada" in err

def test_translator_validate_all() -> None:
    rc, out, _ = _run_node("translator", "validate")
    assert rc == 0, f"validate failed: {out}"
    for line in out.splitlines():
        if "[" in line and "]" in line:
            assert "OK" in line or "FAIL" in line

def test_translator_validate_json() -> None:
    rc, out, _ = _run_node("translator", "validate", "--json")
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert all(r["ok"] for r in payload["results"])

def test_translator_validate_piece() -> None:
    rc, out, _ = _run_node("translator", "validate", "translator.ollama.llama3.2")
    assert rc == 0
    assert "translator.ollama.llama3.2" in out

def test_translator_map_human() -> None:
    rc, out, _ = _run_node("translator", "map", "translator.openai.gpt-4o")
    assert rc == 0
    assert "REQUEST (preview)" in out

def test_translator_map_json() -> None:
    rc, out, _ = _run_node("translator", "map", "translator.openai.gpt-4o", "--json")
    assert rc == 0
    payload = json.loads(out)
    # OpenAI Chat Completions format
    assert "model" in payload
    assert "messages" in payload
    assert isinstance(payload["messages"], list)

def test_guard_under_threshold() -> None:
    """R3/R5/R8 guard no debe tener ERROR."""
    result = subprocess.run(
        ["python", "tools/check_modular.py"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "0 errores" in result.stdout or "0 errors" in result.stdout, result.stdout

if __name__ == "__main__":
    # Simple runner (no pytest dependency)
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print("  OK   %s" % t.__name__)
            passed += 1
        except AssertionError as e:
            print("  FAIL %s: %s" % (t.__name__, e))
            failed += 1
        except Exception as e:  # noqa: BLE001
            print("  ERR  %s: %s" % (t.__name__, e))
            failed += 1
    print()
    print("translator tests: %d passed, %d failed" % (passed, failed))
    sys.exit(0 if failed == 0 else 1)
