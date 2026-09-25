import json
from pathlib import Path

import pytest

from bago_core.resolver import add_piece_paths

add_piece_paths("core.package", "api.package")


def test_structured_logger_appends_and_rotates_through_gateway(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path / "user"))
    from structured_log import StructuredLogger

    logger = StructuredLogger(max_bytes=1, backup_count=2)
    logger.info("first", port=8080)
    logger.info("second", port=8081)

    current = logger.log_path.read_text(encoding="utf-8").splitlines()
    prior = (logger.log_dir / "bridge.1.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(current[0])["event"] == "second"
    assert json.loads(prior[0])["event"] == "first"


def test_structured_logger_rejects_noncanonical_directory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path / "user"))
    from structured_log import StructuredLogger

    with pytest.raises(ValueError, match="canonical BAGO log root"):
        StructuredLogger(log_dir=tmp_path / "other")


def test_structured_log_adapter_rejects_target_drift_before_write(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path / "user"))
    from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
    from execution_adapters.structured_logging import StructuredLoggingEffectAdapter
    from execution_request import build_execution_request

    request = build_execution_request(
        effect_id="logging.append",
        actor_kind="server",
        principal_id="bago-runtime",
        session_id="test-log",
        source_surface="server.test",
        target={"path": str(tmp_path / "other" / "bridge.jsonl"), "allowed_root": str(tmp_path / "other"), "operation": "append_rotate"},
        arguments={"content": '{"event":"blocked"}\n', "max_bytes": 4096, "backup_count": 3},
        scope="persistent",
    )
    context = ExecutionContext(services={"_authorization": {"kind": "server_policy"}})

    with pytest.raises(ExecutionGatewayError) as blocked:
        StructuredLoggingEffectAdapter().execute(request, context)

    assert blocked.value.code == "structured_log_target_invalid"
    assert not (tmp_path / "other" / "bridge.jsonl").exists()
