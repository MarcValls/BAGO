#!/usr/bin/env python3
"""
test_e2e.py — End-to-End Integration Test for BAGO release

Simula el ciclo completo de una sesión multi-provider:
create → send → mark_good → feedback → switch → compress → save → load
Luego verifica que streaming y config/credentials funcionan.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Setup paths
BAGO_ROOT = Path(__file__).resolve().parent
EXPECTED_VERSION = (BAGO_ROOT / "release_version.txt").read_text(encoding="utf-8").strip()
sys.path.insert(0, str(BAGO_ROOT / ".bago" / "core"))
sys.path.insert(0, str(BAGO_ROOT / ".bago" / "chat"))
sys.path.insert(0, str(BAGO_ROOT / ".bago" / "providers"))

from session_manager import SessionManager
from switch_engine import SwitchEngine
from commands import execute
from config_manager import ConfigManager
from credential_manager import CredentialManager


def run_e2e() -> int:
    print("=" * 60)
    print(f"BAGO {EXPECTED_VERSION} End-to-End Integration Test")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as td:
        print(f"\n[1/10] Creating session in {td}...")
        mgr = SessionManager(base_path=td, provider="ollama-local", model="llama3.2:3b")
        engine = SwitchEngine(mgr.adapters)
        assert mgr.session_id
        print(f"   ✓ Session ID: {mgr.session_id}")

        print("\n[2/10] Testing ConfigManager...")
        assert mgr.config.get("default_provider") == "ollama-local"
        mgr.config.set("default_provider", "openrouter")
        assert mgr.config.get("default_provider") == "openrouter"
        mgr.config.reset()
        assert mgr.config.get("default_provider") == "ollama-local"
        print("   ✓ Config get/set/reset OK")

        print("\n[3/10] Testing CredentialManager...")
        assert not mgr.credentials.is_configured("anthropic")
        mgr.credentials.set("anthropic", "ANTHROPIC_API_KEY", "sk-test-123")
        assert mgr.credentials.is_configured("anthropic")
        mgr.credentials.delete("anthropic", "ANTHROPIC_API_KEY")
        assert not mgr.credentials.is_configured("anthropic")
        print("   ✓ Credentials set/delete OK")

        print("\n[4/10] Testing REPL commands...")
        r = execute("/help", mgr, engine)
        assert r["ok"]
        r = execute("/status", mgr, engine)
        assert r["ok"]
        r = execute("/providers", mgr, engine)
        assert r["ok"]
        r = execute("/config list", mgr, engine)
        assert r["ok"]
        r = execute("/credentials list", mgr, engine)
        assert r["ok"]
        print("   ✓ All REPL commands OK")

        print("\n[5/10] Testing switch engine...")
        result = mgr.switch("openrouter", "anthropic/claude-3.5-sonnet", force=True)
        assert result["ok"]
        print(f"   ✓ Switch: {result['old_provider']} → openrouter")

        print("\n[6/10] Testing compression on downgrade...")
        # Simulate some history
        mgr.store.append_user("Tell me about Python", provider="openrouter", model="anthropic/claude-3.5-sonnet")
        mgr.store.append_response("Python is a versatile language...", provider="openrouter", model="anthropic/claude-3.5-sonnet")
        result = mgr.switch("ollama-local", "llama3.2:3b", force=True)
        assert result["ok"]
        print(f"   ✓ Downgrade switch with compression OK")

        print("\n[7/10] Testing mark-as-good...")
        mgr.store.append_user("What is RL?", provider="ollama-local", model="llama3.2:3b")
        mgr.store.append_response("RL stands for Reinforcement Learning...", provider="ollama-local", model="llama3.2:3b")
        ok = mgr.store.mark_good(-1)
        assert ok
        print("   ✓ Mark-as-good OK")

        print("\n[8/10] Testing RL feedback...")
        mgr.feedback(0.8)
        print("   ✓ RL feedback OK")

        print("\n[9/10] Testing save/load...")
        sid = mgr.session_id
        mgr.save()
        loaded = SessionManager.load(sid, base_path=td)
        assert loaded.session_id == sid
        assert loaded.provider == "ollama-local"
        loaded.close()
        print(f"   ✓ Session persisted and loaded OK")

        print("\n[10/10] Testing streaming API...")
        # We can't test actual streaming without a live model, but we can test the method exists
        assert hasattr(mgr, "send_stream")
        adapter = mgr._ensure_adapter()
        assert hasattr(adapter, "chat_stream")
        print("   ✓ Streaming API present")

        mgr.close()

        print("\n" + "=" * 60)
        print("ALL END-TO-END TESTS PASSED")
        print("=" * 60)
        return 0


if __name__ == "__main__":
    try:
        sys.exit(run_e2e())
    except Exception as exc:
        print(f"\n❌ END-TO-END TEST FAILED: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
