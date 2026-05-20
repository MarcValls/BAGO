#!/usr/bin/env python3
"""test_v35_features.py — Tests para las 6 features P0 de v3.5"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".bago" / "core"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".bago" / "tools"))

import json
from prompt_router import SignalMetrics, PromptRouter, compute_efficiency
from role_embedded import RoleSpiralBuilder, EmbeddedRole, RoleArtifact
from token_analytics import TokenAnalytics, TokenBudget
from model_gate import ModelGate, ModelGateResult


class TestPromptRouter:
    def test_select_band_2_4g_for_drift(self):
        m = SignalMetrics(context_depth=5, token_pressure=0.9, coherence_score=0.3,
                         drift_detected=True, noise_level=0.5, task_urgency=3, last_cycle_success=False)
        assert m.band() == "2.4g"

    def test_select_band_5g_for_good_signal(self):
        m = SignalMetrics(context_depth=5, token_pressure=0.5, coherence_score=0.9,
                         drift_detected=False, noise_level=0.1, task_urgency=5, last_cycle_success=True)
        assert m.band() == "5g"

    def test_efficiency_computation(self):
        m = SignalMetrics(context_depth=5, token_pressure=0.5, coherence_score=0.9,
                         drift_detected=False, noise_level=0.1, task_urgency=5, last_cycle_success=True)
        eff = compute_efficiency("5g", m)
        assert "efficiency_score" in eff
        assert 0 <= eff["efficiency_score"] <= 100
        assert eff["recommendation"] == "OK"

    def test_efficiency_warns_on_high_decoupling(self):
        m = SignalMetrics(context_depth=5, token_pressure=0.9, coherence_score=0.3,
                         drift_detected=True, noise_level=0.5, task_urgency=3, last_cycle_success=False)
        eff = compute_efficiency("2.4g", m)
        assert eff["recommendation"] == "REDUCE_DEPTH"


class TestRoleEmbedded:
    def test_build_prompt_basic(self):
        builder = RoleSpiralBuilder()
        result = builder.build_prompt("nonexistent", 1, "test")
        assert "error" in result

    def test_save_and_load_role(self):
        builder = RoleSpiralBuilder()
        role = EmbeddedRole(
            role_id="test_role",
            name="Test Role",
            description="A test role",
            system_prompt="You are a test role.",
            artifacts=[RoleArtifact("art1", "text", "Some content", "local")],
            spiral_index={"init": ["art1"], "build": ["art1"]},
            preferred_band="5g",
        )
        builder.save_role(role)
        assert "test_role" in builder.roles

    def test_prompt_grows_with_cycle(self):
        builder = RoleSpiralBuilder()
        role = EmbeddedRole(
            role_id="grow_role",
            name="Grow Role",
            description="Grows with cycles",
            system_prompt="Base prompt.",
            artifacts=[
                RoleArtifact("a1", "text", "Content 1", "local"),
                RoleArtifact("a2", "text", "Content 2", "local"),
            ],
            spiral_index={"init": ["a1"], "build": ["a1", "a2"]},
        )
        builder.save_role(role)
        r1 = builder.build_prompt("grow_role", 1)
        r2 = builder.build_prompt("grow_role", 2)
        assert len(r1["prompt"]) < len(r2["prompt"])
        assert r1["phase"] == "init"
        assert r2["phase"] == "build"


class TestTokenAnalytics:
    def test_token_budget_class(self):
        b = TokenBudget("test", 100.0, 0.0025, 0.010)
        b.used_in_1k = 10.0
        b.used_out_1k = 5.0
        # cost = 10*0.0025 + 5*0.010 = 0.025 + 0.05 = 0.075
        # pct = 0.075/100 * 100 = 0.075 → 0.08 rounded
        assert b.pct_used() == 0.08
        assert b.remaining_usd() == 99.925

    def test_analytics_init(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ta = TokenAnalytics(bago_root=tmp)
            assert ta.root == Path(tmp).resolve()

    def test_analytics_reports_empty(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ta = TokenAnalytics(bago_root=tmp)
            summary = ta.summary()
            assert "providers" in summary or "records" in summary


class TestModelGate:
    def test_direct_when_model_available(self):
        gate = ModelGate()
        providers = {"ollama": {"ok": True, "models": ["qwen2.5:7b"]}}
        result = gate.check("ollama", "qwen2.5:7b", providers)
        assert result.success
        assert result.gate_action == "direct"

    def test_fallback_when_model_missing(self):
        gate = ModelGate()
        providers = {
            "ollama": {"ok": True, "models": ["qwen2.5:7b"]},
            "copilot": {"ok": True, "models": ["gpt-4o-mini"]},
        }
        result = gate.check("ollama", "qwen2.5:14b", providers)
        assert result.success
        assert result.gate_action == "fallback"

    def test_degrade_when_no_fallback(self):
        gate = ModelGate()
        providers = {"ollama": {"ok": False}, "copilot": {"ok": False}}
        result = gate.check("ollama", "unknown", providers)
        assert not result.success
        assert result.gate_action == "degrade"

    def test_gate_chain_filters_unavailable(self):
        gate = ModelGate()
        providers = {
            "ollama": {"ok": True, "models": ["qwen2.5:7b"]},
            "copilot": {"ok": False},
        }
        chain = [("ollama", "qwen2.5:7b"), ("copilot", "gpt-4o")]
        filtered = gate.gate_chain(chain, providers)
        assert len(filtered) == 1


class TestBrainstormFix:
    def test_brainstorm_injection(self):
        import os
        repo_root = Path(os.environ.get("BAGO_ROOT", Path(__file__).resolve().parents[2]))
        orch_path = repo_root / ".bago" / "tools" / "bago" / "llm" / "orchestrator.py"
        if not orch_path.exists():
            orch_path = Path.cwd() / ".bago" / "tools" / "bago" / "llm" / "orchestrator.py"
        assert orch_path.exists(), f"orchestrator.py not found at {orch_path}"
        content = orch_path.read_text(encoding="utf-8")
        assert "MODO BRAINSTORM ACTIVO" in content
        assert "ANALISIS:" in content or "ANÁLISIS:" in content
        assert "GENERACION:" in content or "GENERACIÓN:" in content
        assert "PROHIBIDO:" in content


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])



