"""Tests para spiral_agent.py — BagoAgent Sprint 2."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".bago" / "tools"))

from harmony_gate import HarmonyGate, SpiralState
from spiral_agent import (
    AgentResult,
    BagoAgent,
    _AGENTS_STATE_DIR,
    agent_from_registry,
    list_agents,
    load_agents_registry,
    main,
)
from skill_engine import SkillResult


# ─────────────────────────────────────────────────────────────
# ── Fixtures ─────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

def _make_skill_result(skill_id: str, validate: str = "GO", radius: float = 0.2) -> SkillResult:
    return SkillResult(
        skill_id=skill_id,
        radius_gained=radius,
        validate=validate,
        fingerprint=[f"skill:{skill_id}", f"validate:{validate}"],
        state_vector={"phase": 0, "cycles": 1},
    )


# ─────────────────────────────────────────────────────────────
# ── AgentResult contract ─────────────────────────────────────
# ─────────────────────────────────────────────────────────────

class TestAgentResult:
    def test_fields_present(self):
        r = AgentResult(agent_id="a1")
        assert hasattr(r, "agent_id")
        assert hasattr(r, "phase")
        assert hasattr(r, "cycles_run")
        assert hasattr(r, "radius_gained")
        assert hasattr(r, "validate")
        assert hasattr(r, "fingerprint")
        assert hasattr(r, "skill_results")
        assert hasattr(r, "state_vector")
        assert hasattr(r, "harmony_scores")
        assert hasattr(r, "timestamp")

    def test_validate_values(self):
        for v in ("GO", "WARN", "FAIL"):
            r = AgentResult(agent_id="x", validate=v)
            assert r.validate == v

    def test_phase_normalized(self):
        r = AgentResult(agent_id="x", phase=14)
        assert r.phase == 14 % 12

    def test_to_dict_shape(self):
        sr = _make_skill_result("code_review")
        r = AgentResult(
            agent_id="a1", phase=4, validate="GO",
            fingerprint=["agent:a1"], skill_results=[sr],
            state_vector={"phase": 4}, harmony_scores={"a↔b": 0.8},
        )
        d = r.to_dict()
        assert d["agent_id"] == "a1"
        assert d["validate"] == "GO"
        assert len(d["skill_results"]) == 1
        assert d["skill_results"][0]["skill_id"] == "code_review"

    def test_repr(self):
        r = AgentResult(agent_id="test_agent", validate="WARN")
        s = repr(r)
        assert "test_agent" in s
        assert "WARN" in s


# ─────────────────────────────────────────────────────────────
# ── BagoAgent construction ───────────────────────────────────
# ─────────────────────────────────────────────────────────────

class TestBagoAgentConstruction:
    def test_basic_creation(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "spiral_agent._AGENTS_STATE_DIR", tmp_path / "agents"
        )
        agent = BagoAgent("test_agent", phase=4, skills=["code_review"])
        assert agent.agent_id == "test_agent"
        assert agent.phase == 4
        assert agent.skill_ids == ["code_review"]

    def test_phase_normalized(self, tmp_path, monkeypatch):
        monkeypatch.setattr("spiral_agent._AGENTS_STATE_DIR", tmp_path / "agents")
        agent = BagoAgent("a", phase=13)
        assert agent.phase == 1  # 13 % 12

    def test_state_dir_created(self, tmp_path, monkeypatch):
        state_root = tmp_path / "agents"
        monkeypatch.setattr("spiral_agent._AGENTS_STATE_DIR", state_root)
        BagoAgent("my_agent", phase=0)
        assert (state_root / "my_agent").exists()

    def test_default_skills_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("spiral_agent._AGENTS_STATE_DIR", tmp_path / "agents")
        agent = BagoAgent("empty_agent")
        assert agent.skill_ids == []


# ─────────────────────────────────────────────────────────────
# ── BagoAgent.run — ciclo completo ───────────────────────────
# ─────────────────────────────────────────────────────────────

class TestBagoAgentRun:
    def _make_agent(self, tmp_path, monkeypatch, agent_id="runner", phase=0, skills=None):
        monkeypatch.setattr("spiral_agent._AGENTS_STATE_DIR", tmp_path / "agents")
        return BagoAgent(agent_id, phase=phase, skills=skills or [])

    def test_run_returns_agent_result(self, tmp_path, monkeypatch):
        agent = self._make_agent(tmp_path, monkeypatch)
        with patch("spiral_agent.run_skill") as mock_run:
            mock_run.return_value = _make_skill_result("s1")
            result = agent.run()
        assert isinstance(result, AgentResult)

    def test_run_with_no_skills(self, tmp_path, monkeypatch):
        agent = self._make_agent(tmp_path, monkeypatch)
        result = agent.run()
        assert isinstance(result, AgentResult)
        assert result.validate == "WARN"   # sin skills → WARN
        assert result.skill_results == []

    def test_run_all_go_yields_go(self, tmp_path, monkeypatch):
        agent = self._make_agent(tmp_path, monkeypatch, skills=["code_review", "doc_writer"])
        with patch("spiral_agent.run_skill") as mock_run:
            mock_run.return_value = _make_skill_result("s1", validate="GO")
            result = agent.run()
        assert result.validate == "GO"

    def test_run_mixed_yields_warn(self, tmp_path, monkeypatch):
        agent = self._make_agent(tmp_path, monkeypatch, skills=["s1", "s2"])
        results = [_make_skill_result("s1", "GO"), _make_skill_result("s2", "FAIL")]
        with patch("spiral_agent.run_skill") as mock_run, \
             patch("spiral_agent._load_skill_registry") as mock_reg:
            mock_reg.return_value = {"s1": {}, "s2": {}}
            mock_run.side_effect = results
            result = agent.run()
        assert result.validate == "WARN"

    def test_run_all_fail_yields_fail(self, tmp_path, monkeypatch):
        agent = self._make_agent(tmp_path, monkeypatch, skills=["s1"])
        with patch("spiral_agent.run_skill") as mock_run, \
             patch("spiral_agent._load_skill_registry") as mock_reg:
            mock_reg.return_value = {"s1": {}}
            mock_run.return_value = _make_skill_result("s1", validate="FAIL")
            result = agent.run()
        assert result.validate == "FAIL"

    def test_run_increments_cycles(self, tmp_path, monkeypatch):
        agent = self._make_agent(tmp_path, monkeypatch, skills=["code_review"])
        with patch("spiral_agent.run_skill") as mock_run:
            mock_run.return_value = _make_skill_result("code_review")
            agent.run()
            agent.run()
        assert agent._cycles == 2

    def test_run_accumulates_radius(self, tmp_path, monkeypatch):
        agent = self._make_agent(tmp_path, monkeypatch, skills=["code_review"])
        with patch("spiral_agent.run_skill") as mock_run:
            mock_run.return_value = _make_skill_result("code_review", radius=0.5)
            agent.run()
            agent.run()
        assert abs(agent._total_radius - 1.0) < 1e-9

    def test_run_creates_state_file(self, tmp_path, monkeypatch):
        state_root = tmp_path / "agents"
        monkeypatch.setattr("spiral_agent._AGENTS_STATE_DIR", state_root)
        agent = BagoAgent("persist_test", phase=0)
        agent.run()
        assert (state_root / "persist_test" / "state.json").exists()

    def test_run_creates_gradient_file(self, tmp_path, monkeypatch):
        state_root = tmp_path / "agents"
        monkeypatch.setattr("spiral_agent._AGENTS_STATE_DIR", state_root)
        agent = BagoAgent("grad_test", phase=0)
        agent.run()
        assert (state_root / "grad_test" / "gradient.json").exists()

    def test_run_creates_episodic_file(self, tmp_path, monkeypatch):
        state_root = tmp_path / "agents"
        monkeypatch.setattr("spiral_agent._AGENTS_STATE_DIR", state_root)
        agent = BagoAgent("ep_test", phase=0)
        agent.run()
        assert (state_root / "ep_test" / "episodic.json").exists()

    def test_run_fingerprint_contains_agent_id(self, tmp_path, monkeypatch):
        agent = self._make_agent(tmp_path, monkeypatch, agent_id="fp_agent")
        result = agent.run()
        assert any("agent:fp_agent" in tag for tag in result.fingerprint)

    def test_parent_ctx_accepted(self, tmp_path, monkeypatch):
        agent = self._make_agent(tmp_path, monkeypatch)
        parent = {"state_vector": {"phase": 0}, "fingerprint": ["parent:tag"]}
        result = agent.run(parent_ctx=parent)
        assert isinstance(result, AgentResult)

    def test_state_vector_has_expected_keys(self, tmp_path, monkeypatch):
        agent = self._make_agent(tmp_path, monkeypatch)
        result = agent.run()
        sv = result.state_vector
        for key in ("phase", "cycles", "total_radius", "skills_active", "validate"):
            assert key in sv, f"Missing key: {key}"


# ─────────────────────────────────────────────────────────────
# ── BagoAgent.spiral_state ────────────────────────────────────
# ─────────────────────────────────────────────────────────────

class TestSpiralState:
    def test_spiral_state_returns_spiral_state(self, tmp_path, monkeypatch):
        monkeypatch.setattr("spiral_agent._AGENTS_STATE_DIR", tmp_path / "agents")
        agent = BagoAgent("ss_agent", phase=4)
        ss = agent.spiral_state
        assert isinstance(ss, SpiralState)
        assert ss.entity_id == "ss_agent"
        assert ss.phase == 4


# ─────────────────────────────────────────────────────────────
# ── Registry helpers ─────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

class TestRegistry:
    def test_load_agents_registry_returns_dict(self):
        reg = load_agents_registry()
        assert isinstance(reg, dict)

    def test_known_agents_present(self):
        reg = load_agents_registry()
        assert "agent_tools" in reg
        assert "agent_tests" in reg

    def test_agent_from_registry_returns_bago_agent(self):
        agent = agent_from_registry("agent_tools")
        assert agent is not None
        assert isinstance(agent, BagoAgent)
        assert agent.agent_id == "agent_tools"

    def test_agent_from_registry_unknown_returns_none(self):
        assert agent_from_registry("nonexistent_xyz") is None

    def test_list_agents_returns_list(self):
        agents = list_agents()
        assert isinstance(agents, list)
        assert len(agents) >= 4

    def test_list_agents_has_required_fields(self):
        agents = list_agents()
        for a in agents:
            for field in ("id", "phase", "skills", "active", "cycles", "total_radius"):
                assert field in a, f"Missing field {field} in agent {a.get('id')}"


# ─────────────────────────────────────────────────────────────
# ── HarmonyGate integration ───────────────────────────────────
# ─────────────────────────────────────────────────────────────

class TestHarmonyGateIntegration:
    def test_agents_harmony_uses_phase_consonance(self):
        gate = HarmonyGate()
        # Fases 0 y 4 = tercera mayor = consonante
        a = SpiralState("tools", phase=0, validate="GO", fingerprint=["validate:GO"], radius_gained=0.3)
        b = SpiralState("tests", phase=4, validate="GO", fingerprint=["validate:GO"], radius_gained=0.2)
        score = gate.score(a, b)
        assert score > 0.6, f"Tercera mayor debería ser consonante, score={score}"

    def test_tritone_agents_dissonant(self):
        gate = HarmonyGate()
        a = SpiralState("a", phase=0, validate="GO", fingerprint=["validate:GO"], radius_gained=0.3)
        b = SpiralState("b", phase=6, validate="GO", fingerprint=["validate:GO"], radius_gained=0.2)
        score = gate.score(a, b)
        # Tritono reduce el score de fase a 0 → total más bajo
        assert score <= 0.7, f"Tritono debería reducir score, score={score}"


# ─────────────────────────────────────────────────────────────
# ── CLI dispatch ─────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

class TestCLI:
    def test_help(self, capsys):
        rc = main(["--help"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "spawn" in out

    def test_list(self, capsys):
        rc = main(["list"])
        assert rc == 0

    def test_status(self, capsys):
        rc = main(["status"])
        assert rc == 0

    def test_unknown_subcmd(self, capsys):
        rc = main(["badcmd"])
        assert rc == 1

    def test_run_unknown_agent(self, capsys):
        rc = main(["run", "nonexistent_agent_xyz"])
        assert rc == 1
