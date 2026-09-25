"""Gateway-owned context bundle attachment."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest, stable_digest


class ContextAttachEffectAdapter:
    """Copy a challenge-bound selection into one session context bundle."""

    effect_ids = frozenset({"workspace.context.attach"})
    _LOCKS_GUARD = threading.RLock()
    _LOCKS: dict[str, threading.RLock] = {}

    @staticmethod
    def _roots(manager: Any) -> tuple[str, Path, Path, Any]:
        session_id = str(getattr(manager, "session_id", "") or "")
        base_path = Path(str(getattr(manager, "base_path", "") or "")).expanduser().resolve(strict=True)
        context_raw = str(getattr(manager, "workspace_context_root", "") or "").strip()
        resolver = getattr(manager, "_resolve_context_selection", None)
        ignore = getattr(manager, "_mirror_ignore", None)
        if not session_id or not context_raw or not callable(resolver) or not callable(ignore):
            raise ExecutionGatewayError(
                "Context attachment identity or policy is unavailable",
                code="context_attach_policy_missing",
            )
        context_root = Path(context_raw).expanduser().resolve()
        if bool(getattr(manager, "workspace_mirror_ready", False)):
            mirror_root = Path(str(getattr(manager, "workspace_mirror_root", "") or "")).expanduser().resolve(strict=True)
            expected_context = mirror_root.parent / "context"
            if mirror_root.name != "workspace" or mirror_root.parent.name != session_id or context_root != expected_context.resolve():
                raise ExecutionGatewayError(
                    "Context destination differs from the canonical session mirror",
                    code="context_attach_destination_out_of_scope",
                )
        else:
            state_root = Path(str(getattr(manager, "workspace_state_root", "") or "")).expanduser().resolve()
            if context_root != (state_root / "context").resolve():
                raise ExecutionGatewayError(
                    "Context destination differs from the active workspace state root",
                    code="context_attach_destination_out_of_scope",
                )
        return session_id, base_path, context_root, resolver

    @classmethod
    def _snapshot(cls, manager: Any, paths: list[str]) -> tuple[str, Path, Path, list[Path], str]:
        session_id, base_path, context_root, resolver = cls._roots(manager)
        selected = list(resolver(paths))
        records: list[dict[str, Any]] = []
        ignore = getattr(manager, "_mirror_ignore")
        for source in selected:
            source = Path(source).resolve(strict=True)
            try:
                source.relative_to(base_path)
            except ValueError as exc:
                raise ExecutionGatewayError(
                    "Selected context source is outside the active session workspace",
                    code="context_attach_source_out_of_scope",
                ) from exc
            if source.is_symlink():
                raise ExecutionGatewayError(
                    "Selected context source cannot be a symlink",
                    code="context_attach_symlink_forbidden",
                )
            if source.is_file():
                entries = [source]
            elif source.is_dir():
                entries = []
                for current, directories, files in os.walk(source, topdown=True, followlinks=False):
                    excluded = set(ignore(current, [*directories, *files]))
                    directories[:] = [name for name in directories
                                      if name not in excluded and not (Path(current) / name).is_symlink()]
                    for name in sorted(files):
                        item = Path(current) / name
                        if name not in excluded and not item.is_symlink() and item.is_file():
                            entries.append(item)
            else:
                continue
            for item in sorted(entries, key=lambda value: str(value).casefold()):
                stat = item.stat()
                digest = hashlib.sha256()
                with item.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                records.append({
                    "path": item.relative_to(base_path).as_posix(),
                    "size": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                    "sha256": digest.hexdigest(),
                })
        selection = [
            {"path": source.relative_to(base_path).as_posix(),
             "kind": "directory" if source.is_dir() else "file"}
            for source in selected
        ]
        return session_id, base_path, context_root, selected, stable_digest({
            "selection": selection,
            "files": records,
        })

    @classmethod
    def prepare_operation(cls, manager: Any, paths: list[str]) -> tuple[Path, Path, list[Path], str]:
        _session_id, base_path, context_root, selected, digest = cls._snapshot(manager, paths)
        return base_path, context_root, selected, digest

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        manager = context.manager
        authorization = context.services.get("_authorization")
        if (
            manager is None
            or not isinstance(authorization, dict)
            or authorization.get("state") != "consumed"
            or authorization.get("effect_id") != request.effect_id
            or authorization.get("operation_fingerprint") != request.fingerprint
            or authorization.get("session_id") != request.session_id
        ):
            raise ExecutionGatewayError(
                "Context attachment requires its exact consumed Permit",
                code="context_attach_authorization_required",
            )
        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        paths = arguments.get("paths", [])
        if not isinstance(paths, list) or any(not isinstance(item, str) for item in paths):
            raise ExecutionGatewayError("Context paths must be a string list", code="context_attach_paths_invalid")
        session_id, base_path, context_root, selected, digest = self._snapshot(manager, paths)
        expected = (str(request.target.get("source_root") or ""),
                    str(request.target.get("context_root") or ""),
                    str(request.target.get("selection_digest") or ""),
                    request.target.get("selection"))
        actual = (str(base_path), str(context_root), digest, [str(path) for path in selected])
        if (session_id != request.session_id or expected != actual
                or request.target.get("resource") != "session_context"
                or request.target.get("operation") != "attach"):
            raise ExecutionGatewayError(
                "Context selection or destination changed after authorization",
                code="context_attach_target_changed",
            )
        with self._LOCKS_GUARD:
            lock = self._LOCKS.setdefault(session_id, threading.RLock())
        ignore = getattr(manager, "_mirror_ignore")
        bundle_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        bundle_root = context_root / bundle_name
        stage_root = context_root / f".attach-{request.fingerprint[:16]}.tmp"
        copied: list[str] = []
        with lock:
            _session2, base2, context2, selected2, digest2 = self._snapshot(manager, paths)
            if (str(base2), str(context2), digest2) != actual[:3] or selected2 != selected:
                raise ExecutionGatewayError(
                    "Context selection changed immediately before materialization",
                    code="context_attach_target_changed",
                )
            try:
                context_root.mkdir(parents=True, exist_ok=True)
                if stage_root.exists():
                    shutil.rmtree(stage_root)
                stage_root.mkdir()
                file_count = 0
                for source in selected:
                    relative = source.relative_to(base_path)
                    destination = stage_root / relative
                    if source.is_file():
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, destination)
                        copied.append(relative.as_posix())
                        file_count += 1
                    elif source.is_dir():
                        for current, directories, files in os.walk(source, topdown=True, followlinks=False):
                            excluded = set(ignore(current, [*directories, *files]))
                            directories[:] = [name for name in directories
                                              if name not in excluded and not (Path(current) / name).is_symlink()]
                            current_path = Path(current)
                            rel_dir = current_path.relative_to(source)
                            target_dir = destination / rel_dir
                            target_dir.mkdir(parents=True, exist_ok=True)
                            for name in sorted(files):
                                item = current_path / name
                                if name in excluded or item.is_symlink() or not item.is_file():
                                    continue
                                rel = item.relative_to(base_path)
                                target = stage_root / rel
                                target.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(item, target)
                                copied.append(rel.as_posix())
                                file_count += 1
                _session3, base3, context3, selected3, digest3 = self._snapshot(manager, paths)
                if (str(base3), str(context3), digest3) != actual[:3] or selected3 != selected:
                    raise ExecutionGatewayError(
                        "Context source changed while the bundle was copied",
                        code="context_attach_source_changed_during_copy",
                    )
                manifest = {
                    "session_id": session_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "work_root": str(base_path),
                    "context_root": str(context_root),
                    "bundle_root": str(bundle_root),
                    "requested_paths": paths,
                    "resolved_paths": [str(path) for path in selected],
                    "copied_paths": copied,
                    "copy_count": len(copied),
                    "file_count": file_count,
                    "mirror_ready": bool(getattr(manager, "workspace_mirror_ready", False)),
                }
                (stage_root / "manifest.json").write_text(
                    json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                os.replace(stage_root, bundle_root)
                store = getattr(manager, "store", None)
                update_meta = getattr(store, "update_meta", None)
                if callable(update_meta):
                    update_meta({
                        "last_context_bundle": manifest,
                        "workspace_context_root": str(context_root),
                    })
            except Exception as exc:
                if stage_root.exists():
                    shutil.rmtree(stage_root, ignore_errors=True)
                if isinstance(exc, ExecutionGatewayError):
                    raise
                raise ExecutionGatewayError(
                    f"Context bundle materialization failed: {exc}",
                    code="context_attach_failed",
                ) from exc
        return {
            "ok": True,
            "message": f"Contexto adjuntado en {bundle_root} ({len(copied)} rutas)",
            "data": manifest,
            "effect_id": request.effect_id,
            "receipt_id": f"context-attach:{session_id}:{request.fingerprint[:16]}",
        }
