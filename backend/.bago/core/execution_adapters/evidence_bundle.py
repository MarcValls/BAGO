"""Strong CLI owner for evidence-bundle materialization and replacement."""
from __future__ import annotations

import hashlib
import os
import shutil
import stat
import uuid
from pathlib import Path
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest


class EvidenceBundleGenerateEffectAdapter:
    effect_ids = frozenset({"evidence.bundle.generate"})
    _MAX_FILES = 20_000
    _MAX_BYTES = 2 * 1024 * 1024 * 1024
    _FORBIDDEN = frozenset({".git", ".env", "node_modules", ".venv", "venv"})

    @classmethod
    def _target(cls, raw_path: str) -> Path:
        raw = str(raw_path or "").strip()
        path = Path(raw).expanduser()
        if not raw or not path.is_absolute():
            raise ExecutionGatewayError("Evidence bundle path must be absolute", code="evidence_bundle_path_invalid")
        path = Path(os.path.abspath(str(path)))
        if path == Path(path.anchor) or any(part.lower() in cls._FORBIDDEN for part in path.parts):
            raise ExecutionGatewayError("Evidence bundle path is not an allowed output", code="evidence_bundle_path_invalid")
        for component in (path, *path.parents):
            if not component.exists() and not component.is_symlink():
                continue
            try:
                metadata = component.lstat()
            except OSError as exc:
                raise ExecutionGatewayError("Evidence bundle path cannot be inspected", code="evidence_bundle_preflight_failed") from exc
            if component.is_symlink() or bool(getattr(metadata, "st_file_attributes", 0) & 0x400):
                raise ExecutionGatewayError("Evidence bundle output refuses linked path components", code="evidence_bundle_link_forbidden")
        return path

    @classmethod
    def target_fingerprint(cls, raw_path: str | Path) -> str:
        path = cls._target(str(raw_path))
        if not path.exists():
            return "missing"
        if not path.is_dir():
            raise ExecutionGatewayError("Evidence bundle target must be a directory", code="evidence_bundle_target_invalid")
        digest = hashlib.sha256()
        count = 0
        total = 0
        for item in sorted(path.rglob("*"), key=lambda entry: entry.relative_to(path).as_posix()):
            try:
                metadata = item.lstat()
            except OSError as exc:
                raise ExecutionGatewayError("Evidence bundle target changed during fingerprinting", code="evidence_bundle_preflight_failed") from exc
            if item.is_symlink() or bool(getattr(metadata, "st_file_attributes", 0) & 0x400):
                raise ExecutionGatewayError("Evidence bundle target contains a link", code="evidence_bundle_link_forbidden")
            relative = item.relative_to(path).as_posix().encode("utf-8")
            digest.update(b"D\0" if item.is_dir() else b"F\0")
            digest.update(relative + b"\0")
            if item.is_file():
                count += 1
                total += metadata.st_size
                if count > cls._MAX_FILES or total > cls._MAX_BYTES:
                    raise ExecutionGatewayError("Evidence bundle replacement target exceeds inspection limits", code="evidence_bundle_target_too_large")
                try:
                    with item.open("rb") as handle:
                        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                            digest.update(chunk)
                except OSError as exc:
                    raise ExecutionGatewayError("Evidence bundle target cannot be fingerprinted", code="evidence_bundle_preflight_failed") from exc
        return digest.hexdigest()

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        authorization = context.services.get("_authorization")
        proof = authorization.get("proof") if isinstance(authorization, dict) else None
        provenance = proof.get("provenance") if isinstance(proof, dict) else None
        if (
            not isinstance(authorization, dict)
            or authorization.get("state") != "consumed"
            or authorization.get("effect_id") != request.effect_id
            or authorization.get("operation_fingerprint") != request.fingerprint
            or not isinstance(proof, dict)
            or proof.get("effect_id") != request.effect_id
            or proof.get("operation_fingerprint") != request.fingerprint
            or proof.get("authenticated_session_id") != request.session_id
            or proof.get("user_decision") != "approve"
            or not isinstance(provenance, dict)
            or provenance.get("kind") != "direct_user_interaction"
            or provenance.get("channel") != "cli"
            or request.actor_kind != "user"
            or request.principal_id != "interactive-local-user"
            or request.source_surface != "cli.evidence_bundle.generate"
        ):
            raise ExecutionGatewayError("Evidence bundle requires its consumed direct CLI Permit", code="evidence_bundle_authorization_required")

        data = request.target if isinstance(request.target, dict) else {}
        args = request.arguments if isinstance(request.arguments, dict) else {}
        target = self._target(str(data.get("path") or ""))
        expected = str(data.get("expected_prior_sha256") or "")
        if expected not in {"missing"} and (len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected)):
            raise ExecutionGatewayError("Evidence bundle request lacks a valid prior identity", code="evidence_bundle_digest_required")
        if self.target_fingerprint(target) != expected:
            raise ExecutionGatewayError("Evidence bundle target changed after approval", code="evidence_bundle_target_changed")
        overwrite = args.get("overwrite") is True
        if target.exists() and not overwrite:
            raise ExecutionGatewayError("Evidence bundle output already exists", code="evidence_bundle_target_exists")
        if args.get("mode") not in {"simulated", "real"} or args.get("objective") not in {"community-knowledge", "code-quality", "release-readiness"}:
            raise ExecutionGatewayError("Evidence bundle options are invalid", code="evidence_bundle_options_invalid")
        if not all(isinstance(args.get(name), str) and len(args[name]) <= 512 for name in ("provider", "model", "base_path")):
            raise ExecutionGatewayError("Evidence bundle provider options are invalid", code="evidence_bundle_options_invalid")
        base_path = Path(str(args["base_path"])).expanduser()
        if not base_path.is_absolute() or not base_path.is_dir():
            raise ExecutionGatewayError("Evidence bundle base path must be an existing directory", code="evidence_bundle_base_path_invalid")

        target.parent.mkdir(parents=True, exist_ok=True)
        stage = target.with_name(f".{target.name}.bago-evidence-stage-{uuid.uuid4().hex}")
        backup = target.with_name(f".{target.name}.bago-evidence-backup-{uuid.uuid4().hex}")
        try:
            from bago_core.evidence_generator import _materialize_bundle

            manifest = _materialize_bundle(
                mode=str(args["mode"]), objective=str(args["objective"]), output_dir=stage,
                provider=str(args["provider"]), model=str(args["model"]),
                base_path=base_path, overwrite=False,
            )
            self._target(str(target))
            if self.target_fingerprint(target) != expected:
                raise ExecutionGatewayError("Evidence bundle target changed during generation", code="evidence_bundle_target_changed")
            if target.exists():
                if not overwrite:
                    raise ExecutionGatewayError("Evidence bundle output appeared during generation", code="evidence_bundle_target_exists")
                os.replace(target, backup)
            try:
                os.replace(stage, target)
            except OSError:
                if backup.exists() and not target.exists():
                    os.replace(backup, target)
                raise
        except ExecutionGatewayError:
            raise
        except Exception as exc:
            raise ExecutionGatewayError(f"Evidence bundle generation failed: {exc}", code="evidence_bundle_generate_failed") from exc
        finally:
            if stage.exists():
                shutil.rmtree(stage, ignore_errors=True)
        if backup.exists():
            shutil.rmtree(backup)
        final_manifest = target / Path(manifest).name
        try:
            final_digest = hashlib.sha256(final_manifest.read_bytes()).hexdigest()
        except OSError as exc:
            raise ExecutionGatewayError("Generated evidence manifest cannot be verified", code="evidence_bundle_receipt_failed") from exc
        return {
            "ok": True,
            "executed": True,
            "effect_id": request.effect_id,
            "path": str(target),
            "manifest_path": str(final_manifest),
            "manifest_sha256": final_digest,
            "receipt_id": f"evidence.bundle.generate:sha256:{final_digest}",
        }
