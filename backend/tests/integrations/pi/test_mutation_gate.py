"""Tests del mutation_gate."""
from __future__ import annotations

import pytest

from integrations.pi.errors import MutationPhaseLocked
from integrations.pi.mutation_gate import MutationDenial, deny, raise_if_mutated


def test_deny_default_denial() -> None:
    decision = deny()
    assert decision.decision == "DENY"
    assert decision.reason_code == "PI_MUTATION_PHASE_LOCKED"
    assert decision.mutation_receipt == "not_issued"
    assert decision.execution_continuation == "cancel"


def test_deny_with_details() -> None:
    decision = deny({"operation": "write", "target": "/etc/passwd"})
    assert decision.details == {"operation": "write", "target": "/etc/passwd"}


def test_denial_to_dict() -> None:
    data = deny().to_dict()
    assert data["decision"] == "DENY"
    assert data["reason_code"] == "PI_MUTATION_PHASE_LOCKED"


def test_raise_if_mutated_blocks_writes() -> None:
    with pytest.raises(MutationPhaseLocked):
        raise_if_mutated("file.write", {"path": "/x"})


def test_raise_if_mutated_blocks_edits() -> None:
    with pytest.raises(MutationPhaseLocked):
        raise_if_mutated("edit_file", {})


def test_raise_if_mutated_blocks_creates() -> None:
    with pytest.raises(MutationPhaseLocked):
        raise_if_mutated("create", {})


def test_raise_if_mutated_blocks_deletes() -> None:
    with pytest.raises(MutationPhaseLocked):
        raise_if_mutated("delete", {})


def test_raise_if_mutated_blocks_renames() -> None:
    with pytest.raises(MutationPhaseLocked):
        raise_if_mutated("rename_file", {})


def test_raise_if_mutated_blocks_patches() -> None:
    with pytest.raises(MutationPhaseLocked):
        raise_if_mutated("atomic_patch", {})


def test_raise_if_mutated_allows_reads() -> None:
    raise_if_mutated("file.read", {})


def test_raise_if_mutated_allows_listing() -> None:
    raise_if_mutated("file.ls", {})
