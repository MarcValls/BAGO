from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from schedule_registry import ScheduleError, ScheduleRegistry, next_cron_run


def schedule_payload(**overrides):
    payload = {
        "name": "Informe periódico",
        "target_type": "task",
        "target": {"task": "Generar un informe local"},
        "schedule_type": "interval",
        "interval_s": 60,
        "timezone": "UTC",
        "enabled": True,
        "confirmed": True,
        "approved_permissions": [],
    }
    payload.update(overrides)
    return payload


def test_enabled_schedule_requires_confirmation(tmp_path):
    registry = ScheduleRegistry(tmp_path)

    with pytest.raises(ScheduleError, match="confirmación"):
        registry.create(schedule_payload(confirmed=False))


def test_interval_schedule_persists_and_can_pause_resume(tmp_path):
    registry = ScheduleRegistry(tmp_path)
    created = registry.create(schedule_payload())

    reloaded = ScheduleRegistry(tmp_path)
    assert reloaded.get(created["id"])["target"]["task"] == "Generar un informe local"

    paused = reloaded.update(created["id"], {"enabled": False})
    assert paused["status"] == "paused"
    assert paused["next_run_at"] == ""

    resumed = reloaded.update(created["id"], {"enabled": True, "confirmed": True})
    assert resumed["status"] == "scheduled"
    assert resumed["next_run_at"]


def test_claim_and_finish_records_execution(tmp_path):
    registry = ScheduleRegistry(tmp_path)
    created = registry.create(schedule_payload(interval_s=1))
    claimed = registry.claim(created["id"])

    assert claimed["status"] == "running"
    final = registry.finish(created["id"], ok=True, receipt_id="receipt-1")
    assert final["status"] == "succeeded"
    assert final["run_count"] == 1
    assert final["last_receipt_id"] == "receipt-1"


def test_claim_due_advances_next_run_atomically(tmp_path):
    registry = ScheduleRegistry(tmp_path)
    created = registry.create(schedule_payload(interval_s=30))
    payload = registry._read()
    payload["schedules"][created["id"]]["next_run_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    registry._write(payload)

    claimed = registry.claim_due()
    assert [item["id"] for item in claimed] == [created["id"]]
    persisted = registry.get(created["id"])
    assert persisted["status"] == "running"
    assert datetime.fromisoformat(persisted["next_run_at"]) > datetime.now(timezone.utc)


def test_cron_uses_timezone_and_five_field_contract():
    after = datetime(2026, 1, 5, 8, 58, tzinfo=timezone.utc)
    next_run = next_cron_run("0 10 * * 1-5", "Europe/Madrid", after=after)

    assert next_run == datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc)


def test_delete_rejects_running_schedule(tmp_path):
    registry = ScheduleRegistry(tmp_path)
    created = registry.create(schedule_payload())
    registry.claim(created["id"])

    with pytest.raises(ScheduleError, match="ejecución"):
        registry.delete(created["id"])
