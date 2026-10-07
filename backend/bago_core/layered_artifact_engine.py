"""Small persistent LAE core exposed by the BAGO CLI.

The store is deliberately project-local and JSON based for the first runtime
slice. It owns lineage bookkeeping only; it does not authorize filesystem,
process, network, or external artifact effects.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Callable


def _bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


class LayerError(RuntimeError):
    pass


@dataclass(frozen=True)
class ApplyResult:
    status: str
    layer_id: str
    receipt: dict[str, Any] | None = None


class LayerStore:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "state.json"
        self.state = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {"artifacts": {}}

    def _save(self) -> None:
        temp = self.path.with_suffix(".tmp")
        temp.write_bytes(_bytes(self.state))
        temp.replace(self.path)

    def _artifact(self, artifact_id: str) -> dict[str, Any]:
        try:
            return self.state["artifacts"][artifact_id]
        except KeyError as exc:
            raise LayerError(f"ARTIFACT_NOT_FOUND:{artifact_id}") from exc

    @staticmethod
    def _root_digest(root_id: str, content: dict[str, Any]) -> str:
        return _digest({"root_id": root_id, "content": content})

    def init_artifact(self, artifact_id: str, root_id: str = "CANON", content: dict[str, Any] | None = None) -> dict[str, Any]:
        if artifact_id in self.state["artifacts"]:
            raise LayerError(f"ARTIFACT_EXISTS:{artifact_id}")
        content = dict(content or {})
        root_digest = self._root_digest(root_id, content)
        self.state["artifacts"][artifact_id] = {
            "artifact_id": artifact_id,
            "root_id": root_id,
            "root_content": content,
            "root_digest": root_digest,
            "head_id": None,
            "head_digest": root_digest,
            "layers": {},
            "authorized": [],
            "receipts": [],
        }
        self._save()
        return self._artifact(artifact_id)

    def propose(self, artifact_id: str, layer_id: str, operation: str, payload: dict[str, Any], parent_id: str | None = None, parent_digest: str | None = None) -> dict[str, Any]:
        artifact = self._artifact(artifact_id)
        if layer_id in artifact["layers"]:
            raise LayerError(f"LAYER_ID_EXISTS:{layer_id}")
        if parent_id is None:
            parent_id = artifact["head_id"]
        if parent_digest is None:
            parent_digest = artifact["head_digest"]
        layer = {
            "layer_id": layer_id,
            "artifact_id": artifact_id,
            "parent_id": parent_id,
            "parent_digest": parent_digest,
            "operation": operation,
            "payload": dict(payload),
            "state": "PROPOSED",
        }
        layer["layer_digest"] = _digest({k: layer[k] for k in ("layer_id", "artifact_id", "parent_id", "parent_digest", "operation", "payload")})
        artifact["layers"][layer_id] = layer
        self._save()
        return layer

    def authorize(self, artifact_id: str, layer_id: str) -> dict[str, Any]:
        artifact = self._artifact(artifact_id)
        if layer_id not in artifact["layers"]:
            raise LayerError(f"LAYER_NOT_FOUND:{layer_id}")
        if layer_id not in artifact["authorized"]:
            artifact["authorized"].append(layer_id)
        self._save()
        return artifact["layers"][layer_id]

    def _lineage(self, artifact: dict[str, Any], head_id: str | None = None) -> list[str]:
        current = artifact["head_id"] if head_id is None else head_id
        chain = [artifact["root_id"]]
        seen: set[str] = set()
        reverse: list[str] = []
        while current is not None:
            if current in seen:
                raise LayerError("LINEAGE_CYCLE")
            seen.add(current)
            layer = artifact["layers"].get(current)
            if layer is None:
                raise LayerError(f"PARENT_NOT_FOUND:{current}")
            reverse.append(current)
            current = layer["parent_id"]
        chain.extend(reversed(reverse))
        return chain

    def _snapshot(self, artifact: dict[str, Any], head_id: str | None) -> dict[str, Any]:
        content = dict(artifact["root_content"])
        lineage = self._lineage(artifact, head_id)
        for layer_id in lineage[1:]:
            layer = artifact["layers"][layer_id]
            if layer["operation"] not in {"ADD", "REPLACE"}:
                raise LayerError(f"UNSUPPORTED_OPERATION:{layer['operation']}")
            content.update(layer["payload"])
        snapshot = {"artifact_id": artifact["artifact_id"], "head_id": head_id, "lineage": lineage, "content": content}
        return {**snapshot, "snapshot_digest": _digest(snapshot)}

    def apply(self, artifact_id: str, layer_id: str) -> ApplyResult:
        artifact = self._artifact(artifact_id)
        layer = artifact["layers"].get(layer_id)
        if layer is None:
            raise LayerError(f"LAYER_NOT_FOUND:{layer_id}")
        if artifact["head_id"] == layer_id:
            return ApplyResult("ALREADY_APPLIED", layer_id)
        if layer_id not in artifact["authorized"]:
            return ApplyResult("NOT_AUTHORIZED", layer_id)
        if layer["parent_id"] != artifact["head_id"] or layer["parent_digest"] != artifact["head_digest"]:
            layer["state"] = "STALE"
            self._save()
            return ApplyResult("STALE_PARENT", layer_id)
        previous = artifact["head_id"]
        layer["state"] = "APPLIED"
        artifact["head_id"] = layer_id
        artifact["head_digest"] = layer["layer_digest"]
        snapshot = self._snapshot(artifact, layer_id)
        receipt_body = {"operation": "APPLY_LAYER", "artifact_id": artifact_id, "layer_id": layer_id, "previous_head": previous, "resulting_head": layer_id, "snapshot_digest": snapshot["snapshot_digest"], "status": "APPLIED"}
        receipt = {**receipt_body, "receipt_id": "sha256:" + _digest(receipt_body)}
        artifact["receipts"].append(receipt)
        self._save()
        return ApplyResult("APPLIED", layer_id, receipt)

    def rebase(self, artifact_id: str, source_id: str, new_layer_id: str) -> dict[str, Any]:
        artifact = self._artifact(artifact_id)
        source = artifact["layers"].get(source_id)
        if source is None:
            raise LayerError(f"LAYER_NOT_FOUND:{source_id}")
        return self.propose(artifact_id, new_layer_id, source["operation"], source["payload"], artifact["head_id"], artifact["head_digest"])

    def show(self, artifact_id: str) -> dict[str, Any]:
        return self._artifact(artifact_id)

    def project(self, artifact_id: str, target: str, expected_head_digest: str, *, allow_write: bool = False, writer: Callable[[Path, str], Any] | None = None) -> dict[str, Any]:
        """Materialize a JSON projection under the controlled candidate root.

        The target is never an arbitrary filesystem path: it must remain under
        ``.bago/layers/projections``. Writing additionally requires the caller
        to pass the explicit ``allow_write`` capability.
        """
        artifact = self._artifact(artifact_id)
        if expected_head_digest != artifact["head_digest"]:
            return {"status": "STALE_PARENT", "artifact_id": artifact_id, "head_digest": artifact["head_digest"]}
        relative = Path(target)
        if relative.is_absolute() or ".." in relative.parts:
            raise LayerError("PROJECTION_TARGET_OUT_OF_SCOPE")
        projection_root = (self.root / "projections").resolve()
        output = (projection_root / relative).resolve()
        try:
            output.relative_to(projection_root)
        except ValueError as exc:
            raise LayerError("PROJECTION_TARGET_OUT_OF_SCOPE") from exc
        snapshot = self._snapshot(artifact, artifact["head_id"])
        if not allow_write:
            return {"status": "PREVIEW", "target": str(output), "snapshot": snapshot}
        if writer is None:
            raise LayerError("PROJECTION_WRITE_REQUIRES_GATEWAY")
        serialized = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        writer(output, serialized)
        receipt_body = {"operation": "EXPORT_PROJECTION", "artifact_id": artifact_id, "target": str(output), "head_id": artifact["head_id"], "snapshot_digest": snapshot["snapshot_digest"], "status": "APPLIED"}
        receipt = {**receipt_body, "receipt_id": "sha256:" + _digest(receipt_body)}
        artifact["receipts"].append(receipt)
        self._save()
        return {"status": "APPLIED", "target": str(output), "snapshot": snapshot, "receipt": receipt}
