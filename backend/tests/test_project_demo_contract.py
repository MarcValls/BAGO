from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


API = Path(__file__).resolve().parents[1] / ".bago" / "api"
sys.path.insert(0, str(API))
SPEC = importlib.util.spec_from_file_location("handlers_project_demo_test", API / "handlers_project.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_create_demo_project_is_runnable_and_identifiable(tmp_path: Path) -> None:
    root = tmp_path / "BAGO-Demo"
    result = MODULE._create_demo_project(str(root))
    assert result["template"] == "bago-demo-v1"
    assert (root / "package.json").is_file()
    assert (root / "src" / "app.js").read_text(encoding="utf-8").strip()


def test_create_demo_project_refuses_non_empty_directory(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    root.mkdir()
    (root / "keep.txt").write_text("user data", encoding="utf-8")
    try:
        MODULE._create_demo_project(str(root))
    except FileExistsError:
        pass
    else:
        raise AssertionError("must not overwrite a non-empty directory")
    assert (root / "keep.txt").read_text(encoding="utf-8") == "user data"
