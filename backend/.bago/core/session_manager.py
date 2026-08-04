#!/usr/bin/env python3
"""session_manager.py — BAGO Session Manager (slim core).

Orquesta todo el ciclo de vida de una sesión de chat:
- Carga/guarda contexto via ContextStore
- Mantiene el provider/modelo activo
- Coordina switches con SwitchEngine
- Expone la API que usa el REPL.

El SessionManager es la única puerta de entrada al core desde el chat.

Modularizado en:
- session_utils.py: constants, free functions
- session_context_mixin.py: prompt, RAG, BC policy, auto-evolve
- session_adapters_mixin.py: adapter lifecycle, providers, switch
- session_persistence_mixin.py: save/load, status, bago_mode, goal
- session_tools_mixin.py: tool approval, feedback, memory
- session_turn_mixin.py: send, stream, receipts, tool rounds, orchestration
"""
from __future__ import annotations

import os
import sys
import time
import json
import shutil
import tempfile
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from version import CURRENT as BAGO_VERSION
from context_store import ContextStore, TimelineEvent
from state_paths import resolve_state_root
from model_equivalence import EquivalenceMap
from message_adapter import MessageAdapter
from rl_engine import FeedbackCollector, PreferenceModel
from config_manager import ConfigManager
from credential_manager import CredentialManager
from script_registry import ScriptRegistry
from tool_registry import ToolRegistry
from plan_engine import PlanEngine
from agent_gateway import AgentGateway
from knowledge_base import KnowledgeBase
from embedding_store import EmbeddingStore
from context_envelope import ContextReceipt
from context_governance import (
    CanonCache,
    ClaimVerifier,
    ContextClassifier,
    ContextPlanner,
    ContextRanker,
    ContextSourceRouter,
    ContradictionDetector,
    TokenBudgeter,
)
from gabo_connector import GaboConnector
from guardrails import PathGuard, ToolLogger, ClaimValidator
from workspace_binding import resolve_framework_root, resolve_workspace_binding
from directory_context import DirectoryContextEngine
from provider_adapter import ProviderAdapter, ProviderResponse

from session_utils import (
    ADAPTER_REGISTRY,
    BAGO_MODES,
    normalize_bago_mode,
    normalize_bridges,
    format_rag_context,
)
from session_context_mixin import SessionContextMixin
from session_adapters_mixin import SessionAdaptersMixin
from session_persistence_mixin import SessionPersistenceMixin
from session_tools_mixin import SessionToolsMixin
from session_turn_mixin import SessionTurnMixin


SESSION_MIRROR_EXCLUDED_DIRS = {
    ".git",
    ".gabo",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    ".venv",
    "venv",
}

PROJECT_ROOT_MARKERS = (
    ".gabo",
    ".git",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
)

SYSTEM_ROOT = Path(os.environ.get("SystemRoot", r"C:\Windows")).expanduser().resolve()
PROGRAM_FILES_ROOT = Path(os.environ.get("ProgramFiles", r"C:\Program Files")).expanduser().resolve()
PROGRAM_FILES_X86_ROOT = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")).expanduser().resolve()

MAX_MIRROR_BYTES = 2 * 1024 * 1024 * 1024
MAX_MIRROR_FILES = 200_000
MAX_MIRROR_SCAN_SECONDS = 30.0


