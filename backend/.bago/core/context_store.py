#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
context_store.py — BAGO Context Store

Persiste el contexto de conversación independientemente del provider.
Cada sesión tiene su propio directorio en .bago/state/sessions/<sid>/
con:
  - context.jsonl   : historial de mensajes (role, content, metadata)
  - timeline.jsonl  : eventos de la sesión
  - tokens.json     : contador de tokens por provider/modelo
  - meta.json       : metadatos de sesión (inicio, último provider, equivalencias usadas)

El ContextStore es el único sistema que debe tocarse al cambiar de provider.
Los adapters de LLM solo leen/escriben a través de él.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _read_current_version() -> str:
    root = Path(__file__).resolve().parents[2]
    for candidate in (
        root / "release_version.txt",
        root / ".bago" / "release_version.txt",
    ):
        try:
            value = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value:
            return value.lstrip("vV").strip()
    versions_path = root / "versions.json"
    try:
        data = json.loads(versions_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    current = data.get("current", "")
    return current.strip() if isinstance(current, str) else ""


try:
    from version import CURRENT as BAGO_VERSION
except Exception:
    BAGO_VERSION = _read_current_version()


class ContextMessage:
    """Mensaje normalizado del historial. Provider-agnostic."""

    def __init__(
        self,
        role: str,
        content: str,
        *,
        provider: str = "",
        model: str = "",
        timestamp: str = "",
        metadata: dict | None = None,
    ):
        self.role = role
        self.content = content
        self.provider = provider
        self.model = model
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "provider": self.provider,
            "model": self.model,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ContextMessage:
        return cls(
            role=d["role"],
            content=d["content"],
            provider=d.get("provider", ""),
            model=d.get("model", ""),
            timestamp=d.get("timestamp", ""),
            metadata=d.get("metadata", {}),
        )


class TimelineEvent:
    """Evento de la timeline de sesión."""

    def __init__(
        self,
        kind: str,
        title: str,
        detail: str = "",
        *,
        level: str = "info",
        timestamp: str = "",
    ):
        self.kind = kind
        self.title = title
        self.detail = detail
        self.level = level
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "title": self.title,
            "detail": self.detail,
            "level": self.level,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> TimelineEvent:
        return cls(
            kind=d["kind"],
            title=d["title"],
            detail=d.get("detail", ""),
            level=d.get("level", "info"),
            timestamp=d.get("timestamp", ""),
        )


class ContextStore:
    """
    Almacén de contexto de sesión. Thread-safe.

    Uso:
        store = ContextStore.create_new()   # nueva sesión
        store = ContextStore.load("<sid>")  # reanudar sesión
        store.append_message(ContextMessage("user", "hola"))
        store.append_response("¡Hola! Soy BAGO.", provider="copilot", model="gpt-5.4")
        history = store.get_history()       # lista de dicts para el LLM
        store.save()
    """

    _lock = threading.Lock()

    def __init__(self, sid: str, base_dir: Path):
        self.sid = sid
        self.base_dir = base_dir
        self.session_dir = base_dir / "sessions" / sid
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self._context_path = self.session_dir / "context.jsonl"
        self._timeline_path = self.session_dir / "timeline.jsonl"
        self._tokens_path = self.session_dir / "tokens.json"
        self._meta_path = self.session_dir / "meta.json"

        self._messages: list[ContextMessage] = []
        self._timeline: list[TimelineEvent] = []
        self._tokens: dict[str, dict[str, dict[str, int]]] = {}  # provider -> model -> {in, out, calls}
        self._meta: dict[str, Any] = {}

        self._load_all()

    # ── Factory methods ──────────────────────────────────────────────────────

    @classmethod
    def create_new(cls, base_dir: Path | None = None) -> ContextStore:
        sid = uuid.uuid4().hex[:16]
        base = base_dir or cls._resolve_base_dir()
        instance = cls(sid, base)
        now = datetime.now(timezone.utc).isoformat()
        instance._meta = {
            "created_at": now,
            "last_provider": "",
            "last_model": "",
            "switch_count": 0,
            "bago_version": BAGO_VERSION,
            "backend_clock_started_at": now,
            "backend_clock_last_reset_at": now,
            "backend_clock_last_reason": "session_start",
            "backend_clock_last_message": "Session created",
            "backend_clock_ticks": 0,
        }
        instance._save_meta()
        instance.add_timeline_event(TimelineEvent("session", "start", f"Session {sid} created"))
        return instance

    @classmethod
    def load(cls, sid: str, base_dir: Path | None = None) -> ContextStore:
        base = base_dir or cls._resolve_base_dir()
        return cls(sid, base)

    @classmethod
    def list_sessions(cls, base_dir: Path | None = None) -> list[dict]:
        base = base_dir or cls._resolve_base_dir()
        sessions_dir = base / "sessions"
        if not sessions_dir.exists():
            return []
        result = []
        for d in sorted(sessions_dir.iterdir()):
            if d.is_dir():
                meta_path = d / "meta.json"
                meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
                result.append({
                    "sid": d.name,
                    "created_at": meta.get("created_at", ""),
                    "last_provider": meta.get("last_provider", ""),
                    "last_model": meta.get("last_model", ""),
                    "switch_count": meta.get("switch_count", 0),
                })
        return result

    # ── Public API: messages ─────────────────────────────────────────────────

    def append_message(self, msg: ContextMessage) -> None:
        with self._lock:
            self._messages.append(msg)
            self._append_jsonl(self._context_path, msg.to_dict())

    def append_user(self, content: str, provider: str = "", model: str = "", good: bool = False) -> None:
        self.append_message(ContextMessage("user", content, provider=provider, model=model, metadata={"good": good}))

    def append_response(self, content: str, provider: str = "", model: str = "", metadata: dict | None = None) -> None:
        meta = metadata or {}
        self.append_message(ContextMessage("assistant", content, provider=provider, model=model, metadata=meta))

    def mark_good(self, index: int = -1) -> bool:
        """Marca un mensaje del historial como 'good' (importante, no diluible)."""
        with self._lock:
            if not self._messages or abs(index) > len(self._messages):
                return False
            self._messages[index].metadata["good"] = True
            # Rewrite file
            self._context_path.write_text("", encoding="utf-8")
            for m in self._messages:
                self._append_jsonl(self._context_path, m.to_dict())
        self.add_timeline_event(TimelineEvent("session", "mark_good", f"Mensaje {index} marcado como good"))
        return True

    def get_history(self, limit: int | None = None) -> list[dict]:
        """Devuelve el historial como lista de dicts compatibles con cualquier LLM."""
        msgs = self._messages
        if limit:
            msgs = msgs[-limit:]
        return [m.to_dict() for m in msgs]

    def get_raw_messages(self) -> list[ContextMessage]:
        return list(self._messages)

    def get_history_for_provider(self, provider: str, model: str, *, max_tokens: int | None = None) -> list[dict]:
        """
        Devuelve historial filtrado/adaptado para un provider específico.
        Por ahora devuelve todo; en el futuro puede comprimir si excede max_tokens.
        """
        # Marcar metadatos de que este provider está accediendo
        self._meta["last_provider"] = provider
        self._meta["last_model"] = model
        self._save_meta()
        return self.get_history()

    def clear_history(self) -> None:
        with self._lock:
            self._messages = []
            self._context_path.write_text("", encoding="utf-8")
        self.add_timeline_event(TimelineEvent("session", "clear", "Historial limpiado"))

    # ── Public API: timeline ─────────────────────────────────────────────────

    def add_timeline_event(self, event: TimelineEvent) -> None:
        with self._lock:
            self._timeline.append(event)
            if len(self._timeline) > 500:
                self._timeline = self._timeline[-400:]
            self._append_jsonl(self._timeline_path, event.to_dict())

    def get_timeline(self, limit: int = 20) -> list[dict]:
        return [e.to_dict() for e in self._timeline[-limit:]]

    # ── Public API: tokens ─────────────────────────────────────────────────

    def record_tokens(self, provider: str, model: str, tokens_in: int, tokens_out: int) -> None:
        with self._lock:
            p = self._tokens.setdefault(provider, {})
            m = p.setdefault(model, {"in": 0, "out": 0, "calls": 0})
            m["in"] += max(0, tokens_in or 0)
            m["out"] += max(0, tokens_out or 0)
            m["calls"] += 1
            self._save_tokens()

    def get_token_summary(self) -> dict:
        return dict(self._tokens)

    # ── Public API: metadata ─────────────────────────────────────────────────

    def get_meta(self) -> dict:
        return dict(self._meta)

    def update_meta(self, patch: dict) -> None:
        with self._lock:
            self._meta.update(patch)
            self._save_meta()

    def record_switch(self, old_provider: str, old_model: str, new_provider: str, new_model: str, reason: str = "") -> None:
        with self._lock:
            self._meta["last_provider"] = new_provider
            self._meta["last_model"] = new_model
            self._meta["switch_count"] = self._meta.get("switch_count", 0) + 1
            self._save_meta()
        self.add_timeline_event(
            TimelineEvent(
                "switch",
                f"{old_provider}/{old_model} → {new_provider}/{new_model}",
                reason,
                level="info",
            )
        )

    def record_backend_event(
        self,
        kind: str,
        title: str,
        detail: str = "",
        *,
        reset_clock: bool = True,
        level: str = "info",
    ) -> dict[str, Any]:
        """Persist a backend activity event and optionally reset the clock."""
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "kind": kind,
            "title": title,
            "detail": detail,
            "timestamp": now,
            "reset_clock": bool(reset_clock),
        }
        with self._lock:
            if "backend_clock_started_at" not in self._meta:
                self._meta["backend_clock_started_at"] = now
            if reset_clock:
                self._meta["backend_clock_last_reset_at"] = now
                self._meta["backend_clock_last_reason"] = kind
                self._meta["backend_clock_last_message"] = detail or title or kind
                self._meta["backend_clock_ticks"] = int(self._meta.get("backend_clock_ticks", 0)) + 1
            self._save_meta()
        self.add_timeline_event(TimelineEvent(kind, title, detail, level=level, timestamp=now))
        return payload

    # ── Persistence helpers ───────────────────────────────────────────────────

    def _load_all(self) -> None:
        self._messages = self._load_jsonl(self._context_path, ContextMessage.from_dict)
        self._timeline = self._load_jsonl(self._timeline_path, TimelineEvent.from_dict)
        self._tokens = self._load_json(self._tokens_path, default={})
        self._meta = self._load_json(self._meta_path, default={})

    def _load_jsonl(self, path: Path, factory) -> list:
        items: list = []
        if not path.exists():
            return items
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(factory(json.loads(line)))
                except Exception:
                    pass
        return items

    def _append_jsonl(self, path: Path, obj: dict) -> None:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    def _load_json(self, path: Path, default: Any = None) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _save_tokens(self) -> None:
        self._tokens_path.write_text(json.dumps(self._tokens, indent=2, ensure_ascii=False), encoding="utf-8")

    def _save_meta(self) -> None:
        self._meta_path.write_text(json.dumps(self._meta, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _resolve_base_dir() -> Path:
        env = os.environ.get("BAGO_STATE_DIR") or os.environ.get("BAGO_ROOT")
        if env:
            return Path(env) / ".bago" / "state"
        # Detect from script location: <repo>/.bago/state
        here = Path(__file__).resolve()
        cand = here.parents[2] / "state"  # core -> .bago -> state
        if cand.exists() or (here.parents[2] / "pack.json").exists():
            return cand
        return Path.cwd() / ".bago" / "state"

    # ── Context compression / summarization (future) ────────────────────────

    def compress_history(self, target_messages: int = 20) -> None:
        """
        Si el historial es muy largo, comprime los mensajes antiguos en un resumen.
        Por ahora solo trunca conservando system + últimos N. En v4.1 se puede
        usar un modelo ligero para resumir.
        """
        with self._lock:
            if len(self._messages) <= target_messages:
                return
            # Keep system messages and last target_messages
            system_msgs = [m for m in self._messages if m.role == "system"]
            other_msgs = [m for m in self._messages if m.role != "system"]
            kept = system_msgs + other_msgs[-target_messages:]
            self._messages = kept
            # Rewrite file
            self._context_path.write_text("", encoding="utf-8")
            for m in self._messages:
                self._append_jsonl(self._context_path, m.to_dict())
        self.add_timeline_event(
            TimelineEvent("session", "compress", f"Historial comprimido a {len(self._messages)} mensajes")
        )


def _run_tests() -> int:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        store = ContextStore.create_new(base_dir=base)
        sid = store.sid
        assert store._meta.get("bago_version") == BAGO_VERSION

        store.append_user("Hola BAGO")
        store.append_response("¡Hola! Soy BAGO.", provider="copilot", model="gpt-5.4")
        store.record_tokens("copilot", "gpt-5.4", 12, 34)
        store.record_switch("copilot", "gpt-5.4", "ollama-local", "qwen2.5-coder:7b", "user requested local")

        history = store.get_history()
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
        assert history[1]["provider"] == "copilot"

        # Reload
        store2 = ContextStore.load(sid, base_dir=base)
        assert len(store2.get_history()) == 2
        assert store2.get_meta()["switch_count"] == 1
        assert store2.get_token_summary()["copilot"]["gpt-5.4"]["calls"] == 1

        print("context_store.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
