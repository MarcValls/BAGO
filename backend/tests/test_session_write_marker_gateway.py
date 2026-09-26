from __future__ import annotations

from pathlib import Path

from session_turn_mixin import _present_write_blocks
import effect_sink_inventory as inventory


def test_legacy_write_marker_is_presented_without_authority_or_materialization():
    response = _present_write_blocks("before\n[WRITE:src/new.py]\nprint('proposal')\n[/WRITE]\nafter")

    assert "Propuesta para `src/new.py`" in response
    assert "filesystem.write` autorizada" in response
    assert "print('proposal')" in response
    assert "[WRITE:" not in response
    assert "[/WRITE]" not in response
    path = inventory.REPO_ROOT / "backend/.bago/core/session_turn_mixin.py"
    assert inventory.scan_python(Path(path)) == []
