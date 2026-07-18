from __future__ import annotations

from pathlib import Path

from bago_core.commands.cmd_doctor import _ui_runtime_status


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"


def test_frontend_is_the_only_ui_source() -> None:
    assert (REPOSITORY_ROOT / "frontend" / "src" / "main.tsx").is_file()
    parallel_source = BACKEND_ROOT / "ui-react" / "src"
    assert not parallel_source.exists() or not any(path.is_file() for path in parallel_source.rglob("*"))


def test_ui_runtime_status_checks_generated_dist(tmp_path: Path) -> None:
    ok, _ = _ui_runtime_status(tmp_path)
    assert ok is False

    index = tmp_path / "ui-react" / "dist" / "index.html"
    index.parent.mkdir(parents=True)
    index.write_text("<!doctype html>", encoding="utf-8")

    ok, detail = _ui_runtime_status(tmp_path)
    assert ok is True
    assert str(index) in detail


def test_release_configuration_does_not_package_parallel_ui_source() -> None:
    for relative in ("package.json", "scripts/package_v4.py", "scripts/package_audit_bundle.py"):
        text = (BACKEND_ROOT / relative).read_text(encoding="utf-8")
        assert '"ui-react/src",' not in text
        assert '"ui-react/src/**/*"' not in text
