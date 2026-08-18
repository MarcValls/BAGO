from pathlib import Path

import pytest

from scripts.packaging_common import normalize_release_version, rel_posix, sha256


def test_normalize_release_version_preserves_packaging_contract():
    assert normalize_release_version(" V4.8.1-RC1 ") == "4.8.1-rc1"
    with pytest.raises(ValueError):
        normalize_release_version("")
    with pytest.raises(ValueError):
        normalize_release_version("4.8.1/unsafe")


def test_shared_path_and_hash_helpers(tmp_path: Path):
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"bago")
    assert rel_posix(Path("one") / "two") == "one/two"
    assert sha256(artifact) == "bdbd98e1b9f7fad0caa4cfe311592d2056eef0c298a39be14c805ae4d7b0ec17"
