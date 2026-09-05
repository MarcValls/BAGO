from __future__ import annotations

import json
from pathlib import Path

import bago_core.atomic_json as atomic_json
from bago_core.atomic_json import append_text_durable, read_json, write_json_atomic, write_text_atomic


def test_atomic_json_replaces_existing_document_without_temp_files(tmp_path: Path) -> None:
    target = tmp_path / "state" / "record.json"
    write_json_atomic(target, {"version": 1})
    write_json_atomic(target, {"version": 2, "label": "actual"})

    assert json.loads(target.read_text(encoding="utf-8")) == {"version": 2, "label": "actual"}
    assert list(target.parent.glob("*.tmp")) == []


def test_read_json_returns_default_for_corrupt_document(tmp_path: Path) -> None:
    target = tmp_path / "broken.json"
    target.write_text("{", encoding="utf-8")
    assert read_json(target, {"safe": True}) == {"safe": True}


def test_atomic_text_replace_and_durable_append(tmp_path: Path) -> None:
    target = tmp_path / "session" / "context.jsonl"
    write_text_atomic(target, '{"id":1}\n')
    append_text_durable(target, '{"id":2}\n')
    assert target.read_text(encoding="utf-8").splitlines() == ['{"id":1}', '{"id":2}']
    assert list(target.parent.glob("*.tmp")) == []


def test_atomic_replace_retries_transient_windows_permission_error(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    original_replace = atomic_json.os.replace
    attempts = []

    def transient_replace(source, destination):
        attempts.append((source, destination))
        if len(attempts) < 3:
            raise PermissionError(13, "sharing violation")
        return original_replace(source, destination)

    monkeypatch.setattr(atomic_json.os, "name", "nt", raising=False)
    monkeypatch.setattr(atomic_json.os, "replace", transient_replace)
    monkeypatch.setattr(atomic_json.time, "sleep", lambda _delay: None)

    write_json_atomic(target, {"recovered": True})

    assert len(attempts) == 3
    assert read_json(target) == {"recovered": True}
    assert not list(tmp_path.glob("*.tmp"))