# CANON[SS-001]: SessionManager owns the authoritative chat/session state.
class SessionManager(
    SessionContextMixin,
    SessionAdaptersMixin,
    SessionPersistenceMixin,
    SessionToolsMixin,
    SessionTurnMixin,
):
    """Gestiona una sesión de chat multi-provider."""

    @staticmethod
    def _format_rag_context(fragments):
        return format_rag_context(fragments)

    @staticmethod
    def _mirror_session_root(session_id: str) -> Path:
        return Path(tempfile.gettempdir()) / "BAGO" / "sessions" / session_id

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _validate_project_root(project_root: Path, *, require_identity: bool = False) -> Path:
        """Resolve a project root and reject unsafe or unidentified locations."""
        expanded_root = project_root.expanduser()
        try:
            resolved_root = expanded_root.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise RuntimeError(f"No se puede resolver el proyecto: {project_root}. {exc}") from exc

        if not resolved_root.is_dir():
            raise RuntimeError(f"La ruta del proyecto no es un directorio: {resolved_root}.")

        home = Path.home().resolve()
        drive_root = Path(resolved_root.anchor).resolve() if resolved_root.anchor else None

        if resolved_root == home:
            raise RuntimeError(
                "BAGO no puede utilizar el perfil completo del usuario como proyecto: "
                f"{resolved_root}. Abre PowerShell dentro de un proyecto o workspace concreto."
            )

        if drive_root is not None and resolved_root == drive_root:
            raise RuntimeError(
                "BAGO no puede utilizar la raíz completa de la unidad como proyecto: "
                f"{resolved_root}."
            )

        protected_roots = (
            SYSTEM_ROOT,
            PROGRAM_FILES_ROOT,
            PROGRAM_FILES_X86_ROOT,
        )
        for protected_root in protected_roots:
            if protected_root and (
                resolved_root == protected_root
                or SessionManager._is_relative_to(resolved_root, protected_root)
            ):
                raise RuntimeError(
                    "BAGO no puede utilizar una ruta protegida del sistema como proyecto: "
                    f"{resolved_root}."
                )

        if require_identity and not any((resolved_root / marker).exists() for marker in PROJECT_ROOT_MARKERS):
            markers = ", ".join(PROJECT_ROOT_MARKERS)
            raise RuntimeError(
                "No se ha detectado un proyecto o workspace válido en "
                f"{resolved_root}. Marcadores aceptados: {markers}."
            )

        return Path(os.path.abspath(str(expanded_root)))

    @staticmethod
    def _workspace_stats(root: Path) -> dict[str, Any]:
        """Measure a workspace while pruning excluded directories and links."""
        try:
            root = root.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            return {"bytes": 0, "files": 0, "error": f"workspace unavailable: {exc}"}

        if not root.is_dir():
            return {"bytes": 0, "files": 0, "error": f"workspace is not a directory: {root}"}

        excluded = {name.casefold() for name in SESSION_MIRROR_EXCLUDED_DIRS}
        total = 0
        file_count = 0
        started_at = time.monotonic()

        def ignore_error(_error: OSError) -> None:
            return None

        for dirpath, dirnames, filenames in os.walk(
            root,
            topdown=True,
            followlinks=False,
            onerror=ignore_error,
        ):
            if time.monotonic() - started_at > MAX_MIRROR_SCAN_SECONDS:
                return {
                    "bytes": total,
                    "files": file_count,
                    "error": f"workspace scan timed out after {MAX_MIRROR_SCAN_SECONDS:g} seconds",
                }

            current_dir = Path(dirpath)
            allowed_dirs: list[str] = []
            for dirname in dirnames:
                candidate = current_dir / dirname
                if dirname.casefold() in excluded:
                    continue
                try:
                    if candidate.is_symlink():
                        continue
                except OSError:
                    continue
                allowed_dirs.append(dirname)
            dirnames[:] = allowed_dirs

            for filename in filenames:
                if time.monotonic() - started_at > MAX_MIRROR_SCAN_SECONDS:
                    return {
                        "bytes": total,
                        "files": file_count,
                        "error": f"workspace scan timed out after {MAX_MIRROR_SCAN_SECONDS:g} seconds",
                    }

                path = current_dir / filename
                try:
                    if path.is_symlink():
                        continue
                    total += path.stat().st_size
                    file_count += 1
                except (OSError, PermissionError):
                    continue

                if total > MAX_MIRROR_BYTES:
                    return {
                        "bytes": total,
                        "files": file_count,
                        "error": (
                            "workspace too large for session mirror: "
                            f"{total} bytes (limit {MAX_MIRROR_BYTES})"
                        ),
                    }
                if file_count > MAX_MIRROR_FILES:
                    return {
                        "bytes": total,
                        "files": file_count,
                        "error": (
                            "workspace has too many files for session mirror: "
                            f"{file_count} (limit {MAX_MIRROR_FILES})"
                        ),
                    }

        return {"bytes": total, "files": file_count, "error": ""}

    @classmethod
    def _workspace_size_bytes(cls, root: Path) -> int:
        return int(cls._workspace_stats(root)["bytes"])

    @staticmethod
    def _mirror_ignore(directory: str, names: list[str]) -> set[str]:
        excluded = {name.casefold() for name in SESSION_MIRROR_EXCLUDED_DIRS}
        ignored: set[str] = set()
        current_dir = Path(directory)
        for name in names:
            if name.casefold() in excluded:
                ignored.add(name)
                continue
            try:
                if (current_dir / name).is_symlink():
                    ignored.add(name)
            except OSError:
                ignored.add(name)
        return ignored

    def _prepare_session_mirror(self, project_root: Path) -> dict[str, Any]:
        session_root = self._mirror_session_root(self.session_id)
        mirror_root = session_root / "workspace"
        context_root = session_root / "context"
        mirror_enabled = os.environ.get("BAGO_SESSION_MIRROR", "1").strip().casefold()
        if mirror_enabled in {"0", "false", "no", "off"}:
            return {
                "ok": False,
                "mirror_root": project_root,
                "context_root": project_root / ".gabo" / "context",
                "session_root": session_root,
                "required_bytes": 0,
                "free_bytes": 0,
                "file_count": 0,
                "error": "session mirror disabled by BAGO_SESSION_MIRROR",
            }

        stats = self._workspace_stats(project_root)
        workspace_bytes = int(stats["bytes"])
        file_count = int(stats["files"])
        required_bytes = max(workspace_bytes * 2, 0)
        free_bytes = 0
        error = str(stats.get("error", ""))
        try:
            free_bytes = shutil.disk_usage(tempfile.gettempdir()).free
        except Exception as exc:
            if not error:
                error = str(exc)
        if not error and required_bytes and free_bytes < required_bytes:
            error = f"insufficient disk space: free={free_bytes} required={required_bytes}"
        if error:
            return {
                "ok": False,
                "mirror_root": project_root,
                "context_root": project_root / ".gabo" / "context",
                "session_root": session_root,
                "required_bytes": required_bytes,
                "free_bytes": free_bytes,
                "file_count": file_count,
                "error": error,
            }
        try:
            if session_root.exists():
                shutil.rmtree(session_root)
            mirror_root.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                project_root,
                mirror_root,
                ignore=self._mirror_ignore,
                symlinks=True,
            )
            context_root.mkdir(parents=True, exist_ok=True)
            return {
                "ok": True,
                "mirror_root": mirror_root,
                "context_root": context_root,
                "session_root": session_root,
                "required_bytes": required_bytes,
                "free_bytes": free_bytes,
                "file_count": file_count,
                "error": "",
            }
        except Exception as exc:
            return {
                "ok": False,
                "mirror_root": project_root,
                "context_root": project_root / ".gabo" / "context",
                "session_root": session_root,
                "required_bytes": required_bytes,
                "free_bytes": free_bytes,
                "file_count": file_count,
                "error": str(exc),
            }

    def __init__(
        self,
        session_id: str | None = None,
        provider: str = "ollama-cloud",
        model: str = "deepseek-v3.1:671b",
        base_path: str | None = None,
        state_root: str | None = None,
        system_prompt: str = "",
        bago_mode: str = "B",
        active_agent: str = "default",
        active_bridges: list[str] | None = None,
        require_project_identity: bool = False,
    ):
        self.session_id = session_id or str(uuid.uuid4())[:12]
        self.provider = provider
        self.model = model
        self.system_prompt = system_prompt
        self.bago_mode = normalize_bago_mode(bago_mode)
        self.active_bridges = normalize_bridges(active_bridges or [provider], primary=provider)
        self.base_path = self._validate_project_root(
            Path(base_path or os.getcwd()),
            require_identity=require_project_identity,
        )
        self.state_root = resolve_state_root(state_root)
        self.state_dir = self.state_root
        self.state_dir.mkdir(parents=True, exist_ok=True)
        # CANON[SS-002]: workspace binding comes from explicit project and workspace roots.
        self.framework_root = resolve_framework_root()
        self.project_root = self.base_path
        self.workspace_state_root = self.project_root / ".gabo"
        self.workspace_scope_root = self.project_root
        binding = resolve_workspace_binding(self.project_root)
        self.workspace_id = binding.workspace_id
        self.workspace_manifest = Path(binding.manifest_path)
        # CANON[SS-003]: keep the resolved binding as a projection, not a second authority.
        self.workspace_binding = binding.to_dict()
        mirror_info = self._prepare_session_mirror(self.project_root)
        self.workspace_mirror_root = Path(mirror_info["mirror_root"]).resolve()
        self.workspace_context_root = Path(mirror_info["context_root"]).resolve()
        self.workspace_mirror_ready = bool(mirror_info["ok"])
        self.workspace_mirror_error = str(mirror_info.get("error", ""))
        self.workspace_mirror_required_bytes = int(mirror_info.get("required_bytes", 0) or 0)
        self.workspace_mirror_free_bytes = int(mirror_info.get("free_bytes", 0) or 0)
        self.base_path = self.workspace_mirror_root if self.workspace_mirror_ready else self.project_root
        self.workspace_work_root = self.base_path

        self.config = ConfigManager(base_path=str(self.base_path), state_root=str(self.state_root))
        self.credentials = CredentialManager(base_path=str(self.base_path), state_root=str(self.state_root))

        self.store = ContextStore(self.session_id, base_dir=self.state_dir)
        if not self.store.get_meta():
            now = datetime.now(timezone.utc).isoformat()
            self.store.update_meta({
                "created_at": now,
                "last_provider": "",
                "last_model": "",
                "switch_count": 0,
                "bago_version": BAGO_VERSION,
                "framework_root": str(self.framework_root),
                "project_root": str(self.project_root),
                "workspace_state_root": str(self.workspace_state_root),
                "workspace_scope_root": str(self.workspace_scope_root),
                "workspace_mirror_root": str(self.workspace_mirror_root),
                "workspace_id": str(self.workspace_id),
                "backend_clock_started_at": now,
                "backend_clock_last_reset_at": now,
                "backend_clock_last_reason": "session_start",
                "backend_clock_last_message": "Session created",
                "backend_clock_ticks": 0,
            })
            self.store.add_timeline_event(TimelineEvent("session", "start", f"Session {self.session_id} created"))
        self.equiv = EquivalenceMap()
        self.msg_adapter = MessageAdapter()

        self.rl_pref = PreferenceModel(base_dir=self.base_path, state_root=self.state_root)
        self.rl_feedback = FeedbackCollector(self.rl_pref)
        self.script_registry = ScriptRegistry(repo_root=self.base_path, event_sink=self.store)
        self.dev_mode = os.environ.get("BAGO_DEV_MODE", "").strip() in ("1", "true", "TRUE", "yes", "YES")
        self.tool_registry = ToolRegistry(script_registry=self.script_registry, workspace_root=self.base_path, dev_mode=self.dev_mode)
        self.plan_engine = PlanEngine()
        self.agent_gateway = AgentGateway()
        self.agent_gateway.activate(active_agent)
        self.knowledge = KnowledgeBase(base_path=str(self.base_path), state_root=str(self.state_root))
        self.embedding_store = EmbeddingStore(base_path=str(self.base_path), state_root=str(self.state_root))
        self.context_classifier = ContextClassifier()
        self.context_planner = ContextPlanner()
        self.context_router = ContextSourceRouter()
        self.context_ranker = ContextRanker()
        self.context_contradictions = ContradictionDetector()
        self.claim_verifier = ClaimVerifier()
        self.token_budgeter = TokenBudgeter()
        self.canon_cache = CanonCache(self.base_path, self.workspace_context_root)
        self.last_code_task: dict[str, Any] | None = None
        self.last_code_task_contract: dict[str, Any] | None = None
        self.last_context_envelope = None
        self._adapter: ProviderAdapter | None = None
        self._init_info: dict = self._init_adapter()
        self.persistent_goal: str = ""
        self.last_receipt: ContextReceipt | None = None
        self.last_budget_report = None
        self.last_context_benchmark: dict[str, Any] | None = None
        self.last_cognitive_benchmark: dict[str, Any] | None = None
        self.last_context_certification: dict[str, Any] | None = None
        self._gabo: GaboConnector = GaboConnector(self.project_root)
        self.directory_context = DirectoryContextEngine(self.base_path, self.workspace_context_root)
        self.last_working_set: dict[str, Any] | None = None

        self.path_guard = PathGuard(dev_mode=self.dev_mode)
        tool_log_path = self.state_dir / "tool_log.jsonl"
        self.tool_logger = ToolLogger(log_path=str(tool_log_path))
        self.claim_validator = ClaimValidator()

        self.created_at = time.time()
        self.total_tokens = 0
        self.total_calls = 0
        self.last_switch_at: float | None = None
        self.switch_log: list[dict] = []

        self._pending_tools: list[dict] | None = None
        self._pending_normalized: list[dict] | None = None
        self._pending_user_message: str = ""
        self._pending_tools_kwargs: dict[str, Any] = {}
        self._providers_cache: list[dict[str, Any]] | None = None
        self._providers_cache_at = 0.0
        self._providers_cache_ttl = 30.0

    def rebind_project_root(self, new_project_root: str | Path) -> None:
        """Rebindea la sesión al proyecto activo sin perder el estado de chat."""
        project_root = self._validate_project_root(
            Path(new_project_root),
            require_identity=True,
        )

        def _close_safe(value: Any) -> None:
            try:
                if value:
                    value.close()
            except Exception:
                pass

        _close_safe(getattr(self, "knowledge", None))
        _close_safe(getattr(self, "embedding_store", None))

        self.project_root = project_root
        self.workspace_scope_root = project_root
        self.workspace_state_root = project_root / ".gabo"
        mirror_info = self._prepare_session_mirror(project_root)
        self.workspace_mirror_root = Path(mirror_info["mirror_root"]).resolve()
        self.workspace_context_root = Path(mirror_info["context_root"]).resolve()
        self.workspace_mirror_ready = bool(mirror_info["ok"])
        self.workspace_mirror_error = str(mirror_info.get("error", ""))
        self.workspace_mirror_required_bytes = int(mirror_info.get("required_bytes", 0) or 0)
        self.workspace_mirror_free_bytes = int(mirror_info.get("free_bytes", 0) or 0)
        self.base_path = self.workspace_mirror_root if self.workspace_mirror_ready else self.project_root
        self.workspace_work_root = self.base_path
        # CANON[SS-004]: rebinding updates project and workspace roots together.
        binding = resolve_workspace_binding(project_root)
        self.workspace_id = binding.workspace_id
        self.workspace_manifest = Path(binding.manifest_path)
        self.workspace_binding = binding.to_dict()

        self.config = ConfigManager(base_path=str(self.base_path), state_root=str(self.state_root))
        self.credentials = CredentialManager(base_path=str(self.base_path), state_root=str(self.state_root))
        self.script_registry = ScriptRegistry(repo_root=self.base_path, event_sink=self.store)
        self.dev_mode = os.environ.get("BAGO_DEV_MODE", "").strip() in ("1", "true", "TRUE", "yes", "YES")
        self.tool_registry = ToolRegistry(script_registry=self.script_registry, workspace_root=self.base_path, dev_mode=self.dev_mode)
        self.knowledge = KnowledgeBase(base_path=str(self.base_path), state_root=str(self.state_root))
        self.embedding_store = EmbeddingStore(base_path=str(self.base_path), state_root=str(self.state_root))
        self.context_classifier = ContextClassifier()
        self.context_planner = ContextPlanner()
        self.context_router = ContextSourceRouter()
        self.context_ranker = ContextRanker()
        self.context_contradictions = ContradictionDetector()
        self.claim_verifier = ClaimVerifier()
        self.token_budgeter = TokenBudgeter()
        self.canon_cache = CanonCache(self.base_path, self.workspace_context_root)
        self.path_guard = PathGuard(dev_mode=self.dev_mode)
        self._gabo = GaboConnector(self.project_root)
        self.directory_context = DirectoryContextEngine(self.base_path, self.workspace_context_root)
        self.last_working_set = None
        self._adapter = None
        self._init_info = self._init_adapter()
        self._providers_cache = None
        self._providers_cache_at = 0.0

        self.store.update_meta({
            "framework_root": str(self.framework_root),
            "project_root": str(self.project_root),
            "workspace_state_root": str(self.workspace_state_root),
            "workspace_scope_root": str(self.workspace_scope_root),
            "workspace_mirror_root": str(self.workspace_mirror_root),
            "workspace_id": str(self.workspace_id),
            # CANON[SS-005]: persist the rebinding so future sessions can restore it.
            "active_project_analysis": {
                "root": str(self.project_root),
                "configured": None,
                "linked": None,
                "stack": [],
                "issues": [],
                "suggestions": [],
                "source": "rebind",
            },
        })

    def record_project_analysis(self, data: dict[str, Any]) -> None:
        """Persist a compact project audit for the next model turn."""
        if not isinstance(data, dict):
            return
        summary = {
            "root": str(data.get("root") or data.get("project_root") or self.project_root),
            "configured": data.get("configured"),
            "linked": data.get("linked"),
            "link_mode": data.get("link_mode"),
            "stack": list(data.get("stack") or [])[:8],
            "issues": list(data.get("issues") or [])[:8],
            "suggestions": list(data.get("suggestions") or [])[:8],
            "source": "project_analysis",
        }
        self.store.update_meta({"active_project_analysis": summary})

    @staticmethod
    def _context_path_pattern() -> re.Pattern[str]:
        return re.compile(r"(?:[A-Za-z]:[\\/]|\.{1,2}[\\/]|/)[^\s'\"`<>|]+")

    def _recent_context_paths(self, limit: int = 8) -> list[str]:
        patterns = self._context_path_pattern()
        candidates: list[str] = []
        try:
            history = list(self.store.get_history())[-12:]
        except Exception:
            history = []
        for entry in reversed(history):
            text = " ".join(
                str(entry.get(field, ""))
                for field in ("content", "text", "message")
                if str(entry.get(field, "")).strip()
            ).strip()
            if not text:
                continue
            for match in patterns.findall(text):
                if match not in candidates:
                    candidates.append(match)
                if len(candidates) >= limit:
                    return candidates
        return candidates

    def _resolve_context_selection(self, paths: list[str] | None = None) -> list[Path]:
        work_root = Path(getattr(self, "base_path", self.project_root)).resolve()
        raw_items = [str(item).strip() for item in (paths or []) if str(item).strip()]
        if not raw_items:
            raw_items = self._recent_context_paths()
        resolved: list[Path] = []
        for raw in raw_items:
            candidate = Path(raw).expanduser()
            if not candidate.is_absolute():
                candidate = (work_root / candidate).resolve()
            else:
                candidate = candidate.resolve()
            try:
                candidate.relative_to(work_root)
            except Exception:
                continue
            if candidate.exists() and candidate not in resolved:
                resolved.append(candidate)
        return resolved

    def attach_context(self, paths: list[str] | None = None) -> dict[str, Any]:
        work_root = Path(getattr(self, "base_path", self.project_root)).resolve()
        context_root = Path(getattr(self, "workspace_context_root", self.workspace_state_root / "context")).resolve()
        context_root.mkdir(parents=True, exist_ok=True)
        selected = self._resolve_context_selection(paths)
        bundle_root = context_root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        bundle_root.mkdir(parents=True, exist_ok=True)
        copied: list[str] = []
        copied_files = 0
        for source in selected:
            rel = source.relative_to(work_root)
            target = bundle_root / rel
            if source.is_dir():
                shutil.copytree(
                    source,
                    target,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(*SESSION_MIRROR_EXCLUDED_DIRS),
                )
                copied.append(rel.as_posix())
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(rel.as_posix())
            copied_files += 1
        manifest = {
            "session_id": self.session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "work_root": str(work_root),
            "context_root": str(context_root),
            "bundle_root": str(bundle_root),
            "requested_paths": [str(item) for item in (paths or []) if str(item).strip()],
            "resolved_paths": [str(path) for path in selected],
            "copied_paths": copied,
            "copy_count": len(copied),
            "file_count": copied_files,
            "mirror_ready": bool(getattr(self, "workspace_mirror_ready", False)),
        }
        (bundle_root / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        self.store.update_meta({
            "last_context_bundle": manifest,
            "workspace_context_root": str(context_root),
        })
        return {
            "ok": True,
            "message": f"Contexto adjuntado en {bundle_root} ({len(copied)} rutas)",
            "data": manifest,
        }

    def sync_workspace_mirror(self) -> dict[str, Any]:
        src = Path(getattr(self, "base_path", self.project_root)).resolve()
        dst = Path(getattr(self, "project_root", self.base_path)).resolve()
        if src == dst:
            return {
                "ok": False,
                "blocked": True,
                "message": "No hay espejo activo para sincronizar.",
                "source_root": str(src),
                "target_root": str(dst),
            }
        copied: list[str] = []
        for path in sorted(src.rglob("*"), key=lambda item: str(item).lower()):
            try:
                rel = path.relative_to(src)
            except Exception:
                continue
            if any(part in SESSION_MIRROR_EXCLUDED_DIRS for part in rel.parts):
                continue
            target = dst / rel
            try:
                if path.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if path.is_file():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
                    copied.append(rel.as_posix())
            except Exception:
                continue
        self.store.update_meta({
            "last_mirror_sync": {
                "source_root": str(src),
                "target_root": str(dst),
                "files_synced": len(copied),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        })
        return {
            "ok": True,
            "message": f"Espejo sincronizado hacia {dst} ({len(copied)} archivos)",
            "source_root": str(src),
            "target_root": str(dst),
            "files_synced": len(copied),
            "sample_files": copied[:20],
        }

# ── Quick test ──────────────────────────────────────────────────────

def _run_tests() -> int:
    import tempfile
    from provider_adapter import HealthStatus, ModelInfo

    class FailingAdapter(ProviderAdapter):
        def __init__(self, config: dict | None = None):
            super().__init__("failing", config)

        def chat(self, messages: list[dict], model: str, **kwargs: Any) -> ProviderResponse:
            raise RuntimeError("boom")

        def list_models(self) -> list[ModelInfo]:
            return [ModelInfo("broken", "broken", self.provider_name, 1024, 256, "test", "free")]

        def health_check(self, timeout: float = 5.0):
            return HealthStatus(ok=False, provider=self.provider_name, detail="boom")

        def is_configured(self) -> bool:
            return True

        def supports_tools(self) -> bool:
            return False

        def supports_streaming(self) -> bool:
            return False

    with tempfile.TemporaryDirectory() as td:
        state_root = Path(td) / "state"
        old = os.environ.get("BAGO_STATE_ROOT")
        os.environ["BAGO_STATE_ROOT"] = str(state_root)
        mgr = SessionManager(base_path=td, state_root=str(state_root), provider="ollama-local", model="qwen2.5:14b")
        assert mgr.session_id
        assert mgr.provider == "ollama-local"
        status = mgr.status()
        assert "session_id" in status
        assert status["provider"] == "ollama-local"
        original_engine = (mgr.provider, mgr.model)
        assert mgr.set_bago_mode("G")["mode"] == "G"
        assert mgr.activate_agent("coder")["ok"]
        assert (mgr.provider, mgr.model) == original_engine
        effective_prompt = mgr.effective_system_prompt()
        assert "MODO BAGO ACTIVO [G]" in effective_prompt
        assert "AGENTE ACTIVO [coder]" in effective_prompt
        mgr.save()
        loaded = SessionManager.load(mgr.session_id, base_path=td, state_root=str(state_root))
        assert loaded.provider == "ollama-local"
        assert loaded.bago_mode == "G"
        assert loaded.agent_gateway.active.name == "coder"

        ADAPTER_REGISTRY["failing"] = FailingAdapter
        failing = SessionManager(base_path=td, state_root=str(state_root), provider="failing", model="broken")
        before = len(failing.store.get_history())
        try:
            failing.send("este turno no debe persistirse")
            raise AssertionError("send() debía fallar con el adapter de prueba")
        except RuntimeError as exc:
            assert str(exc) == "boom"
        after = len(failing.store.get_history())
        assert before == after
        failing.close()
        ADAPTER_REGISTRY.pop("failing", None)

        loaded.close()
        mgr.close()
        print("session_manager.py --test: ALL PASS")
        if old is None:
            os.environ.pop("BAGO_STATE_ROOT", None)
        else:
            os.environ["BAGO_STATE_ROOT"] = old
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

