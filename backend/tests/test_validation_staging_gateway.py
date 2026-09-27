from pathlib import Path
import tempfile

import pytest

from bago_core.execution.staging_workspace import StagingError, open_staging_workspace


def test_staging_copy_and_cleanup_use_gateway_owned_temp_identity(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "temp"))
    source = tmp_path / "project"
    source.mkdir()
    (source / "src").mkdir()
    (source / "src" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (source / ".env").write_text("secret\n", encoding="utf-8")

    staging = open_staging_workspace(source)
    staging_root = Path(staging.root)
    assert staging_root.parent.parent == Path(tmp_path / "temp" / "BAGO" / "validation")
    assert (staging_root / "src" / "main.py").read_text(encoding="utf-8") == "print('ok')\n"
    assert not (staging_root / ".env").exists()
    assert "src/main.py" in staging.snapshot.copied_paths

    staging.close()
    assert not staging_root.exists()


def test_staging_rejects_noncanonical_parent_before_effect(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "temp"))
    source = tmp_path / "project"
    source.mkdir()

    with pytest.raises(StagingError) as blocked:
        open_staging_workspace(source, parent_dir=tmp_path / "other")

    assert blocked.value.code == "staging_target_out_of_scope"
    assert not (tmp_path / "other").exists()


def test_gateway_cleanup_rejects_staging_identity_it_did_not_create(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "temp"))
    from bago_core.server_effects import cleanup_validation_workspace

    with pytest.raises(RuntimeError) as blocked:
        cleanup_validation_workspace("0" * 32, label="bago_staging")

    assert blocked.value.code == "validation_staging_cleanup_unowned"
    assert not (tmp_path / "temp" / "BAGO" / "validation").exists()
