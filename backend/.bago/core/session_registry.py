"""Índice canónico y puntero de la sesión activa de BAGO."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
ACTIVE_SESSION_FILE = "active-session.json"


def validate_session_id(session_id: str) -> str:
    value = str(session_id or "").strip()
    if not SESSION_ID_PATTERN.fullmatch(value):
        raise ValueError("session_id inválido")
    return value


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def active_session_id(state_root: str | Path) -> str:
    payload = _read_json(Path(state_root) / ACTIVE_SESSION_FILE)
    try:
        return validate_session_id(str(payload.get("session_id") or ""))
    except ValueError:
        return ""


def mark_active_session(manager: Any) -> None:
    now = datetime.now(timezone.utc).isoformat()
    state_root = Path(manager.state_root)
    state_root.mkdir(parents=True, exist_ok=True)
    manager.store.update_meta({"last_opened_at": now})
    manager.save()
    target = state_root / ACTIVE_SESSION_FILE
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps({
        "session_id": validate_session_id(manager.session_id),
        "updated_at": now,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)


def session_exists(state_root: str | Path, session_id: str) -> bool:
    sid = validate_session_id(session_id)
    sessions = Path(state_root) / "sessions"
    return (sessions / sid).is_dir() or (sessions / f"{sid}.json").is_file()


def session_archived(state_root: str | Path, session_id: str) -> bool:
    sid = validate_session_id(session_id)
    return bool(_read_json(Path(state_root) / "sessions" / sid / "meta.json").get("archived", False))


def update_session_meta(state_root: str | Path, session_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    sid = validate_session_id(session_id)
    meta_path = Path(state_root) / "sessions" / sid / "meta.json"
    if not meta_path.exists():
        raise ValueError(f"Sesión no encontrada: {sid}")
    meta = _read_json(meta_path)
    meta.update(patch)
    temporary = meta_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(meta_path)
    return meta


def rename_session(state_root: str | Path, session_id: str, title: str) -> dict[str, Any]:
    clean_title = " ".join(str(title or "").split()).strip()
    if not clean_title:
        raise ValueError("El nombre de la sesión no puede estar vacío")
    if len(clean_title) > 80:
        raise ValueError("El nombre de la sesión no puede superar 80 caracteres")
    if session_archived(state_root, session_id):
        raise ValueError("No se puede renombrar una sesión archivada")
    return update_session_meta(state_root, session_id, {
        "session_title": clean_title,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })


def archive_session(state_root: str | Path, session_id: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return update_session_meta(state_root, session_id, {
        "archived": True,
        "archived_at": now,
        "updated_at": now,
    })


def restore_session(state_root: str | Path, session_id: str) -> dict[str, Any]:
    if not session_archived(state_root, session_id):
        raise ValueError("La sesión no está archivada")
    now = datetime.now(timezone.utc).isoformat()
    return update_session_meta(state_root, session_id, {
        "archived": False,
        "restored_at": now,
        "updated_at": now,
    })


def restore_active_session(manager_class: Any, state_root: str | Path, *, base_path: str | None = None) -> Any | None:
    sid = active_session_id(state_root)
    if not sid or not session_exists(state_root, sid) or session_archived(state_root, sid):
        return None
    return manager_class.load(sid, base_path=base_path, state_root=str(state_root))


def _message_summary(path: Path) -> tuple[int, str, str, str]:
    count = 0
    first_user = ""
    preview = ""
    last_at = ""
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(item, dict):
                    continue
                count += 1
                content = str(item.get("content") or "").strip()
                if content:
                    preview = content[:120]
                    if not first_user and str(item.get("role") or "") == "user":
                        first_user = content[:80]
                last_at = str(item.get("timestamp") or last_at)
    except OSError:
        pass
    return count, first_user, preview, last_at


def list_session_summaries(
    state_root: str | Path,
    *,
    current_session_id: str = "",
    limit: int = 30,
    archived_only: bool = False,
) -> list[dict[str, Any]]:
    root = Path(state_root)
    sessions_root = root / "sessions"
    if not sessions_root.is_dir():
        return []
    active = current_session_id or active_session_id(root)
    summaries: list[dict[str, Any]] = []
    for session_dir in sessions_root.iterdir():
        if not session_dir.is_dir():
            continue
        try:
            sid = validate_session_id(session_dir.name)
        except ValueError:
            continue
        meta = _read_json(session_dir / "meta.json")
        is_archived = bool(meta.get("archived", False))
        if is_archived != archived_only:
            continue
        saved = _read_json(sessions_root / f"{sid}.json")
        message_count, first_user, preview, message_updated_at = _message_summary(session_dir / "context.jsonl")
        conversations = meta.get("conversations") if isinstance(meta.get("conversations"), dict) else {}
        conversation_count = max(len(conversations), int(saved.get("conversation_count", 0) or 0), 1)
        active_conversation = str(meta.get("active_conversation_id") or saved.get("active_conversation_id") or "main")
        active_meta = conversations.get(active_conversation) if isinstance(conversations.get(active_conversation), dict) else {}
        objective = str(saved.get("persistent_goal") or meta.get("persistent_goal") or "").strip()
        title = str(meta.get("session_title") or "").strip() or objective or str(active_meta.get("title") or "").strip()
        if not title or title in {"Principal", "Nueva conversación", "Conversación"}:
            title = first_user or preview or f"Sesión {sid}"
        project_root = str(saved.get("project_root") or meta.get("project_root") or saved.get("authorized_root") or "")
        updated_at = str(
            meta.get("last_opened_at")
            or active_meta.get("updated_at")
            or message_updated_at
            or meta.get("created_at")
            or saved.get("created_at")
            or ""
        )
        is_active = sid == active
        if not archived_only and not is_active and message_count == 0 and conversation_count <= 1 and not objective:
            continue
        summaries.append({
            "session_id": sid,
            "title": title[:80],
            "preview": preview,
            "created_at": str(meta.get("created_at") or saved.get("created_at") or ""),
            "updated_at": updated_at,
            "last_opened_at": str(meta.get("last_opened_at") or ""),
            "project_root": project_root,
            "workspace_name": Path(project_root).name if project_root else "",
            "provider": str(saved.get("provider") or meta.get("last_provider") or ""),
            "model": str(saved.get("model") or meta.get("last_model") or ""),
            "message_count": message_count,
            "conversation_count": conversation_count,
            "active_conversation_id": active_conversation,
            "active": is_active,
            "archived": is_archived,
            "archived_at": str(meta.get("archived_at") or ""),
        })
    summaries.sort(key=lambda item: (bool(item["active"]), str(item.get("updated_at") or "")), reverse=True)
    return summaries[:max(1, min(int(limit or 30), 100))]
