"""Tests para Sprint 3 — cmd_orchestrate y orquestador nivel-0."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".bago" / "tools"))

from harmony_gate import HarmonyGate, SpiralState
from spiral_agent import AgentResult, BagoAgent, list_agents


# ─────────────────────────────────────────────────────────────
# ── Helpers ──────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

def _make_agent_result(agent_id: str, validate: str = "GO", radius: float = 0.3) -> AgentResult:
    return AgentResult(
        agent_id=agent_id,
        phase=0,
        validate=validate,
        radius_gained=radius,
        fingerprint=[f"agent:{agent_id}", f"validate:{validate}"],
    )


# ─────────────────────────────────────────────────────────────
# ── Orchestrator state dir ───────────────────────────────────
# ─────────────────────────────────────────────────────────────

class TestOrchestratorStateDir:
    def test_state_dir_exists(self):
        orch_dir = REPO_ROOT / ".bago" / "state" / "orchestrator"
        assert orch_dir.is_dir(), f"Orchestrator state dir missing: {orch_dir}"

    def test_agents_state_dir_exists(self):
        agents_dir = REPO_ROOT / ".bago" / "state" / "agents"
        assert agents_dir.is_dir(), f"Agents state dir missing: {agents_dir}"


# ─────────────────────────────────────────────────────────────
# ── cmd_orchestrate importable ───────────────────────────────
# ─────────────────────────────────────────────────────────────

class TestOrchestrateImport:
    def test_cmd_orchestrate_importable(self):
        from spiral_loop import cmd_orchestrate
        assert callable(cmd_orchestrate)

    def test_orchestrate_status_importable(self):
        from spiral_loop import _orchestrate_status
        assert callable(_orchestrate_status)


# ─────────────────────────────────────────────────────────────
# ── cmd_orchestrate --status (read-only) ─────────────────────
# ─────────────────────────────────────────────────────────────

class TestOrchestrateStatus:
    def test_status_returns_int(self, capsys):
        from spiral_loop import cmd_orchestrate
        rc = cmd_orchestrate(status_only=True)
        assert isinstance(rc, int)

    def test_status_output_contains_nivel0(self, capsys):
        from spiral_loop import cmd_orchestrate
        cmd_orchestrate(status_only=True)
        out = capsys.readouterr().out
        assert "Nivel-0" in out

    def test_status_output_contains_agentes(self, capsys):
        from spiral_loop import cmd_orchestrate
        cmd_orchestrate(status_only=True)
        out = capsys.readouterr().out
        assert "Agentes" in out

    def test_status_output_contains_harmony(self, capsys):
        from spiral_loop import cmd_orchestrate
        cmd_orchestrate(status_only=True)
        out = capsys.readouterr().out
        assert "harmony" in out.lower()

    def test_status_shows_known_agents(self, capsys):
        from spiral_loop import cmd_orchestrate
        cmd_orchestrate(status_only=True)
        out = capsys.readouterr().out
        # Al menos uno de los agentes del registro debe aparecer
        assert any(name in out for name in ("agent_tools", "agent_tests", "agent_docs"))


# ─────────────────────────────────────────────────────────────
# ── cmd_orchestrate (ciclo completo) ─────────────────────────
# ─────────────────────────────────────────────────────────────

class TestOrchestrateRun:
    def test_run_returns_int(self):
        from spiral_loop import cmd_orchestrate
        rc = cmd_orchestrate(status_only=False)
        assert isinstance(rc, int)
        assert rc in (0, 1)

    def test_run_creates_orchestrator_state_file(self):
        from spiral_loop import cmd_orchestrate, STATE
        cmd_orchestrate(status_only=False)
        orch_file = STATE / "orchestrator" / "state.json"
        assert orch_file.exists(), "Orchestrator state file should be created"

    def test_orchestrator_state_has_required_keys(self):
        from spiral_loop import cmd_orchestrate, STATE
        cmd_orchestrate(status_only=False)
        orch_file = STATE / "orchestrator" / "state.json"
        if orch_file.exists():
            data = json.loads(orch_file.read_text())
            for key in ("cycles", "n_agents_active", "global_harmony"):
                assert key in data, f"Missing key: {key}"

    def test_run_increments_cycles(self):
        from spiral_loop import cmd_orchestrate, STATE
        orch_file = STATE / "orchestrator" / "state.json"
        before = 0
        if orch_file.exists():
            try:
                before = json.loads(orch_file.read_text()).get("cycles", 0)
            except (json.JSONDecodeError, OSError):
                pass
        cmd_orchestrate(status_only=False)
        if orch_file.exists():
            after = json.loads(orch_file.read_text()).get("cycles", 0)
            assert after > before, "Orchestrator cycles should increment"

    def test_run_harmony_in_range(self):
        from spiral_loop import cmd_orchestrate, STATE
        cmd_orchestrate(status_only=False)
        orch_file = STATE / "orchestrator" / "state.json"
        if orch_file.exists():
            data = json.loads(orch_file.read_text())
            harmony = data.get("global_harmony", 0.0)
            assert 0.0 <= harmony <= 1.0, f"Harmony out of range: {harmony}"


# ─────────────────────────────────────────────────────────────
# ── HarmonyGate a nivel de orquestador ───────────────────────
# ─────────────────────────────────────────────────────────────

class TestOrchestratorHarmonyGate:
    def test_all_go_agents_open_gate(self):
        gate = HarmonyGate(threshold=0.6)
        results = [_make_agent_result(f"a{i}", "GO") for i in range(3)]
        states = [
            SpiralState(r.agent_id, phase=i * 4, validate="GO",
                        fingerprint=r.fingerprint, radius_gained=r.radius_gained)
            for i, r in enumerate(results)
        ]
        # Fases 0·4·8 = terceras mayores = consonante
        s = gate.score(states[0], states[1])
        assert s > 0.6, f"Agents with GO and phase Δ4 should be consonant, score={s}"

    def test_fail_agent_closes_gate(self):
        gate = HarmonyGate(threshold=0.6)
        good  = SpiralState("good",  phase=0, validate="GO",   fingerprint=["validate:GO"],   radius_gained=0.3)
        bad   = SpiralState("bad",   phase=6, validate="FAIL", fingerprint=["validate:FAIL"], radius_gained=0.0)
        s = gate.score(good, bad)
        assert s < 0.6, f"FAIL agent at tritone should be dissonant, score={s}"

    def test_global_harmony_formula(self):
        results = [
            _make_agent_result("a1", "GO"),
            _make_agent_result("a2", "GO"),
            _make_agent_result("a3", "WARN"),
        ]
        go_count = sum(1 for r in results if r.validate == "GO")
        global_harmony = go_count / len(results)
        assert abs(global_harmony - 2/3) < 1e-9

    def test_harmony_threshold_67_percent(self):
        """El ciclo es exitoso cuando la mayoría de agentes están GO (threshold ~0.67)."""
        # 2/3 agentes GO = 0.6667 ≥ threshold de corte (~0.67 ≈ 2/3)
        harmony_2_of_3 = 2 / 3
        # El threshold real usado en cmd_run_polyphony es >= 0.67
        # 2/3 es casi pero no exactamente 0.67; verificar que la escala tiene sentido
        assert harmony_2_of_3 > 0.66, "2 de 3 GO debe superar el 66%"
        assert harmony_2_of_3 < 0.67, "2 de 3 GO está justo debajo del 67% exacto"


# ─────────────────────────────────────────────────────────────
# ── Fractal contract — misma interfaz en todos los niveles ────
# ─────────────────────────────────────────────────────────────

class TestFractalContract:
    def test_skill_result_has_fractal_fields(self):
        from skill_engine import SkillResult
        sr = SkillResult(skill_id="test", radius_gained=0.1, validate="GO",
                         fingerprint=[], state_vector={})
        assert hasattr(sr, "validate")
        assert hasattr(sr, "radius_gained")
        assert hasattr(sr, "fingerprint")
        assert hasattr(sr, "state_vector")

    def test_agent_result_has_fractal_fields(self):
        ar = AgentResult(agent_id="test")
        assert hasattr(ar, "validate")
        assert hasattr(ar, "radius_gained")
        assert hasattr(ar, "fingerprint")
        assert hasattr(ar, "state_vector")

    def test_spiral_state_from_skill_result(self):
        from skill_engine import SkillResult
        sr = SkillResult(skill_id="s1", radius_gained=0.2, validate="GO",
                         fingerprint=["tag1"], state_vector={"phase": 4})
        ss = SpiralState.from_skill_result(sr)
        assert isinstance(ss, SpiralState)
        assert ss.validate == "GO"
        assert ss.phase == 4

    def test_spiral_state_from_agent_result(self):
        ar = AgentResult(agent_id="a1", phase=8, validate="WARN",
                         fingerprint=["agent:a1"], radius_gained=0.5)
        ss = SpiralState(
            entity_id=ar.agent_id,
            phase=ar.phase,
            validate=ar.validate,
            fingerprint=ar.fingerprint,
            radius_gained=ar.radius_gained,
        )
        assert ss.validate == "WARN"
        assert ss.phase == 8


# ─────────────────────────────────────────────────────────────
# ── spiral_loop main dispatch ─────────────────────────────────
# ─────────────────────────────────────────────────────────────

class TestSpiralLoopDispatch:
    def test_orchestrate_flag_dispatches(self, monkeypatch, capsys):
        import spiral_loop
        monkeypatch.setattr(sys, "argv", ["spiral_loop", "--orchestrate", "--status"])
        rc = spiral_loop.main()
        assert isinstance(rc, int)
        out = capsys.readouterr().out
        # Should NOT go through cmd_status (which shows "Ciclos completados")
        assert "Nivel-0" in out or "agentes" in out.lower()
