from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from schedule_registry import (
    SCHEDULE_SCHEMA_VERSION,
    ScheduleError,
    ScheduleRegistry,
    next_cron_run,
)


def schedule_payload(**overrides):
    payload = {
        "name": "Informe periódico",
        "target_type": "plan",
        "target": {"plan_id": "plan-1"},
        "schedule_type": "interval",
        "interval_s": 60,
        "timezone": "UTC",
        "enabled": True,
        "delegation_id": "delegation-1",
    }
    payload.update(overrides)
    return payload


def test_enabled_schedule_requires_delegation(tmp_path):
    registry = ScheduleRegistry(tmp_path)

    with pytest.raises(ScheduleError) as denied:
        registry.create(schedule_payload(delegation_id=""))
    assert denied.value.code == "delegation_required"


def test_interval_schedule_persists_and_can_pause_resume(tmp_path):
    registry = ScheduleRegistry(tmp_path)
    created = registry.create(schedule_payload())

    reloaded = ScheduleRegistry(tmp_path)
    assert reloaded.get(created["id"])["target"]["plan_id"] == "plan-1"

    paused = reloaded.update(created["id"], {"enabled": False})
    assert paused["status"] == "paused"
    assert paused["next_run_at"] == ""

    resumed = reloaded.update(created["id"], {"enabled": True})
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
    payload["schedules"][created["id"]]["next_run_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    ).isoformat()
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


def test_legacy_confirmation_and_permissions_are_not_authority(tmp_path):
    path = tmp_path / "schedules.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "schedules": {
                    "legacy-1": {
                        **schedule_payload(
                            id="legacy-1",
                            delegation_id="",
                            confirmed=True,
                            approved_permissions=["filesystem.write"],
                        ),
                        "created_at": "2026-09-20T10:00:00+00:00",
                        "updated_at": "2026-09-20T10:00:00+00:00",
                        "status": "scheduled",
                        "next_run_at": "2026-09-20T11:00:00+00:00",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    registry = ScheduleRegistry(tmp_path)
    migrated = registry.get("legacy-1")

    assert migrated["enabled"] is False
    assert migrated["status"] == "paused"
    assert migrated["next_run_at"] == ""
    assert migrated["legacy_authority_disabled"] is True
    assert "confirmed" not in migrated
    assert "approved_permissions" not in migrated

    assert registry.claim_due(now=datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)) == []


def test_client_legacy_authority_fields_are_never_persisted(tmp_path):
    registry = ScheduleRegistry(tmp_path)
    created = registry.create(
        schedule_payload(
            confirmed=True,
            approved_permissions=["filesystem.write", "process.execute"],
        )
    )

    assert "confirmed" not in created
    assert "approved_permissions" not in created

    persisted = json.loads((tmp_path / "schedules.json").read_text(encoding="utf-8"))
    assert persisted["schema_version"] == SCHEDULE_SCHEMA_VERSION
    raw = persisted["schedules"][created["id"]]
    assert "confirmed" not in raw
    assert "approved_permissions" not in raw


def test_manual_claim_without_delegation_fails_closed(tmp_path):
    path = tmp_path / "schedules.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": SCHEDULE_SCHEMA_VERSION,
                "schedules": {
                    "draft-1": {
                        **schedule_payload(
                            id="draft-1",
                            enabled=False,
                            delegation_id="",
                        ),
                        "created_at": "2026-09-20T10:00:00+00:00",
                        "updated_at": "2026-09-20T10:00:00+00:00",
                        "status": "paused",
                        "next_run_at": "",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    registry = ScheduleRegistry(tmp_path)

    with pytest.raises(ScheduleError) as denied:
        registry.claim("draft-1")
    assert denied.value.code == "delegation_required"
