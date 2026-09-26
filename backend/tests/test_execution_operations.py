from __future__ import annotations

import pytest


def test_sqlite_operation_ledger_recovers_pending_and_replays_committed_receipt(tmp_path):
    from execution_operations import ExecutionOperationError, SQLiteExecutionOperationStore

    db_path = tmp_path / "state" / "execution_claims.sqlite3"
    first = SQLiteExecutionOperationStore(db_path)
    pending = first.prepare("pipeline:step-1:attempt:1", "file:/repo/a.txt", "digest-a", 1)
    assert pending["status"] == "PENDING"

    restarted = SQLiteExecutionOperationStore(db_path)
    recovered = restarted.prepare("pipeline:step-1:attempt:1", "file:/repo/a.txt", "digest-a", 2)
    assert recovered["status"] == "PENDING"
    restarted.commit("pipeline:step-1:attempt:1", {"receipt_id": "receipt-a", "ok": True})

    replay = SQLiteExecutionOperationStore(db_path).get("pipeline:step-1:attempt:1")
    assert replay["status"] == "COMMITTED"
    assert replay["receipt"] == {"receipt_id": "receipt-a", "ok": True}
    with pytest.raises(ExecutionOperationError) as conflict:
        restarted.prepare("pipeline:step-1:attempt:1", "file:/repo/a.txt", "digest-b", 3)
    assert conflict.value.code == "execution_operation_conflict"
