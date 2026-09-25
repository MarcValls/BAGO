from pathlib import Path

import pytest

from bago_core.resolver import add_piece_paths

add_piece_paths("core.package")
import learning_writer


def test_learning_observations_and_promotions_use_registered_gateway(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "repo"
    monkeypatch.setattr(learning_writer, "_BAGO_ROOT", root)
    monkeypatch.setattr(learning_writer, "_STATE_DIR", root / ".bago" / "state")
    monkeypatch.setattr(learning_writer, "_KNOWLEDGE", root / ".bago" / "knowledge")
    monkeypatch.setattr(learning_writer, "_LEARNINGS", root / ".bago" / "state" / "auto_learnings.jsonl")
    monkeypatch.setattr(learning_writer, "_AUTO_PATTERNS", root / ".bago" / "knowledge" / "auto_patterns.md")

    writer = learning_writer.LearningWriter()
    for cycle in range(3):
        writer.observe(goal="health_check", agent="VALIDADOR", success=True, cycle=cycle)

    assert len(learning_writer._LEARNINGS.read_text(encoding="utf-8").splitlines()) == 3
    assert "PATTERN: VALIDADOR:health_check:ok" in learning_writer._AUTO_PATTERNS.read_text(encoding="utf-8")


def test_learning_gateway_blocks_unregistered_target_before_write(tmp_path: Path) -> None:
    from bago_core.server_effects import append_learning_text

    target = tmp_path / ".bago" / "knowledge" / "unexpected.md"
    with pytest.raises(RuntimeError) as blocked:
        append_learning_text(target, "must-not-write\n", trusted_root=tmp_path)

    assert blocked.value.code == "server_learning_target_invalid"
    assert not target.exists()
