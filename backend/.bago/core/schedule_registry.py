"""Persistent schedule registry with interval and five-field cron support."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


_LOCK = threading.RLock()
VALID_TARGET_TYPES = {"task", "plan", "capability", "pipeline"}
VALID_SCHEDULE_TYPES = {"interval", "cron"}
VALID_STATUSES = {"scheduled", "paused", "running", "succeeded", "failed"}


class ScheduleError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid_schedule") -> None:
        super().__init__(message)
        self.code = code


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ScheduleError(f"Fecha inválida: {text}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except ZoneInfoNotFoundError as exc:
        raise ScheduleError(f"Zona horaria desconocida: {name}") from exc


def _cron_values(expression: str, minimum: int, maximum: int, *, sunday: bool = False) -> set[int]:
    values: set[int] = set()
    for part in expression.split(","):
        token = part.strip()
        if not token:
            raise ScheduleError("Campo cron vacío")
        step = 1
        if "/" in token:
            token, step_text = token.split("/", 1)
            try:
                step = int(step_text)
            except ValueError as exc:
                raise ScheduleError(f"Paso cron inválido: {step_text}") from exc
            if step < 1:
                raise ScheduleError("El paso cron debe ser mayor que cero")
        if token == "*":
            start, end = minimum, maximum
        elif "-" in token:
            start_text, end_text = token.split("-", 1)
            try:
                start, end = int(start_text), int(end_text)
            except ValueError as exc:
                raise ScheduleError(f"Rango cron inválido: {token}") from exc
        else:
            try:
                start = end = int(token)
            except ValueError as exc:
                raise ScheduleError(f"Valor cron inválido: {token}") from exc
        if sunday and start == 7:
            start = 0
        if sunday and end == 7:
            end = 0
        if start < minimum or start > maximum or end < minimum or end > maximum or start > end:
            raise ScheduleError(f"Valor cron fuera de rango: {part}")
        values.update(range(start, end + 1, step))
    return values


def next_cron_run(expression: str, timezone_name: str, *, after: datetime | None = None) -> datetime:
    fields = str(expression or "").split()
    if len(fields) != 5:
        raise ScheduleError("cron_expr debe contener minuto hora día mes día-semana")
    minute, hour, day, month, weekday = (
        _cron_values(fields[0], 0, 59),
        _cron_values(fields[1], 0, 23),
        _cron_values(fields[2], 1, 31),
        _cron_values(fields[3], 1, 12),
        _cron_values(fields[4], 0, 6, sunday=True),
    )
    zone = _timezone(timezone_name)
    cursor = (after or _utc_now()).astimezone(zone).replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = cursor + timedelta(days=366)
    while cursor <= limit:
        cron_weekday = (cursor.weekday() + 1) % 7
        if cursor.minute in minute and cursor.hour in hour and cursor.day in day and cursor.month in month and cron_weekday in weekday:
            return cursor.astimezone(timezone.utc)
        cursor += timedelta(minutes=1)
    raise ScheduleError("No se encontró una ejecución cron durante el próximo año")


def _next_run(record: dict[str, Any], *, after: datetime | None = None) -> datetime:
    current = after or _utc_now()
    if record["schedule_type"] == "interval":
        return current + timedelta(seconds=int(record["interval_s"]))
    return next_cron_run(record["cron_expr"], record["timezone"], after=current)


class ScheduleRegistry:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = Path(state_dir)
        self.path = self.state_dir / "schedules.json"

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": 1, "schedules": {}}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ScheduleError(f"No se pudo leer el registro de programación: {exc}", code="registry_invalid") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("schedules"), dict):
            raise ScheduleError("El registro de programación no es válido", code="registry_invalid")
        return payload

    def _write(self, payload: dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        payload["schema_version"] = 1
        payload["updated_at"] = _utc_now().isoformat()
        temporary = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def list(self) -> list[dict[str, Any]]:
        with _LOCK:
            schedules = self._read()["schedules"]
            return sorted((dict(item) for item in schedules.values()), key=lambda item: str(item.get("created_at", "")), reverse=True)

    def get(self, schedule_id: str) -> dict[str, Any]:
        with _LOCK:
            item = self._read()["schedules"].get(str(schedule_id))
            if not isinstance(item, dict):
                raise ScheduleError(f"Programación no encontrada: {schedule_id}", code="not_found")
            return dict(item)

    def create(self, raw: dict[str, Any]) -> dict[str, Any]:
        clean = self._validate(raw, creating=True)
        now = _utc_now()
        schedule_id = str(raw.get("id") or f"schedule-{uuid.uuid4().hex[:12]}").strip()
        if not schedule_id or "/" in schedule_id or "\\" in schedule_id:
            raise ScheduleError("id de programación inválido")
        record = {
            **clean,
            "id": schedule_id,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "last_run_at": "",
            "last_finished_at": "",
            "last_receipt_id": "",
            "run_count": 0,
            "error": "",
            "status": "scheduled" if clean["enabled"] else "paused",
        }
        record["next_run_at"] = _next_run(record, after=now).isoformat() if record["enabled"] else ""
        with _LOCK:
            payload = self._read()
            if schedule_id in payload["schedules"]:
                raise ScheduleError(f"Ya existe la programación {schedule_id}", code="conflict")
            payload["schedules"][schedule_id] = record
            self._write(payload)
        return dict(record)

    def update(self, schedule_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        with _LOCK:
            payload = self._read()
            current = payload["schedules"].get(schedule_id)
            if not isinstance(current, dict):
                raise ScheduleError(f"Programación no encontrada: {schedule_id}", code="not_found")
            clean = self._validate({**current, **patch}, creating=False)
            record = {**current, **clean, "updated_at": _utc_now().isoformat()}
            record["status"] = "scheduled" if record["enabled"] else "paused"
            record["next_run_at"] = _next_run(record).isoformat() if record["enabled"] else ""
            payload["schedules"][schedule_id] = record
            self._write(payload)
            return dict(record)

    def delete(self, schedule_id: str) -> dict[str, Any]:
        with _LOCK:
            payload = self._read()
            current = payload["schedules"].pop(schedule_id, None)
            if not isinstance(current, dict):
                raise ScheduleError(f"Programación no encontrada: {schedule_id}", code="not_found")
            if current.get("status") == "running":
                raise ScheduleError("No se puede eliminar una programación en ejecución", code="running")
            self._write(payload)
            return {"id": schedule_id, "deleted": True}

    def claim_due(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        instant = (now or _utc_now()).astimezone(timezone.utc)
        claimed: list[dict[str, Any]] = []
        with _LOCK:
            payload = self._read()
            changed = False
            for schedule_id, current in payload["schedules"].items():
                if not isinstance(current, dict) or not current.get("enabled") or current.get("status") == "running":
                    continue
                due = _parse_datetime(current.get("next_run_at"))
                if due is None or due > instant:
                    continue
                current["status"] = "running"
                current["last_run_at"] = instant.isoformat()
                current["next_run_at"] = _next_run(current, after=instant).isoformat()
                current["updated_at"] = instant.isoformat()
                claimed.append(dict(current))
                changed = True
            if changed:
                self._write(payload)
        return claimed

    def claim(self, schedule_id: str) -> dict[str, Any]:
        with _LOCK:
            payload = self._read()
            current = payload["schedules"].get(schedule_id)
            if not isinstance(current, dict):
                raise ScheduleError(f"Programación no encontrada: {schedule_id}", code="not_found")
            if current.get("status") == "running":
                raise ScheduleError("La programación ya está en ejecución", code="running")
            now = _utc_now()
            current["status"] = "running"
            current["last_run_at"] = now.isoformat()
            current["next_run_at"] = _next_run(current, after=now).isoformat() if current.get("enabled") else ""
            current["updated_at"] = now.isoformat()
            self._write(payload)
            return dict(current)

    def finish(self, schedule_id: str, *, ok: bool, receipt_id: str = "", error: str = "") -> dict[str, Any]:
        with _LOCK:
            payload = self._read()
            current = payload["schedules"].get(schedule_id)
            if not isinstance(current, dict):
                raise ScheduleError(f"Programación no encontrada: {schedule_id}", code="not_found")
            current["status"] = "succeeded" if ok else "failed"
            current["last_finished_at"] = _utc_now().isoformat()
            current["last_receipt_id"] = str(receipt_id or "")
            current["run_count"] = int(current.get("run_count", 0) or 0) + 1
            current["error"] = str(error or "")[:1000]
            current["updated_at"] = current["last_finished_at"]
            self._write(payload)
            return dict(current)

    def _validate(self, raw: dict[str, Any], *, creating: bool) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise ScheduleError("La programación debe ser un objeto")
        name = str(raw.get("name") or "").strip()
        if not name:
            raise ScheduleError("name es obligatorio")
        target_type = str(raw.get("target_type") or "task").strip()
        if target_type not in VALID_TARGET_TYPES:
            raise ScheduleError(f"target_type no soportado: {target_type}")
        target = raw.get("target")
        if not isinstance(target, dict) or not target:
            raise ScheduleError("target debe describir la tarea, plan, capacidad o pipeline")
        schedule_type = str(raw.get("schedule_type") or "interval").strip()
        if schedule_type not in VALID_SCHEDULE_TYPES:
            raise ScheduleError(f"schedule_type no soportado: {schedule_type}")
        interval_s = int(raw.get("interval_s") or 0)
        cron_expr = str(raw.get("cron_expr") or "").strip()
        timezone_name = str(raw.get("timezone") or "UTC").strip()
        _timezone(timezone_name)
        if schedule_type == "interval" and interval_s < 1:
            raise ScheduleError("interval_s debe ser mayor que cero")
        if schedule_type == "cron":
            next_cron_run(cron_expr, timezone_name)
        enabled = bool(raw.get("enabled", False))
        confirmed = bool(raw.get("confirmed", False))
        if enabled and not confirmed:
            raise ScheduleError("Activar una programación requiere confirmación explícita", code="confirmation_required")
        permissions = raw.get("approved_permissions", [])
        if not isinstance(permissions, list):
            raise ScheduleError("approved_permissions debe ser una lista")
        return {
            "name": name[:120],
            "description": str(raw.get("description") or "")[:500],
            "target_type": target_type,
            "target": target,
            "schedule_type": schedule_type,
            "interval_s": interval_s if schedule_type == "interval" else None,
            "cron_expr": cron_expr if schedule_type == "cron" else "",
            "timezone": timezone_name,
            "enabled": enabled,
            "confirmed": confirmed,
            "approved_permissions": sorted({str(item) for item in permissions if str(item)}),
            "overlap_policy": "skip",
            "misfire_policy": str(raw.get("misfire_policy") or "run_once"),
        }
