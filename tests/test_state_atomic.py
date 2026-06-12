from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_atomic_write_json_writes_final_file_only() -> None:
    import sys

    sys.path.insert(0, str(ROOT / ".bago" / "core"))
    from io_utils import atomic_write_json

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "state.json"
        atomic_write_json(path, {"ok": True})
        assert path.exists()
        assert path.read_text(encoding="utf-8").strip() == '{\n  "ok": true\n}'
        assert not path.with_name(path.name + ".tmp").exists()


def test_read_json_quarantine_moves_corrupt_file() -> None:
    import sys

    sys.path.insert(0, str(ROOT / ".bago" / "core"))
    from io_utils import read_json_quarantine

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "broken.json"
        path.write_text("{", encoding="utf-8")
        payload = read_json_quarantine(path, default={})
        assert payload == {}
        assert not path.exists()
        assert path.with_suffix(".json.corrupt").exists()

