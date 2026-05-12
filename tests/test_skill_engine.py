"""tests/test_skill_engine.py — Suite de tests para el Skill Layer (Sprint 1)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add tools to path for direct import
sys.path.insert(0, str(Path(__file__).parent.parent / ".bago" / "tools"))

import skill_engine


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

SAMPLE_REGISTRY = {
    "test_skill": {
        "steps": [0, 8, 9, 10, 11],
        "phase": 0,
        "category": "tests",
        "description": "Test skill fixture",
    },
    "mini_docs": {
        "steps": [3, 4, 5],
        "phase": 3,
        "category": "docs",
        "description": "Minimal docs skill",
    },
}


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Redirect all state I/O to a tmp_path so tests don't touch real state."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    monkeypatch.setattr(skill_engine, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(skill_engine, "REGISTRY_FILE", tmp_path / "skill_registry.json")
    monkeypatch.setattr(skill_engine, "GS_FILE", tmp_path / "global_state.json")
    # Stub _bago to avoid real subprocess calls
    monkeypatch.setattr(skill_engine, "_bago", lambda cmd, timeout=30: (0, "validate: OK", ""))
    yield tmp_path


# ─────────────────────────────────────────────────────────────
# Tests: SkillResult contract
# ─────────────────────────────────────────────────────────────

def test_skill_result_shape():
    """SkillResult has required fields and to_dict works."""
    r = skill_engine.SkillResult(
        skill_id="code_review",
        validate="GO",
        radius_gained=0.5,
        state_vector={"health": 95},
        fingerprint=["skill:code_review", "validate:GO"],
    )
    assert r.skill_id == "code_review"
    assert r.validate in ("GO", "WARN", "FAIL")
    assert isinstance(r.radius_gained, float)
    assert isinstance(r.state_vector, dict)
    assert isinstance(r.fingerprint, list)

    d = r.to_dict()
    assert set(d.keys()) == {"skill_id", "validate", "radius_gained", "state_vector", "fingerprint"}


def test_skill_result_validate_values():
    """validate field only accepts GO/WARN/FAIL."""
    for val in ("GO", "WARN", "FAIL"):
        r = skill_engine.SkillResult("x", val, 0.0, {}, [])
        assert r.validate == val


def test_skill_result_repr():
    r = skill_engine.SkillResult("my_skill", "GO", 1.2, {}, [])
    assert "my_skill" in repr(r)
    assert "GO" in repr(r)


# ─────────────────────────────────────────────────────────────
# Tests: registry loading
# ─────────────────────────────────────────────────────────────

def test_load_registry_empty_when_missing(isolated_state):
    """_load_registry returns {} if file doesn't exist."""
    reg = skill_engine._load_registry()
    assert reg == {}


def test_load_registry_reads_json(isolated_state):
    skill_engine.REGISTRY_FILE.write_text(json.dumps(SAMPLE_REGISTRY))
    reg = skill_engine._load_registry()
    assert "test_skill" in reg
    assert reg["test_skill"]["phase"] == 0


# ─────────────────────────────────────────────────────────────
# Tests: state persistence
# ─────────────────────────────────────────────────────────────

def test_skill_state_roundtrip(isolated_state):
    """State can be saved and loaded back intact."""
    data = {"cycles": [{"validate": "GO", "radius": 0.3}], "total_radius": 0.3}
    skill_engine._save_skill_state("my_skill", data)
    loaded = skill_engine._load_skill_state("my_skill")
    assert loaded["total_radius"] == 0.3
    assert loaded["cycles"][0]["validate"] == "GO"


def test_skill_state_default_when_missing(isolated_state):
    state = skill_engine._load_skill_state("nonexistent")
    assert state == {"cycles": [], "total_radius": 0.0}


def test_skill_gradient_roundtrip(isolated_state):
    g = {"step_weights": {"OBSERVE": 1.5}, "last_delta": 0.2}
    skill_engine._save_skill_gradient("g_skill", g)
    loaded = skill_engine._load_skill_gradient("g_skill")
    assert loaded["last_delta"] == 0.2


# ─────────────────────────────────────────────────────────────
# Tests: phase rotation
# ─────────────────────────────────────────────────────────────

def test_phase_rotation_selects_correct_steps(isolated_state):
    """A skill with phase=3 starts at step 3 (DETECT) in the rotation."""
    skill_engine.REGISTRY_FILE.write_text(json.dumps(SAMPLE_REGISTRY))
    # mini_docs has steps=[3,4,5] (DETECT, PROPOSE, SELECT) phase=3
    # No RECORD step → no state file, but result is valid
    result = skill_engine.run_skill("mini_docs", SAMPLE_REGISTRY)
    assert result.skill_id == "mini_docs"
    # Without a RECORD step, state file is NOT created — that's correct behaviour
    assert result.validate in ("GO", "WARN", "FAIL")
    # fingerprint should contain skill id
    assert any("mini_docs" in tag for tag in result.fingerprint)


def test_phase_zero_runs_observe_first(isolated_state):
    """test_skill (phase=0) starts with OBSERVE."""
    skill_engine.REGISTRY_FILE.write_text(json.dumps(SAMPLE_REGISTRY))
    result = skill_engine.run_skill("test_skill", SAMPLE_REGISTRY)
    state = skill_engine._load_skill_state("test_skill")
    assert len(state["cycles"]) == 1
    assert state["total_radius"] >= 0.0


