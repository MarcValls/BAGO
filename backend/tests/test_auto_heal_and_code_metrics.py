from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".bago" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import auto_heal
import code_metrics


def test_auto_heal_scans_and_repairs_only_the_supplied_fixture_root(tmp_path) -> None:
    tools = tmp_path / ".bago" / "tools"
    tools.mkdir(parents=True)
    (tools / "bad_tool.py").write_text("print('x')\n", encoding="utf-8")
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    (tmp_path / "empty.json").write_text("", encoding="utf-8")
    (tmp_path / "broken.py").write_text("def x(:\n    pass\n", encoding="utf-8")
    (tmp_path / "large.bin").write_bytes(b"0" * (auto_heal.MAX_LARGE_SIZE + 1))

    assert len(auto_heal.scan_missing_test_flag(tmp_path)) == 1
    assert auto_heal._json_fix_replacement("") == "{}\n"
    assert auto_heal._json_fix_replacement("[") == "[]\n"
    assert len(auto_heal.scan_invalid_python(tmp_path)) == 1
    assert len(auto_heal.scan_large_files(tmp_path)) == 1
    actions = auto_heal.apply_fixes(tmp_path, auto_heal.scan_invalid_json(tmp_path), dry_run=False)

    assert {item["file"] for item in actions} == {"bad.json", "empty.json"}
    assert all(item["action"] == "rewrite_json" and item["applied"] for item in actions)
    assert json.loads((tmp_path / "bad.json").read_text(encoding="utf-8")) == {}


def test_code_metrics_counts_sources_and_excludes_dependency_trees(tmp_path) -> None:
    (tmp_path / "a.py").write_text("print('x')\nprint('y')\n", encoding="utf-8")
    (tmp_path / "b.ts").write_text("const a = 1;\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("hello\nworld\n", encoding="utf-8")
    dependency = tmp_path / "node_modules"
    dependency.mkdir()
    (dependency / "skip.js").write_text("ignored\n", encoding="utf-8")

    report = code_metrics.analyze(tmp_path)

    assert code_metrics._normalize_exts("ts,py") == {".ts", ".py"}
    assert report["total"]["files"] == 3
    assert report["extensions"][".py"]["lines"] == 2
    assert ".js" not in report["extensions"]
    assert code_metrics._sorted_extensions(report["extensions"], "files")[0][0] in {".md", ".py", ".ts"}


@pytest.mark.parametrize("parser", [auto_heal.build_parser, code_metrics.build_parser])
def test_removed_selftest_switch_is_rejected(parser) -> None:
    with pytest.raises(SystemExit) as exc:
        parser().parse_args(["--test"])

    assert exc.value.code == 2
