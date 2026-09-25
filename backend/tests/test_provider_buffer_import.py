from __future__ import annotations

import importlib.util
from pathlib import Path


def test_provider_buffer_import_does_not_create_persistent_directory(tmp_path, monkeypatch) -> None:
    requested_path = tmp_path / "buffer"
    monkeypatch.setenv("BAGO_BUFFER_DIR", str(requested_path))
    source = (
        Path(__file__).resolve().parents[1]
        / ".bago"
        / "api"
        / "handlers_provider_buffer.py"
    )
    spec = importlib.util.spec_from_file_location("provider_buffer_import_probe", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module._BUFFER_STATE == {}
    assert not requested_path.exists()