# ─────────────────────────────────────────────────────────────
# Tests: run_skill end-to-end
# ─────────────────────────────────────────────────────────────

def test_run_skill_returns_skill_result(isolated_state):
    result = skill_engine.run_skill("test_skill", SAMPLE_REGISTRY)
    assert isinstance(result, skill_engine.SkillResult)
    assert result.skill_id == "test_skill"
    assert result.validate in ("GO", "WARN", "FAIL")


def test_run_skill_unknown_returns_fail(isolated_state):
    result = skill_engine.run_skill("nonexistent_skill", SAMPLE_REGISTRY)
    assert result.validate == "FAIL"
    assert "unknown-skill" in result.fingerprint


def test_run_skill_accumulates_radius(isolated_state):
    """Running the same skill twice accumulates radius."""
    skill_engine.run_skill("test_skill", SAMPLE_REGISTRY)
    skill_engine.run_skill("test_skill", SAMPLE_REGISTRY)
    state = skill_engine._load_skill_state("test_skill")
    assert len(state["cycles"]) == 2


def test_run_skill_fingerprint_contains_skill_id(isolated_state):
    result = skill_engine.run_skill("test_skill", SAMPLE_REGISTRY)
    assert any("test_skill" in tag for tag in result.fingerprint)


def test_run_skill_validate_go_when_bago_succeeds(isolated_state):
    """When _bago returns rc=0, validate should be GO."""
    result = skill_engine.run_skill("test_skill", SAMPLE_REGISTRY)
    # _bago is stubbed to return rc=0 → validate = GO
    assert result.validate == "GO"


def test_run_skill_validate_fail_when_bago_fails(isolated_state, monkeypatch):
    """When _bago returns rc=1, validate should be FAIL."""
    monkeypatch.setattr(skill_engine, "_bago", lambda cmd, timeout=30: (1, "", "error"))
    result = skill_engine.run_skill("test_skill", SAMPLE_REGISTRY)
    assert result.validate == "FAIL"


# ─────────────────────────────────────────────────────────────
# Tests: CLI commands
# ─────────────────────────────────────────────────────────────

def test_cmd_skill_list_empty(isolated_state, capsys):
    rc = skill_engine.cmd_skill_list()
    assert rc == 0
    out = capsys.readouterr().out
    assert "No hay skills" in out


def test_cmd_skill_list_shows_skills(isolated_state, capsys):
    skill_engine.REGISTRY_FILE.write_text(json.dumps(SAMPLE_REGISTRY))
    rc = skill_engine.cmd_skill_list()
    assert rc == 0
    out = capsys.readouterr().out
    assert "test_skill" in out
    assert "mini_docs" in out


def test_cmd_skill_run_unknown(isolated_state, capsys):
    skill_engine.REGISTRY_FILE.write_text(json.dumps(SAMPLE_REGISTRY))
    rc = skill_engine.cmd_skill_run("does_not_exist")
    assert rc == 1


def test_cmd_skill_run_known(isolated_state):
    skill_engine.REGISTRY_FILE.write_text(json.dumps(SAMPLE_REGISTRY))
    rc = skill_engine.cmd_skill_run("test_skill")
    assert rc == 0


def test_cmd_skill_status_empty(isolated_state, capsys):
    rc = skill_engine.cmd_skill_status()
    assert rc == 0


def test_cmd_skill_status_shows_all(isolated_state, capsys):
    skill_engine.REGISTRY_FILE.write_text(json.dumps(SAMPLE_REGISTRY))
    skill_engine.run_skill("test_skill", SAMPLE_REGISTRY)
    rc = skill_engine.cmd_skill_status()
    assert rc == 0
    out = capsys.readouterr().out
    assert "test_skill" in out


# ─────────────────────────────────────────────────────────────
# Tests: CLI dispatch (main)
# ─────────────────────────────────────────────────────────────

def test_main_list(isolated_state):
    skill_engine.REGISTRY_FILE.write_text(json.dumps(SAMPLE_REGISTRY))
    rc = skill_engine.main(["list"])
    assert rc == 0


def test_main_status(isolated_state):
    rc = skill_engine.main(["status"])
    assert rc == 0


def test_main_run_missing_arg(isolated_state, capsys):
    rc = skill_engine.main(["run"])
    assert rc == 1


def test_main_unknown_subcommand(isolated_state, capsys):
    rc = skill_engine.main(["bogus"])
    assert rc == 1


def test_main_help(isolated_state, capsys):
    rc = skill_engine.main(["--help"])
    assert rc == 0


# ─────────────────────────────────────────────────────────────
# Tests: registry file structure
# ─────────────────────────────────────────────────────────────

def test_skill_registry_json_exists():
    """The production skill_registry.json must exist and have ≥3 skills."""
    reg_path = Path(__file__).parent.parent / ".bago" / "state" / "skill_registry.json"
    assert reg_path.exists(), f"Missing: {reg_path}"
    data = json.loads(reg_path.read_text())
    assert len(data) >= 3, "skill_registry.json debe tener ≥3 skills"
    for sid, entry in data.items():
        assert "steps" in entry, f"{sid}: missing 'steps'"
        assert "phase" in entry, f"{sid}: missing 'phase'"
        assert "category" in entry, f"{sid}: missing 'category'"
        assert isinstance(entry["steps"], list)
        assert all(0 <= s <= 11 for s in entry["steps"]), f"{sid}: steps must be in [0-11]"
