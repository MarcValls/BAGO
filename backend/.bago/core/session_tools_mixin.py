#!/usr/bin/env python3
"""session_tools_mixin.py — Tool approval, feedback, and memory mixin for SessionManager.

Extracted from session_manager.py during modularization.
Contains tool call approval/denial, feedback recording, and hybrid memory operations.
"""
from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from context_store import ContextMessage


class SessionToolsMixin:
    """Mixin: tool approval, feedback, hybrid memory operations."""

    def execute_runtime_control(self, arguments: dict[str, Any] | None = None) -> str:
        """Execute the fixed backend launch through the real Gateway path."""
        import hashlib
        import uuid
        import webbrowser
        from authorization_boundary import AuthorizationBoundary
        from execution_adapter_contract import ExecutionContext
        from execution_gateway import ExecutionGateway
        from execution_request import build_execution_request

        args = arguments if isinstance(arguments, dict) else {}
        action = str(args.get("action") or "start_and_open").strip().lower()
        if action not in {"start", "start_and_open"}:
            raise ValueError("runtime-control solo autoriza start o start_and_open")
        root = Path(str(getattr(self, "framework_root", "") or "")).resolve(strict=True)
        ui_dist = (root / "ui-react" / "dist").resolve(strict=True)
        launcher = (root / "bago_core" / "launcher.py").resolve(strict=True)
        host, port = "127.0.0.1", 8080
        argv = ["--base-path", str(root), "serve", "--host", host, "--port", str(port), "--ui-dist", str(ui_dist)]
        request = build_execution_request(
            effect_id="process.execute", actor_kind="user", principal_id="interactive-local-user",
            session_id=str(self.session_id), source_surface="cli.manager.launch",
            target={"operation": "launch_manager_server", "cwd": str(root), "python_root": str(root),
                    "python_module_sha256": hashlib.sha256(launcher.read_bytes()).hexdigest(),
                    "host": host, "port": port, "ui_dist": str(ui_dist)},
            arguments={"argv": argv}, scope="workspace", world_state_authority=self,
        )
        boundary = AuthorizationBoundary()
        interaction_id = f"chat-runtime-{uuid.uuid4().hex}"
        challenge = boundary.create_challenge(request, interaction_id=interaction_id)
        approval = boundary.approve_cli_native_challenge(
            challenge_id=str(challenge["challenge_id"]), interaction_id=interaction_id,
            session_id=request.session_id,
        )
        permit = str(approval.get("permit", {}).get("token") or "")
        if not permit:
            raise RuntimeError("no se emitió Permit para runtime-control")
        result, _authorization = ExecutionGateway(boundary).execute(
            permit_token=permit, request=request, context=ExecutionContext(manager=self),
        )
        opened = bool(webbrowser.open(f"http://{host}:{port}")) if action == "start_and_open" else False
        return json.dumps({"ok": bool(result.get("executed")), "action": action,
                           "gateway_owned": True, "effect_id": request.effect_id,
                           "receipt_id": result.get("receipt_id"),
                           "process_id": result.get("process_id"), "browser_opened": opened}, ensure_ascii=False)

    def _normalize_tool_approval_policy(self, policy: str | None) -> str:
        raw = " ".join(str(policy or "").strip().split()).lower().replace("-", "_")
        if raw in {"always", "auto", "permitir", "permitir_siempre", "siempre", "yes", "true", "1"}:
            return "always"
        if raw in {"ask", "prompt", "preguntar", "preguntar_siempre", "question", "maybe", "no", "false", "0"}:
            return "ask"
        return ""

    def tool_approval_policy(self) -> str:
        """Devuelve la política persistida de aprobación de tools."""
        policy = self._normalize_tool_approval_policy(self.config.get("features.tool_approval_policy", ""))
        if policy:
            return policy
        return "always" if bool(self.config.get("features.auto_allow_tools", False)) else "ask"

    def _tool_approval_auto_allowed(self) -> bool:
        return self.tool_approval_policy() == "always"

    def set_tool_approval_policy(self, policy: str) -> str:
        """Persiste la política de aprobación de tools y la sincroniza con el flag legado."""
        normalized = self._normalize_tool_approval_policy(policy)
        if not normalized:
            normalized = "ask"
        self.config.set("features.tool_approval_policy", normalized)
        self.config.set("features.auto_allow_tools", normalized == "always")
        return normalized

    def approve_tools(self, mode: str = "once") -> str:
        """Ejecuta las tool calls pendientes y reenvía al modelo.

        mode:
            once   -> ejecuta solo esta ronda
            always -> activa aprobación automática y ejecuta esta ronda
        Retorna la respuesta final del modelo.
        """
        normalized_mode = self._normalize_tool_approval_policy(mode)
        policy_note = ""
        if normalized_mode == "always":
            self.set_tool_approval_policy("always")
            policy_note = " Política actualizada a permitir siempre."

        if not self._pending_tools or not self._pending_normalized:
            return f"No hay herramientas pendientes de aprobación.{policy_note}"

        adapter = self._ensure_adapter()
        tools = None
        if adapter.supports_tools() and len(self.tool_registry) > 0:
            tools = self.tool_registry.to_openai()

        for tc in self._pending_tools:
            call = self.tool_registry.parse_tool_calls({"tool_calls": [tc]})[0]
            result = self.tool_registry.execute_model_call(call)
            tool_msg = {
                "role": "tool",
                "tool_call_id": result.call_id,
                "content": result.content,
            }
            self._pending_normalized.append(tool_msg)
            self.store.append_message(ContextMessage(
                role="tool",
                content=result.content,
                metadata={"tool_call_id": result.call_id, "name": result.name},
            ))

        resp = adapter.chat(
            self._pending_normalized,
            self.model,
            system=self.effective_system_prompt(),
            tools=tools,
            **self._pending_tools_kwargs,
        )

        self.store.append_response(
            resp.content,
            provider=self.provider,
            model=resp.model_used,
            metadata={"finish_reason": resp.finish_reason},
        )
        self.store.record_tokens(
            provider=self.provider,
            model=resp.model_used,
            tokens_in=resp.usage.input_tokens,
            tokens_out=resp.usage.output_tokens,
        )
        self.total_tokens += resp.usage.total_tokens
        self.total_calls += 1

        if bool(self.config.get("features.rl_learning", True)):
            self.rl_feedback.implicit(
                session_id=self.session_id,
                provider=self.provider,
                model=resp.model_used or self.model,
                user_message=self._pending_user_message,
                response=resp.content,
                response_time_ms=0,
                tokens_used=resp.usage.total_tokens,
            )

        self._pending_tools = None
        self._pending_normalized = None
        self._pending_user_message = ""
        self._pending_tools_kwargs = {}

        return resp.content

    def deny_tools(self, mode: str = "once") -> str:
        """Rechaza las tool calls pendientes y limpia el estado.

        mode:
            once -> rechaza solo esta ronda
            ask  -> rechaza esta ronda y deja la política en preguntar siempre
        """
        normalized_mode = self._normalize_tool_approval_policy(mode)
        policy_note = ""
        if normalized_mode == "ask":
            self.set_tool_approval_policy("ask")
            policy_note = " Política actualizada a preguntar siempre."

        if not self._pending_tools:
            return f"No hay herramientas pendientes de aprobación.{policy_note}"

        self.store.append_message(ContextMessage(
            role="system",
            content="[El usuario rechazó la ejecución de herramientas]",
        ))

        self._pending_tools = None
        self._pending_normalized = None
        self._pending_user_message = ""
        self._pending_tools_kwargs = {}
        return f"Herramientas rechazadas.{policy_note}"

    def feedback(self, rating: float, user_message: str = "") -> None:
        """Registra feedback explícito del usuario para la última interacción."""
        if not bool(self.config.get("features.rl_learning", True)):
            return
        history = self.store.get_history()
        last_user = ""
        for entry in reversed(history):
            if entry.get("role") == "user":
                last_user = entry.get("content", "")
                break
        self.rl_feedback.explicit(
            session_id=self.session_id,
            provider=self.provider,
            model=self.model,
            user_message=user_message or last_user,
            rating=rating,
        )

    def memory_add_hybrid(self, content: str) -> dict[str, Any]:
        adapter = self._ensure_adapter()
        if not adapter.supports_embeddings():
            raise RuntimeError(f"{self.provider} no soporta memoria híbrida")
        vector = adapter.embed([content], model=self.model)[0]
        from bago_core.memory_database import execute_memory_database_cli

        return execute_memory_database_cli(
            self,
            "knowledge.hybrid_add",
            {
                "content": content,
                "vector": vector,
                "provider": self.provider,
                "model": self.model,
            },
        )

    def memory_search_hybrid(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        adapter = self._ensure_adapter()
        if not adapter.supports_embeddings():
            raise RuntimeError(f"{self.provider} no soporta memoria híbrida")
        query_vector = adapter.embed([query], model=self.model)[0]
        return self.embedding_store.search(query_vector=query_vector, limit=limit)
