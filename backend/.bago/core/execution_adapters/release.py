"""Server-owned release download adapter."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.request import Request

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest
from execution_adapters.network import NetworkReadEffectAdapter


def _gateway_urlopen(*args: Any, **kwargs: Any) -> Any:
    from bago_core.server_effects import gateway_urlopen

    return gateway_urlopen(*args, **kwargs)


class ReleaseDownloadEffectAdapter:
    """Fetch and verify one fixed-name BAGO release bundle under server state."""

    effect_ids = frozenset({"release.download"})
    server_policy_only = True
    _FILENAME_RE = re.compile(
        r"^bago-v?\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?-distribution\.zip$"
    )
    _JOB_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
    _MAX_SIZE = 2 * 1024 * 1024 * 1024

    @classmethod
    def _target(cls, filename: str, job_id: str = "") -> tuple[Path, Path]:
        if Path(filename).name != filename or filename in {".", ".."}:
            raise ExecutionGatewayError(
                "Release bundle filename is not canonical",
                code="release_download_filename_invalid",
            )
        if job_id:
            if not cls._JOB_FILENAME_RE.fullmatch(filename):
                raise ExecutionGatewayError("Release job asset filename is invalid", code="release_download_filename_invalid")
            from release_job_paths import release_job_cache_directory

            try:
                root = release_job_cache_directory(job_id)
            except ValueError as exc:
                raise ExecutionGatewayError(str(exc), code="release_download_job_id_invalid") from exc
            target = root / filename
            partial = target.with_suffix(target.suffix + ".part")
            if target.is_symlink() or partial.is_symlink():
                raise ExecutionGatewayError("Release job asset cannot be a symlink", code="release_download_symlink_forbidden")
            return root, target
        if not cls._FILENAME_RE.fullmatch(filename):
            raise ExecutionGatewayError(
                "Release bundle filename is not canonical",
                code="release_download_filename_invalid",
            )
        from update_manager import _update_root

        root = Path(_update_root()).expanduser().resolve()
        target = root / filename
        partial = target.with_suffix(target.suffix + ".part")
        if target.is_symlink() or partial.is_symlink():
            raise ExecutionGatewayError(
                "Release bundle target cannot be a symlink",
                code="release_download_symlink_forbidden",
            )
        return root, target

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict) or authorization.get("kind") != "server_policy":
            raise ExecutionGatewayError(
                "Release download requires server-owned policy authorization",
                code="release_download_authorization_required",
            )

        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        url = str(arguments.get("url") or "").strip()
        filename = str(request.target.get("filename") or "").strip()
        expected = str(arguments.get("digest") or "").lower()
        expected_size = int(arguments.get("size") or 0)
        job_id = str(request.target.get("job_id") or "").strip()
        asset_kind = str(request.target.get("asset_kind") or "bundle").strip().lower()
        resume = bool(request.target.get("resume"))

        # Complete all request, host and path checks before touching the cache
        # or opening the network connection.
        NetworkReadEffectAdapter.validate_release_download_url(url)
        if (expected and not re.fullmatch(r"[a-f0-9]{64}", expected)) or (not expected and not job_id):
            raise ExecutionGatewayError(
                "Release bundle requires a verified SHA-256 digest",
                code="release_download_digest_invalid",
            )
        if job_id and asset_kind not in {"bundle", "checksum", "signature"}:
            raise ExecutionGatewayError("Release asset kind is invalid", code="release_download_asset_kind_invalid")
        if expected_size <= 0 or expected_size > self._MAX_SIZE:
            raise ExecutionGatewayError(
                "Release bundle size is outside the accepted limit",
                code="release_download_size_invalid",
            )
        root, destination = self._target(filename, job_id)
        partial = destination.with_suffix(destination.suffix + ".part")

        if not job_id:
            from update_manager import _set_state
        else:
            _set_state = None

        digest = hashlib.sha256()
        transferred = partial.stat().st_size if resume and partial.exists() else 0
        if transferred >= expected_size:
            partial.unlink(missing_ok=True)
            transferred = 0
        elif transferred:
            with partial.open("rb") as previous:
                for chunk in iter(lambda: previous.read(1024 * 1024), b""):
                    digest.update(chunk)
        last_report = 0.0
        try:
            if job_id and self._job_cancel_requested(job_id):
                raise ExecutionGatewayError("Release asset download cancelled", code="release_download_cancelled")
            if not transferred:
                partial.unlink(missing_ok=True)
            headers = {"Range": f"bytes={transferred}-"} if transferred else {}
            with _gateway_urlopen(
                Request(url, headers=headers),
                timeout=60,
                network_class="release_asset_download",
            ) as response:
                append = False
                start = 0
                content_length = int(response.headers.get("Content-Length") or 0)
                total = expected_size
                if transferred and response.status == 206:
                    content_range = str(response.headers.get("Content-Range") or "")
                    match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", content_range)
                    if (
                        not match
                        or int(match.group(1)) != transferred
                        or int(match.group(2)) < transferred
                        or int(match.group(2)) != expected_size - 1
                        or int(match.group(3)) != expected_size
                        or (content_length and content_length != int(match.group(2)) - transferred + 1)
                    ):
                        raise ExecutionGatewayError("Release server returned an invalid byte range", code="release_download_range_invalid")
                    append = True
                    start = transferred
                    total = int(match.group(3))
                elif response.status not in {200, 206}:
                    raise ExecutionGatewayError(f"Release download returned HTTP {response.status}", code="release_download_http_failed")
                elif response.status == 206:
                    content_range = str(response.headers.get("Content-Range") or "")
                    match = re.fullmatch(r"bytes 0-(\d+)/(\d+)", content_range)
                    if (
                        not match
                        or int(match.group(1)) != expected_size - 1
                        or int(match.group(2)) != expected_size
                        or (content_length and content_length != int(match.group(1)) + 1)
                    ):
                        raise ExecutionGatewayError("Release server returned an invalid byte range", code="release_download_range_invalid")
                    total = int(match.group(2))
                elif content_length:
                    total = content_length
                if not append and transferred:
                    digest = hashlib.sha256()
                    transferred = 0
                root.mkdir(parents=True, exist_ok=True)
                with partial.open("ab" if append else "wb") as output:
                    while True:
                        if job_id and self._job_cancel_requested(job_id):
                            raise ExecutionGatewayError("Release asset download cancelled", code="release_download_cancelled")
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        digest.update(chunk)
                        transferred += len(chunk)
                        if transferred > expected_size:
                            raise ExecutionGatewayError(
                                "Release bundle exceeds its published size",
                                code="release_download_size_exceeded",
                            )
                        now = time.monotonic()
                        if _set_state and now - last_report >= 0.2:
                            percent = min(99, int(transferred * 100 / total)) if total else 0
                            _set_state(status="downloading", phase="download", message="Descargando actualización…", total=total, transferred=transferred, percent=percent)
                            last_report = now

            if transferred != expected_size:
                raise ExecutionGatewayError(
                    "Release bundle size does not match its published size",
                    code="release_download_size_mismatch",
                )
            actual = digest.hexdigest().lower()
            if expected and actual != expected:
                raise ExecutionGatewayError(
                    "SHA-256 no coincide; la actualización se ha descartado.",
                    code="release_download_digest_mismatch",
                )
            os.replace(partial, destination)
        except Exception as exc:
            if not (job_id and getattr(exc, "code", "") == "release_download_cancelled"):
                partial.unlink(missing_ok=True)
            raise

        return {
            "ok": True,
            "executed": True,
            "effect_id": request.effect_id,
            "path": str(destination),
            "sha256": actual,
            "bytes_written": transferred,
            "receipt_id": f"release-download:{job_id or 'update'}:sha256:{actual}",
        }

    @staticmethod
    def _job_cancel_requested(job_id: str) -> bool:
        from release_job_paths import release_job_file

        try:
            state = json.loads(release_job_file(job_id, "jobs", ".json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            return False
        except (OSError, ValueError, TypeError) as exc:
            raise ExecutionGatewayError(f"Could not read release job cancellation state: {exc}", code="release_download_cancel_state_failed") from exc
        return bool(state.get("cancel_requested")) if isinstance(state, dict) else False
