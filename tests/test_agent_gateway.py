"""
test_agent_gateway.py — Unit tests for the BAGO Multi-Agent Gateway

Tests:
- AgentRequest allowlist enforcement
- Risk policy (dangerous without unsafe/dry_run is blocked)
- LocalAdapter health + dispatch (health_check, list_tools)
- MCPAdapter readonly restriction
- AgentGateway dispatch routing
- JSON output of AgentResult.to_dict()
- Unknown adapter falls back to local
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── import gateway ──────────────────────────────────────────────────────────
_GW_PATH = Path(__file__).resolve().parent.parent / ".bago" / "agents" / "agent_gateway.py"
assert _GW_PATH.exists(), f"agent_gateway.py not found at {_GW_PATH}"

spec = importlib.util.spec_from_file_location("agent_gateway", str(_GW_PATH))
gw_mod = importlib.util.module_from_spec(spec)
sys.modules["agent_gateway"] = gw_mod  # required for dataclass __module__ lookup
spec.loader.exec_module(gw_mod)

AgentGateway   = gw_mod.AgentGateway
AgentRequest   = gw_mod.AgentRequest
AgentResult    = gw_mod.AgentResult
LocalAdapter   = gw_mod.LocalAdapter
MCPAdapter     = gw_mod.MCPAdapter
OllamaAdapter  = gw_mod.OllamaAdapter
AdapterRegistry = gw_mod.AdapterRegistry
ALL_ALLOWED_INTENTS  = gw_mod.ALL_ALLOWED_INTENTS
DANGEROUS_INTENTS    = gw_mod.DANGEROUS_INTENTS
READONLY_INTENTS     = gw_mod.READONLY_INTENTS


# ── Helpers ────────────────────────────────────────────────────────────────

def _gw() -> AgentGateway:
    return AgentGateway()


def _req(intent: str, adapter: str = "local", **opts) -> AgentRequest:
    return AgentRequest(intent=intent, source={"adapter": adapter}, options=opts)


# ── Tests: AgentRequest ─────────────────────────────────────────────────────

class TestAgentRequest:
    def test_default_adapter_is_local(self):
        r = AgentRequest(intent="health_check")
        assert r.adapter_name == "local"

    def test_dry_run_false_by_default(self):
        r = AgentRequest(intent="health_check")
        assert r.dry_run is False

    def test_unsafe_false_by_default(self):
        r = AgentRequest(intent="health_check")
        assert r.unsafe is False

    def test_timeout_default_30(self):
        r = AgentRequest(intent="health_check")
        assert r.timeout == 30

    def test_custom_options(self):
        r = _req("autonomous_cycle", dry_run=True, unsafe=True, timeout=60)
        assert r.dry_run is True
        assert r.unsafe is True
        assert r.timeout == 60


# ── Tests: Allowlist ────────────────────────────────────────────────────────

class TestAllowlist:
    def test_known_readonly_intents_allowed(self):
        gw = _gw()
        for intent in list(READONLY_INTENTS)[:3]:
            req = _req(intent)
            # Just check it doesn't return intent_not_allowed
            result = gw.dispatch(req)
            assert "intent_not_allowed" not in result.error, f"Intent '{intent}' was blocked"

    def test_unknown_intent_blocked(self):
        gw = _gw()
        result = gw.dispatch(_req("rm_rf_everything"))
        assert result.success is False
        assert "allowlist" in result.error.lower() or "not allowed" in result.error.lower() or "intent" in result.error.lower()

    def test_all_allowed_intents_not_empty(self):
        assert len(ALL_ALLOWED_INTENTS) >= 10


# ── Tests: Risk policy ──────────────────────────────────────────────────────

class TestRiskPolicy:
    def test_dangerous_intent_without_unsafe_blocked(self):
        gw = _gw()
        result = gw.dispatch(_req("autonomous_cycle"))
        assert result.success is False
        assert "dangerous" in result.error.lower() or "unsafe" in result.error.lower() or "dry_run" in result.error.lower()

    def test_dangerous_intent_with_dry_run_allowed(self):
        gw = _gw()
        with patch.object(gw_mod, "_run_bago", return_value=(0, "[DRY RUN OK]")):
            result = gw.dispatch(_req("autonomous_cycle", dry_run=True))
        assert result.success is True

    def test_dangerous_intent_with_unsafe_flag_allowed(self):
        gw = _gw()
        with patch.object(gw_mod, "_run_bago", return_value=(0, "[OK]")):
            result = gw.dispatch(_req("autonomous_cycle", unsafe=True))
        assert result.success is True


# ── Tests: LocalAdapter ─────────────────────────────────────────────────────

class TestLocalAdapter:
    def test_health_returns_bool(self):
        adapter = LocalAdapter()
        assert isinstance(adapter.health(), bool)

    def test_capability_has_correct_name(self):
        cap = LocalAdapter().capability()
        assert cap.name == "local"

    def test_capability_supports_all_intents(self):
        cap = LocalAdapter().capability()
        for intent in ALL_ALLOWED_INTENTS:
            assert intent in cap.supported_intents

    def test_execute_health_check(self):
        adapter = LocalAdapter()
        with patch.object(gw_mod, "_run_bago", return_value=(0, "Health: 100")):
            result = adapter.execute(AgentRequest(intent="health_check"))
        assert result.success is True
        assert "Health" in result.output

    def test_execute_unknown_intent_returns_error(self):
        adapter = LocalAdapter()
        result = adapter.execute(AgentRequest(intent="not_a_real_intent"))
        assert result.success is False
        assert "command mapped" in result.error.lower() or "no command" in result.error.lower()

    def test_dangerous_without_unsafe_adds_dry_run(self):
        """Dangerous intents without unsafe=True get --dry-run injected automatically."""
        adapter = LocalAdapter()
        calls = []
        def _fake_run(*args, **kwargs):
            calls.append(args)
            return (0, "dry ok")
        with patch.object(gw_mod, "_run_bago", side_effect=_fake_run):
            req = AgentRequest(intent="autonomous_cycle", options={"unsafe": False})
            adapter.execute(req)
        # --dry-run should be in the args
        assert calls, "No call was made"
        flat_args = [str(a) for a in calls[0]]
        assert "--dry-run" in flat_args

    def test_exit_code_nonzero_is_failure(self):
        adapter = LocalAdapter()
        with patch.object(gw_mod, "_run_bago", return_value=(1, "Error output")):
            result = adapter.execute(AgentRequest(intent="health_check"))
        assert result.success is False
        assert result.exit_code == 1


# ── Tests: MCPAdapter ───────────────────────────────────────────────────────

class TestMCPAdapter:
    def test_blocks_mutating_intents(self):
        adapter = MCPAdapter()
        result = adapter.execute(AgentRequest(intent="task_create"))
        assert result.success is False
        assert "readonly" in result.error.lower() or "mcp" in result.error.lower()

    def test_allows_readonly_intents(self):
        adapter = MCPAdapter()
        with patch.object(gw_mod, "_run_bago", return_value=(0, "ok")):
            result = adapter.execute(AgentRequest(intent="health_check"))
        assert result.success is True

    def test_capability_supports_only_readonly(self):
        cap = MCPAdapter().capability()
        for intent in cap.supported_intents:
            assert intent in READONLY_INTENTS


# ── Tests: AgentGateway ────────────────────────────────────────────────────

class TestAgentGateway:
    def test_dispatch_routes_to_local_by_default(self):
        gw = _gw()
        with patch.object(gw_mod, "_run_bago", return_value=(0, "routed")):
            result = gw.dispatch(AgentRequest(intent="health_check"))
        assert result.adapter == "local"

    def test_unknown_adapter_falls_back_to_local(self):
        gw = _gw()
        req = AgentRequest(intent="health_check", source={"adapter": "nonexistent_adapter_xyz"})
        with patch.object(gw_mod, "_run_bago", return_value=(0, "fallback ok")):
            result = gw.dispatch(req)
        assert result.success is True
        assert result.adapter == "local"

    def test_result_has_timestamp(self):
        gw = _gw()
        with patch.object(gw_mod, "_run_bago", return_value=(0, "ts")):
            result = gw.dispatch(AgentRequest(intent="health_check"))
        assert result.timestamp  # not empty

    def test_result_has_neural_event_id(self):
        gw = _gw()
        with patch.object(gw_mod, "_run_bago", return_value=(0, "evt")):
            result = gw.dispatch(AgentRequest(intent="health_check"))
        assert result.neural_event_id.startswith("evt-")

    def test_status_returns_all_adapters(self):
        gw = _gw()
        st = gw.status()
        assert "adapters" in st
        assert "local" in st["adapters"]
        assert "ollama" in st["adapters"]
        assert "mcp" in st["adapters"]

    def test_to_dict_is_json_serializable(self):
        gw = _gw()
        with patch.object(gw_mod, "_run_bago", return_value=(0, "json ok")):
            result = gw.dispatch(AgentRequest(intent="health_check"))
        d = result.to_dict()
        s = json.dumps(d)  # must not raise
        assert isinstance(s, str)

    def test_rate_limit_is_enforced(self):
        """After 10 calls in under 1s, 11th should be rate-limited."""
        gw = _gw()
        gw._rate_limit = 3  # lower for test speed
        with patch.object(gw_mod, "_run_bago", return_value=(0, "ok")):
            for _ in range(3):
                gw.dispatch(AgentRequest(intent="health_check"))
            result = gw.dispatch(AgentRequest(intent="health_check"))
        assert result.success is False
        assert "rate limit" in result.error.lower()


# ── Tests: AdapterRegistry ─────────────────────────────────────────────────

class TestAdapterRegistry:
    def test_default_adapters_registered(self):
        all_adapters = AdapterRegistry.all()
        assert "local" in all_adapters
        assert "ollama" in all_adapters
        assert "mcp" in all_adapters
        assert "codex" in all_adapters
        assert "cloud" in all_adapters

    def test_local_is_always_available(self):
        assert AdapterRegistry.get("local").health() is True  # bago script must exist
