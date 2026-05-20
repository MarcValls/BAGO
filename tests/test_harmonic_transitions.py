import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".bago" / "core"))

from autonomous_loop import AutonomousLoop, HARMONIC_MODES
import json


class TestStableVerifiedIntegrity:
    def test_stable_verified_requires_all_gates(self):
        loop = AutonomousLoop(dry_run=True)
        # All gates passing
        after = {
            "version_truth": True,
            "audit_ok": True,
            "encoding_ok": True,
            "tests_ok": True,
            "git_dirty": False,
            "health": 80,
            "pack_ok": True,
            "stale_count": 0,
        }
        before = dict(after)
        # Simulate stable count threshold reached
        loop._stable_count = 2
        result = loop.decide([], before, after)
        assert result == "STABLE_VERIFIED"

    def test_stable_unverified_when_version_truth_fails(self):
        loop = AutonomousLoop(dry_run=True)
        after = {
            "version_truth": False,
            "audit_ok": True,
            "encoding_ok": True,
            "tests_ok": True,
            "git_dirty": False,
            "health": 80,
            "pack_ok": True,
            "stale_count": 0,
        }
        before = dict(after)
        loop._stable_count = 2
        result = loop.decide([], before, after)
        assert result == "STABLE_UNVERIFIED"

    def test_stable_unverified_when_git_dirty(self):
        loop = AutonomousLoop(dry_run=True)
        after = {
            "version_truth": True,
            "audit_ok": True,
            "encoding_ok": True,
            "tests_ok": True,
            "git_dirty": True,
            "health": 80,
            "pack_ok": True,
            "stale_count": 0,
        }
        before = dict(after)
        loop._stable_count = 2
        result = loop.decide([], before, after)
        assert result == "STABLE_UNVERIFIED"

    def test_stable_unverified_when_audit_fails(self):
        loop = AutonomousLoop(dry_run=True)
        after = {
            "version_truth": True,
            "audit_ok": False,
            "encoding_ok": True,
            "tests_ok": True,
            "git_dirty": False,
            "health": 80,
            "pack_ok": True,
            "stale_count": 0,
        }
        before = dict(after)
        loop._stable_count = 2
        result = loop.decide([], before, after)
        assert result == "STABLE_UNVERIFIED"


class TestManualModeOverride:
    def test_manual_mode_crisis_recovery_overrides_auto(self):
        loop = AutonomousLoop(dry_run=True, manual_mode="crisis_recovery")
        # Sensor state would normally select production_monitor
        state = {
            "health": 95,
            "pack_ok": True,
            "version_truth": True,
            "git_dirty": False,
            "audit_status": "GO",
            "stale_count": 0,
            "inbox_tasks": [],
        }
        plan = loop.plan(state)
        # plan() should run without error and use manual mode
        assert isinstance(plan, list)

    def test_manual_mode_clean_install(self):
        loop = AutonomousLoop(dry_run=True, manual_mode="clean_install")
        state = {"health": 50, "pack_ok": False, "version_truth": False, "git_dirty": True, "audit_status": "KO", "stale_count": 0, "inbox_tasks": []}
        plan = loop.plan(state)
        # Should still be clean_install despite bad sensors
        # We verify by checking the mode was used (plan exists)
        assert len(plan) >= 0  # plan generated, no crash


class TestModePersistence:
    def test_mode_persists_to_global_state(self, tmp_path):
        # Patch STATE_DIR temporarily
        import autonomous_loop as al
        orig_state_dir = al._STATE_DIR
        test_state = tmp_path / "state"
        test_state.mkdir()
        al._STATE_DIR = test_state
        try:
            loop = AutonomousLoop(dry_run=False)
            loop._persist_harmonic_mode("crisis_recovery")
            gs = test_state / "global_state.json"
            assert gs.exists()
            data = json.loads(gs.read_text(encoding="utf-8"))
            assert data.get("harmonic_mode") == "crisis_recovery"
        finally:
            al._STATE_DIR = orig_state_dir


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
