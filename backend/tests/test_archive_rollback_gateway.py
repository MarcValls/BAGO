from __future__ import annotations

import builtins
import sys
import zipfile
from argparse import Namespace
from pathlib import Path

import pytest


def _make_backup(path: Path, entries: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


@pytest.mark.parametrize("restore_backed_up_state", [False, True])
def test_cli_archive_rollback_restores_runtime_and_applies_explicit_state_choice(
    tmp_path: Path, monkeypatch, capsys, restore_backed_up_state: bool,
) -> None:
    import authorization_boundary
    from bago_core.commands.cmd_lifecycle import cmd_rollback_archive

    install = tmp_path / "install"
    (install / "state").mkdir(parents=True)
    (install / "old-marker.txt").write_text("old runtime", encoding="utf-8")
    (install / "state" / "keep.txt").write_text("current state", encoding="utf-8")
    backup_root = tmp_path / "backups"
    archive = backup_root / "bago-programfiles-backup-fixture.zip"
    _make_backup(archive, {
        "new-marker.txt": "restored runtime",
        "state/archived.txt": "archived state",
    })
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "si")
    monkeypatch.setattr(authorization_boundary, "state_root", lambda: tmp_path / "authorization-state")

    result = cmd_rollback_archive(Namespace(
        install_dir=str(install), backup_root=str(backup_root), backup_zip=str(archive),
        restore_backed_up_state=restore_backed_up_state,
    ))

    assert result == 0
    assert (install / "new-marker.txt").read_text(encoding="utf-8") == "restored runtime"
    assert not (install / "old-marker.txt").exists()
    if restore_backed_up_state:
        assert (install / "state" / "archived.txt").read_text(encoding="utf-8") == "archived state"
        assert not (install / "state" / "keep.txt").exists()
    else:
        assert (install / "state" / "keep.txt").read_text(encoding="utf-8") == "current state"
        assert not (install / "state" / "archived.txt").exists()
    assert list(backup_root.glob("bago-pre-rollback-safety-*.zip"))
    assert "Receipt:" in capsys.readouterr().out


def test_archive_rollback_rejects_install_drift_before_safety_archive(tmp_path: Path) -> None:
    from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
    from execution_request import build_execution_request
    from execution_adapters.archive_rollback import SystemInstallArchiveRollbackEffectAdapter

    install = tmp_path / "install"
    install.mkdir()
    (install / "old.txt").write_text("before approval", encoding="utf-8")
    backup_root = tmp_path / "backups"
    archive = backup_root / "bago-programfiles-backup-fixture.zip"
    _make_backup(archive, {"restored.txt": "payload"})
    target = SystemInstallArchiveRollbackEffectAdapter.prepare_target(
        install, backup_root, archive, restore_backed_up_state=False,
    )
    request = build_execution_request(
        effect_id="system.install.archive.rollback", actor_kind="user",
        principal_id="interactive-local-user", session_id="rollback-session",
        source_surface="cli.install.archive-rollback", target=target,
        arguments={}, scope="system",
    )
    (install / "old.txt").write_text("changed after approval", encoding="utf-8")
    fake_authorization = {
        "state": "consumed", "effect_id": request.effect_id,
        "operation_fingerprint": request.fingerprint,
        "proof": {
            "effect_id": request.effect_id,
            "operation_fingerprint": request.fingerprint,
            "authenticated_session_id": request.session_id,
            "user_decision": "approve",
            "provenance": {"kind": "direct_user_interaction", "channel": "cli"},
        },
    }

    with pytest.raises(ExecutionGatewayError, match="changed after approval"):
        SystemInstallArchiveRollbackEffectAdapter().execute(
            request, ExecutionContext(services={"_authorization": fake_authorization}),
        )

    assert (install / "old.txt").read_text(encoding="utf-8") == "changed after approval"
    assert not list(backup_root.glob("bago-pre-rollback-safety-*.zip"))


def test_archive_rollback_rejects_zip_slip_before_extraction(tmp_path: Path) -> None:
    from execution_adapter_contract import ExecutionGatewayError
    from execution_adapters.archive_rollback import SystemInstallArchiveRollbackEffectAdapter

    archive = tmp_path / "bago-programfiles-backup-malicious.zip"
    _make_backup(archive, {"../escape.txt": "outside"})
    stage = tmp_path / "stage"

    with pytest.raises(ExecutionGatewayError, match="unsafe path"):
        SystemInstallArchiveRollbackEffectAdapter._safe_extract(archive, stage)

    assert not (tmp_path / "escape.txt").exists()
    assert not stage.exists()


def test_rollback_archive_is_an_obvious_root_cli_command(capsys) -> None:
    from bago_core.launcher import main

    with pytest.raises(SystemExit) as exit_info:
        main(["rollback-archive", "--help"])

    assert exit_info.value.code == 0
    assert "--backup-zip" in capsys.readouterr().out
