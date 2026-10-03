"""Isolated Layered Artifact Engine MVP for LAE-01..LAE-07.

This is a candidate reference implementation. It is deliberately independent
from BAGO runtime state and has no filesystem or subprocess authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
from typing import Any


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


@dataclass(frozen=True)
class CanonicalRoot:
    root_id: str
    content: dict[str, Any]
    root_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "root_digest", digest({"root_id": self.root_id, "content": self.content}))


@dataclass(frozen=True)
class Layer:
    layer_id: str
    artifact_id: str
    parent_id: str | None
    parent_digest: str
    operation: str
    payload: dict[str, Any]
    state: str = "PROPOSED"
    layer_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "layer_digest",
            digest(
                {
                    "layer_id": self.layer_id,
                    "artifact_id": self.artifact_id,
                    "parent_id": self.parent_id,
                    "parent_digest": self.parent_digest,
                    "operation": self.operation,
                    "payload": self.payload,
                }
            ),
        )


@dataclass(frozen=True)
class Snapshot:
    artifact_id: str
    head_id: str | None
    lineage: tuple[str, ...]
    content: dict[str, Any]
    snapshot_digest: str


@dataclass(frozen=True)
class Receipt:
    receipt_id: str
    operation: str
    artifact_id: str
    layer_id: str | None
    previous_head: str | None
    resulting_head: str | None
    resulting_snapshot_digest: str
    status: str
    reason: str | None = None


@dataclass
class ApplyResult:
    status: str
    layer_id: str | None
    receipt: Receipt | None = None


@dataclass
class Artifact:
    artifact_id: str
    root: CanonicalRoot
    layers: dict[str, Layer] = field(default_factory=dict)
    authorized: set[str] = field(default_factory=set)
    head_id: str | None = None
    snapshot: Snapshot | None = None
    receipts: list[Receipt] = field(default_factory=list)

    @property
    def head_digest(self) -> str:
        if self.head_id is None:
            return self.root.root_digest
        return self.layers[self.head_id].layer_digest

    def propose_layer(
        self,
        layer_id: str,
        operation: str,
        payload: dict[str, Any],
        *,
        parent_id: str | None = None,
        parent_digest: str | None = None,
    ) -> Layer:
        if layer_id in self.layers:
            raise ValueError(f"LAYER_ID_EXISTS:{layer_id}")
        if parent_id is None and parent_digest is None:
            parent_digest = self.root.root_digest if self.head_id is None else self.layers[self.head_id].layer_digest
            parent_id = self.head_id
        if parent_digest is None:
            parent_digest = self.root.root_digest if parent_id is None else self.layers[parent_id].layer_digest
        layer = Layer(layer_id, self.artifact_id, parent_id, parent_digest, operation, dict(payload))
        self.layers[layer_id] = layer
        return layer

    def authorize_layer(self, layer_id: str) -> None:
        if layer_id not in self.layers:
            raise KeyError(layer_id)
        self.authorized.add(layer_id)

    def _lineage(self, head_id: str | None = None) -> tuple[str, ...]:
        current = self.head_id if head_id is None else head_id
        chain: list[str] = [self.root.root_id]
        seen: set[str] = set()
        reverse: list[str] = []
        while current is not None:
            if current in seen:
                raise ValueError("LINEAGE_CYCLE")
            seen.add(current)
            layer = self.layers[current]
            reverse.append(layer.layer_id)
            current = layer.parent_id
        chain.extend(reversed(reverse))
        return tuple(chain)

    def _content_for(self, head_id: str | None) -> dict[str, Any]:
        content = dict(self.root.content)
        chain = self._lineage(head_id)[1:]
        for layer_id in chain:
            layer = self.layers[layer_id]
            if layer.operation not in {"ADD", "REPLACE"}:
                raise ValueError(f"UNSUPPORTED_OPERATION:{layer.operation}")
            content.update(layer.payload)
        return content

    def materialize_snapshot(self, head_id: str | None = None) -> Snapshot:
        selected = self.head_id if head_id is None else head_id
        content = self._content_for(selected)
        lineage = self._lineage(selected)
        snapshot_digest = digest({"artifact_id": self.artifact_id, "head_id": selected, "lineage": lineage, "content": content})
        return Snapshot(self.artifact_id, selected, lineage, content, snapshot_digest)

    def apply_layer(self, layer_id: str, *, simulate_failure: bool = False) -> ApplyResult:
        if self.head_id == layer_id:
            return ApplyResult("ALREADY_APPLIED", layer_id)
        layer = self.layers[layer_id]
        previous_head = self.head_id
        if layer_id not in self.authorized:
            return ApplyResult("NOT_AUTHORIZED", layer_id)
        if layer.parent_id != self.head_id or layer.parent_digest != self.head_digest:
            self.layers[layer_id] = replace(layer, state="STALE")
            return ApplyResult("STALE_PARENT", layer_id)
        if simulate_failure:
            receipt = self._receipt("APPLY_LAYER", layer_id, previous_head, previous_head, "FAILED", "SIMULATED_FAILURE")
            self.receipts.append(receipt)
            return ApplyResult("FAILED", layer_id, receipt)
        self.layers[layer_id] = replace(layer, state="APPLIED")
        self.head_id = layer_id
        self.snapshot = self.materialize_snapshot()
        receipt = self._receipt("APPLY_LAYER", layer_id, previous_head, self.head_id, "APPLIED")
        self.receipts.append(receipt)
        return ApplyResult("APPLIED", layer_id, receipt)

    def rebase(self, layer_id: str, new_layer_id: str) -> Layer:
        source = self.layers[layer_id]
        if new_layer_id in self.layers:
            raise ValueError(f"LAYER_ID_EXISTS:{new_layer_id}")
        return self.propose_layer(new_layer_id, source.operation, source.payload, parent_id=self.head_id, parent_digest=self.head_digest)

    def _receipt(self, operation: str, layer_id: str | None, previous: str | None, resulting: str | None, status: str, reason: str | None = None) -> Receipt:
        snapshot = self.snapshot.snapshot_digest if self.snapshot else self.materialize_snapshot(previous).snapshot_digest
        body = {"operation": operation, "artifact_id": self.artifact_id, "layer_id": layer_id, "previous_head": previous, "resulting_head": resulting, "snapshot": snapshot, "status": status, "reason": reason}
        return Receipt("sha256:" + digest(body), operation, self.artifact_id, layer_id, previous, resulting, snapshot, status, reason)


def create_artifact(artifact_id: str, root_id: str = "CANON", content: dict[str, Any] | None = None) -> Artifact:
    artifact = Artifact(artifact_id, CanonicalRoot(root_id, dict(content or {})))
    artifact.snapshot = artifact.materialize_snapshot()
    return artifact
