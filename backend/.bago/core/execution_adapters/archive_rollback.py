"""Strong CLI owner for restoring a named Program Files rollback archive."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest


class SystemInstallArchiveRollbackEffectAdapter:
    effect_ids = frozenset({"system.install.archive.rollback"})
    _BACKUP_NAME = re.compile(r"^bago-programfiles-backup-[A-Za-z0-9._-]+\.zip$", re.IGNORECASE)
    _MAX_ENTRIES = 50_000
    _MAX_UNPACKED = 8 * 1024 * 1024 * 1024
    _PRESERVED = (".bago/state", ".bago/logs", "state", "logs")

    @staticmethod
    def _file_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @classmethod
    def _path(cls, raw: str, *, allow_missing: bool = True) -> Path:
        value = str(raw or "").strip()
        path = Path(value).expanduser()
        if not value or not path.is_absolute():
            raise ExecutionGatewayError("Rollback paths must be absolute", code="archive_rollback_path_invalid")
        path = Path(os.path.abspath(str(path)))
        if path == Path(path.anchor):
            raise ExecutionGatewayError("Rollback refuses filesystem roots", code="archive_rollback_path_invalid")
        for component in (path, *path.parents):
            if not component.exists() and not component.is_symlink():
                continue
            try:
                info = component.lstat()
            except OSError as exc:
                raise ExecutionGatewayError("Rollback path cannot be inspected", code="archive_rollback_preflight_failed") from exc
            if component.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & 0x400):
                raise ExecutionGatewayError("Rollback refuses linked path components", code="archive_rollback_link_forbidden")
        if not allow_missing and not path.exists():
            raise ExecutionGatewayError("Rollback source does not exist", code="archive_rollback_source_missing")
        return path

    @classmethod
    def _tree_fingerprint(cls, root: Path) -> str:
        if not root.exists():
            return "missing"
        if not root.is_dir():
            raise ExecutionGatewayError("Rollback install target must be a directory", code="archive_rollback_target_invalid")
        digest = hashlib.sha256()
        count = 0
        total = 0
        for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix().casefold()):
            try:
                info = path.lstat()
            except OSError as exc:
                raise ExecutionGatewayError("Rollback target changed during inspection", code="archive_rollback_preflight_failed") from exc
            if path.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & 0x400):
                raise ExecutionGatewayError("Rollback refuses links in install tree", code="archive_rollback_link_forbidden")
            relative = path.relative_to(root).as_posix().encode("utf-8")
            digest.update((b"D\0" if path.is_dir() else b"F\0") + relative + b"\0")
            if path.is_file():
                count += 1
                total += info.st_size
                if count > cls._MAX_ENTRIES or total > cls._MAX_UNPACKED:
                    raise ExecutionGatewayError("Rollback target exceeds inspection limits", code="archive_rollback_target_too_large")
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
        return digest.hexdigest()

    @classmethod
    def prepare_target(
        cls, install_dir: str | Path, backup_root: str | Path, backup_zip: str | Path,
        *, restore_backed_up_state: bool,
    ) -> dict[str, Any]:
        install = cls._path(str(install_dir))
        backup_dir = cls._path(str(backup_root))
        archive = cls._path(str(backup_zip), allow_missing=False)
        try:
            backup_dir.relative_to(install)
        except ValueError:
            pass
        else:
            raise ExecutionGatewayError("Rollback backup root cannot be inside the install target", code="archive_rollback_backup_root_invalid")
        if not archive.is_file() or not cls._BACKUP_NAME.fullmatch(archive.name):
            raise ExecutionGatewayError("Rollback requires a named BAGO backup ZIP", code="archive_rollback_archive_invalid")
        try:
            archive.relative_to(backup_dir)
        except ValueError as exc:
            raise ExecutionGatewayError("Rollback ZIP must be inside the approved backup root", code="archive_rollback_archive_out_of_scope") from exc
        safety = backup_dir / f"bago-pre-rollback-safety-{uuid.uuid4().hex}.zip"
        return {
            "install_dir": str(install),
            "backup_root": str(backup_dir),
            "backup_zip": str(archive),
            "backup_sha256": cls._file_sha256(archive),
            "install_tree_sha256": cls._tree_fingerprint(install),
            "safety_zip": str(safety),
            "restore_backed_up_state": bool(restore_backed_up_state),
        }

    @classmethod
    def _safe_extract(cls, archive: Path, stage: Path) -> None:
        total = 0
        seen: set[str] = set()
        with zipfile.ZipFile(archive) as source:
            entries = source.infolist()
            if not entries or len(entries) > cls._MAX_ENTRIES:
                raise ExecutionGatewayError("Rollback archive entry count is invalid", code="archive_rollback_archive_invalid")
            for entry in entries:
                name = entry.filename
                posix = PurePosixPath(name)
                if not name or "\\" in name or posix.is_absolute() or any(part in {"", ".", ".."} for part in posix.parts) or (posix.parts and ":" in posix.parts[0]):
                    raise ExecutionGatewayError("Rollback archive contains an unsafe path", code="archive_rollback_archive_path_invalid")
                key = posix.as_posix().casefold()
                if key in seen:
                    raise ExecutionGatewayError("Rollback archive contains duplicate paths", code="archive_rollback_archive_duplicate")
                seen.add(key)
                mode = (entry.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode):
                    raise ExecutionGatewayError("Rollback archive contains a symbolic link", code="archive_rollback_archive_link_forbidden")
                file_kind = stat.S_IFMT(mode)
                if file_kind not in {0, stat.S_IFREG, stat.S_IFDIR}:
                    raise ExecutionGatewayError("Rollback archive contains a special file", code="archive_rollback_archive_invalid")
                total += int(entry.file_size)
                if total > cls._MAX_UNPACKED:
                    raise ExecutionGatewayError("Rollback archive expands beyond the size limit", code="archive_rollback_archive_too_large")
                destination = stage.joinpath(*posix.parts)
                try:
                    destination.resolve().relative_to(stage.resolve())
                except ValueError as exc:
                    raise ExecutionGatewayError("Rollback archive path escapes staging", code="archive_rollback_archive_path_invalid") from exc
                if entry.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with source.open(entry, "r") as src, destination.open("xb") as dst:
                        shutil.copyfileobj(src, dst, length=1024 * 1024)
                except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                    raise ExecutionGatewayError("Rollback archive extraction failed", code="archive_rollback_extract_failed") from exc

    @classmethod
    def _create_safety_archive(cls, install: Path, archive: Path) -> None:
        archive.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as output:
            for path in sorted(install.rglob("*"), key=lambda item: item.relative_to(install).as_posix()):
                if path.is_symlink():
                    raise ExecutionGatewayError("Rollback refuses links in current install tree", code="archive_rollback_link_forbidden")
                relative = path.relative_to(install).as_posix()
                if path.is_dir():
                    output.writestr(relative.rstrip("/") + "/", b"")
                elif path.is_file():
                    output.write(path, relative)

    @classmethod
    def _preserve_state(cls, install: Path, stage: Path) -> None:
        for relative in cls._PRESERVED:
            source = install / Path(relative)
            if not source.exists():
                continue
            destination = stage / Path(relative)
            if destination.is_dir():
                shutil.rmtree(destination)
            elif destination.exists():
                destination.unlink()
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        authorization = context.services.get("_authorization")
        proof = authorization.get("proof") if isinstance(authorization, dict) else None
        provenance = proof.get("provenance") if isinstance(proof, dict) else None
        if (
            not isinstance(authorization, dict) or authorization.get("state") != "consumed"
            or authorization.get("effect_id") != request.effect_id
            or authorization.get("operation_fingerprint") != request.fingerprint
            or not isinstance(proof, dict) or proof.get("effect_id") != request.effect_id
            or proof.get("operation_fingerprint") != request.fingerprint
            or proof.get("authenticated_session_id") != request.session_id
            or proof.get("user_decision") != "approve"
            or not isinstance(provenance, dict) or provenance.get("kind") != "direct_user_interaction"
            or provenance.get("channel") != "cli"
            or request.actor_kind != "user" or request.principal_id != "interactive-local-user"
            or request.source_surface != "cli.install.archive-rollback" or request.scope != "system"
        ):
            raise ExecutionGatewayError("Archive rollback requires its consumed strong CLI Permit", code="archive_rollback_authorization_required")

        target = request.target if isinstance(request.target, dict) else {}
        install = self._path(str(target.get("install_dir") or ""))
        backup_root = self._path(str(target.get("backup_root") or ""))
        archive = self._path(str(target.get("backup_zip") or ""), allow_missing=False)
        safety = self._path(str(target.get("safety_zip") or ""))
        if safety.parent != backup_root or safety.name != Path(str(target.get("safety_zip") or "")).name or not safety.name.startswith("bago-pre-rollback-safety-") or not safety.name.endswith(".zip"):
            raise ExecutionGatewayError("Safety archive path is invalid", code="archive_rollback_safety_path_invalid")
        try:
            relative_archive = archive.relative_to(backup_root)
        except ValueError as exc:
            raise ExecutionGatewayError("Rollback ZIP is outside its approved root", code="archive_rollback_archive_out_of_scope") from exc
        if not self._BACKUP_NAME.fullmatch(relative_archive.name):
            raise ExecutionGatewayError("Rollback requires a named BAGO backup ZIP", code="archive_rollback_archive_invalid")
        try:
            backup_digest = self._file_sha256(archive)
        except OSError as exc:
            raise ExecutionGatewayError("Rollback archive cannot be read", code="archive_rollback_preflight_failed") from exc
        if backup_digest != str(target.get("backup_sha256") or ""):
            raise ExecutionGatewayError("Rollback archive changed after approval", code="archive_rollback_archive_changed")
        approved_tree = str(target.get("install_tree_sha256") or "")
        if self._tree_fingerprint(install) != approved_tree:
            raise ExecutionGatewayError("Install tree changed after approval", code="archive_rollback_install_changed")
        if safety.exists():
            raise ExecutionGatewayError("Safety archive destination already exists", code="archive_rollback_safety_exists")

        restore_state = target.get("restore_backed_up_state") is True
        stage = install.with_name(f".{install.name}.bago-archive-stage-{uuid.uuid4().hex}")
        displaced = install.with_name(f".{install.name}.bago-archive-displaced-{uuid.uuid4().hex}")
        committed = False
        preserved_old_path = ""
        try:
            self._safe_extract(archive, stage)
            if self._file_sha256(archive) != str(target.get("backup_sha256") or ""):
                raise ExecutionGatewayError("Rollback archive changed during extraction", code="archive_rollback_archive_changed")
            if self._tree_fingerprint(install) != approved_tree:
                raise ExecutionGatewayError("Install tree changed during rollback preparation", code="archive_rollback_install_changed")
            if install.exists():
                if any(install.iterdir()):
                    self._create_safety_archive(install, safety)
                if not restore_state:
                    self._preserve_state(install, stage)
                if self._tree_fingerprint(install) != approved_tree:
                    raise ExecutionGatewayError("Install tree changed before rollback commit", code="archive_rollback_install_changed")
                os.replace(install, displaced)
            try:
                os.replace(stage, install)
            except OSError:
                if displaced.exists() and not install.exists():
                    os.replace(displaced, install)
                raise
            committed = True
            if displaced.exists():
                try:
                    shutil.rmtree(displaced)
                except OSError:
                    preserved_old_path = str(displaced)
        except ExecutionGatewayError:
            raise
        except Exception as exc:
            if displaced.exists() and not install.exists():
                os.replace(displaced, install)
            raise ExecutionGatewayError(f"Archive rollback failed: {exc}", code="archive_rollback_failed") from exc
        finally:
            if stage.exists():
                shutil.rmtree(stage, ignore_errors=True)
            if not committed and safety.exists():
                safety.unlink(missing_ok=True)
        installed_fingerprint = self._tree_fingerprint(install)
        return {
            "ok": True, "executed": True, "effect_id": request.effect_id,
            "restored_to": str(install), "backup_zip": str(archive),
            "safety_zip": str(safety) if safety.exists() else "",
            "preserved_old_install_path": preserved_old_path,
            "restored_backed_up_state": restore_state,
            "backup_sha256": backup_digest,
            "safety_zip_sha256": self._file_sha256(safety) if safety.exists() else "",
            "install_tree_sha256": installed_fingerprint,
            "receipt_id": f"system.install.archive.rollback:sha256:{installed_fingerprint}",
        }
