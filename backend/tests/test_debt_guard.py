from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / ".bago" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import debt_guard


def _authorize_cli(monkeypatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    execute_cli_effect = debt_guard.execute_cli_effect
    monkeypatch.setattr(
        debt_guard,
        "execute_cli_effect",
        lambda request, *, confirmation_text: execute_cli_effect(
            request,
            confirmation_text=confirmation_text,
            input_fn=lambda _prompt: "s",
            output_fn=lambda _message: None,
        ),
    )


def test_default_config_round_trips(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    _authorize_cli(monkeypatch)
    config = debt_guard.load_config(tmp_path)

    assert isinstance(config, dict)
    assert "rules" in config
    assert config["rules"]["D01"] == {
        "active": True,
        "action": "block",
        "desc": "Parsers argparse anónimos",
    }
    assert config["rules"]["D06"]["active"] is True
    assert config["rules"]["D06"]["action"] == "block"
    assert config["rules"]["D09"]["active"] is False
    assert ".bago/tools/" in config["exclude_paths"]

    debt_guard.save_config(tmp_path, config)
    restored = debt_guard.load_config(tmp_path)

    assert restored["rules"] == config["rules"]


def test_hook_install_and_uninstall_use_gateway_owner(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    _authorize_cli(monkeypatch)

    assert debt_guard.cmd_install(tmp_path) == 0
    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    assert debt_guard.HOOK_MARKER in hook.read_text(encoding="utf-8")

    assert debt_guard.cmd_uninstall(tmp_path) == 0
    assert not hook.exists()


def test_staged_path_listing_rejects_paths_outside_repository(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    outside = tmp_path.parent / "outside.py"
    outside.write_text("secret = True\n", encoding="utf-8")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(
        debt_guard,
        "execute_cli_effect",
        lambda *_args, **_kwargs: ({"ok": True, "stdout": "../outside.py\0"}, {}),
    )

    assert debt_guard._staged_python_files(tmp_path) == []


def test_check_files_applies_enabled_rules_and_exclusions(tmp_path: Path) -> None:
    config = debt_guard.load_config(tmp_path)
    clean = tmp_path / "clean.py"
    clean.write_text("def hello() -> str:\n    return 'hi'\n", encoding="utf-8")
    blocked, warned = debt_guard._check_files([clean], tmp_path, config)
    assert not blocked
    assert not warned

    anonymous = tmp_path / "anonymous.py"
    anonymous.write_text("sub.add_parser('foo', help='x')\n", encoding="utf-8")
    blocked, _ = debt_guard._check_files([anonymous], tmp_path, config)
    assert any(item.code == "D01" for item in blocked)

    silent = tmp_path / "silent.py"
    silent.write_text("try:\n    x = 1\nexcept Exception:\n    pass\n", encoding="utf-8")
    blocked, _ = debt_guard._check_files([silent], tmp_path, config)
    assert any(item.code == "D06" for item in blocked)

    excluded = tmp_path / ".bago" / "tools" / "probe.py"
    excluded.parent.mkdir(parents=True)
    excluded.write_text("sub.add_parser('foo')\n", encoding="utf-8")
    blocked, warned = debt_guard._check_files([excluded], tmp_path, config)
    assert not blocked
    assert not warned


def test_status_is_read_only_and_cli_test_mode_points_to_pytest(tmp_path: Path) -> None:
    config = debt_guard.load_config(tmp_path)
    output = io.StringIO()
    with redirect_stdout(output):
        result = debt_guard.cmd_status(tmp_path, config)

    assert result == 0
    assert "BAGO Debt Guard" in output.getvalue()
    assert debt_guard.main(["--root", str(tmp_path), "--test"]) == 2
