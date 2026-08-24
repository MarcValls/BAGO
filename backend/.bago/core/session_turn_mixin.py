#!/usr/bin/env python3
"""session_turn_mixin.py - Turn execution mixin for SessionManager.

Contains model turn orchestration: send, streaming, tool-call rounds,
receipts, token accounting, and bridge orchestration.
"""
from __future__ import annotations

import sys
import time
import json
import re
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from context_store import ContextMessage
from context_envelope import ContextReceipt
from context_budget import compute_budget, truncate_context
from intent_engine import classify_intent, should_enable_tools, get_few_shot_examples, intent_guidance
from prompt_loader import load_prompt
from provider_adapter import ProviderResponse
from task_response_contract import (
    TASK_INTENTS,
    canonicalize_task_response,
    task_response_guidance,
    validate_task_response,
)
from task_response_presenter import present_legacy_task_content, present_task_response, task_response_state
from reflexive_interpreter import analyze_question
from reflexive_audit_ledger import ReflexiveAuditLedger
from session_utils import ADAPTER_REGISTRY, normalize_bridges, format_rag_context

# --- File-write helpers ---------------------------------------------------

_FILE_CREATE_RE = re.compile(
    r"\b(crea[r]?|genera[r]?|escrib[ei]r?|redacta[r]?|produce?|make|creat[ei])\b.{0,80}"
    r"\b(archivo|fichero|file|\.md|\.txt|\.py|\.js|\.ts|\.json|\.html|\.css|\.yaml|\.yml)\b",
    re.IGNORECASE | re.UNICODE,
)
_ESCRIBELO_RE = re.compile(r"^\s*(es[cC]r[ií]b[ea]lo|escri[bv]elo|wr[ií]t[ei]\s*it|write\s+it)\s*$", re.IGNORECASE)
_WRITE_BLOCK_RE = re.compile(r"\[WRITE:([^\]\r\n]+)\]\n(.*?)\[/WRITE\]", re.DOTALL)
_NO_EXECUTION_RE = re.compile(
    r"\b(sin\s+(?:ejecutar|aplicar|hacer)\s+(?:cambios|acciones)?|solo\s+(?:un\s+)?plan|no\s+uses?\s+herramientas|read[- ]?only)\b",
    re.IGNORECASE | re.UNICODE,
)


def _is_file_creation_request(text: str) -> bool:
    t = (text or "").strip()
    if _ESCRIBELO_RE.match(t):
        return True
    return bool(_FILE_CREATE_RE.search(t))


def _requests_no_execution(text: str) -> bool:
    return bool(_NO_EXECUTION_RE.search(text or ""))


def _extract_and_write_files(content: str, write_root: "Path") -> tuple[list[dict], str]:
    """Extract [WRITE:path]content[/WRITE] blocks from content, write them to disk.
    Returns (files_written, cleaned_content)."""
    files_written: list[dict] = []
    def _replacer(m: re.Match) -> str:
        rel_path = m.group(1).strip()
        file_content = m.group(2)
        # strip trailing newline added by the marker
        if file_content.endswith("\n"):
            file_content = file_content[:-1]
        try:
            target = (write_root / rel_path).resolve()
            target.relative_to(write_root)  # sandbox check
            target.parent.mkdir(parents=True, exist_ok=True)
            existed = target.exists()
            target.write_text(file_content, encoding="utf-8")
            files_written.append({"ok": True, "path": rel_path, "absolute_path": str(target), "created": not existed})
            return f"✅ Archivo escrito: `{rel_path}` ({len(file_content.encode())} bytes)\nRuta completa: `{target}`"
        except Exception as exc:
            files_written.append({"ok": False, "path": rel_path, "error": str(exc)})
            return f"❌ No se pudo escribir `{rel_path}`: {exc}"
    cleaned = _WRITE_BLOCK_RE.sub(_replacer, content)
    return files_written, cleaned


# -------------------------------------------------------------------------


class SessionTurnMixin:
    """Mixin: one user turn, streaming turn, and bridge orchestration."""

    def _sanitize_provider_history(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sanitized: list[dict[str, Any]] = []
        for message in messages:
            item = dict(message)
            if item.get("role") == "assistant" and isinstance(item.get("content"), str):
                item["content"] = present_legacy_task_content(item["content"])[0]
            sanitized.append(item)
        return sanitized

    def send_internal(self, user_message: str, **kwargs: Any) -> str:
        """Run a structured helper prompt without polluting chat history or receipts."""
        adapter = self._ensure_adapter()
        system = self.effective_system_prompt() + (
            "\n\nINTERNAL BAGO ANALYSIS\n"
            "This is an internal structured request. Return exactly the format requested by the prompt. "
            "Do not call tools and do not address the end user."
        )
        response = adapter.chat(
            [{"role": "user", "content": user_message}],
            self.model,
            system=system,
            tools=None,
            **self._provider_call_kwargs("chat", kwargs),
        )
        return response.content

    def _default_max_tokens_for_intent(self, intent: str) -> int:
        """Keep local Ollama turns bounded unless the caller overrides it."""
        if intent in ("work", "review"):
            return 1024
        if intent == "execute":
            return 512
        return 160

    def _provider_call_kwargs(self, intent: str, provided: dict[str, Any]) -> dict[str, Any]:
        call_kwargs = dict(provided)
        depth = str(getattr(self, "reasoning_depth", "normal") or "normal").lower()
        auto_temperature = 0.35 if intent == "execute" else 0.45 if intent in ("work", "review") else 0.6
        depth_temperature = {"normal": 0.7, "media": 0.5, "alta": 0.3, "maxima": 0.2, "auto": auto_temperature}.get(depth, 0.7)
        temperature = float(self.config.get("temperature", depth_temperature)) if depth == "normal" else float(depth_temperature)
        call_kwargs.setdefault("temperature", temperature)
        if call_kwargs.get("max_tokens") is None:
            configured_max = self.config.get("max_tokens")
            if configured_max:
                call_kwargs["max_tokens"] = int(configured_max)
            elif self.provider == "ollama-local":
                call_kwargs["max_tokens"] = self._default_max_tokens_for_intent(intent)
        return call_kwargs

    def _route_system_prompt(self) -> str:
        return load_prompt("router.md")

    def _route_fallback(self, user_message: str) -> dict[str, Any]:
        return {"kind": "chat", "command": "", "args": [], "confidence": 0.0, "reason": "model unavailable"}

    def _route_from_model(self, user_message: str) -> dict[str, Any]:
        text = (user_message or "").strip()
        if not text:
            return {"kind": "chat", "command": "", "args": [], "confidence": 1.0, "reason": "empty"}
        lowered = text.lower()
        if lowered in {"hola", "buenas", "buenos dias", "buenas tardes", "buenas noches", "hello", "hi"}:
            return {"kind": "chat", "command": "", "args": [], "confidence": 0.99, "reason": "greeting_heuristic", "source": "heuristic"}
        history = []
        try:
            history = list(getattr(self, "store", None).get_history() or [])
        except Exception:
            history = []
        recent_lines = []
        for item in history[-6:]:
            role = str(item.get("role", "")).strip().lower()
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            recent_lines.append(f"{role}: {content[:500]}")
        router_messages = [{"role": "system", "content": self._route_system_prompt()}]
        if recent_lines:
            router_messages.append({
                "role": "system",
                "content": "CONTEXTO RECIENTE\n" + "\n".join(recent_lines),
            })
        router_messages.append({"role": "user", "content": text})
        try:
            adapter = self._ensure_adapter()
            response = adapter.chat(
                router_messages,
                self.model,
                system=self._route_system_prompt(),
                tools=None,
                temperature=0.0,
                max_tokens=96,
            )
        except Exception:
            return self._route_fallback(text)

        raw = (response.content or "").strip()
        if not raw:
            return self._route_fallback(text)
        candidate = raw
        if "```" in candidate:
            candidate = candidate.replace("```json", "").replace("```", "").strip()
        match = re.search(r"\{.*\}", candidate, re.S)
        if match:
            candidate = match.group(0)
        try:
            data = json.loads(candidate)
        except Exception:
            return self._route_fallback(text)
        # Defensive: small/local models sometimes return a JSON scalar
        # (e.g. just a number or a string) which parses successfully
        # but is not a dict. The router contract is "kind/command/args"
        # so anything non-dict must fall back to chat.
        if not isinstance(data, dict):
            return self._route_fallback(text)
        kind = str(data.get("kind", "chat")).strip().lower()
        command = str(data.get("command", "") or "").strip()
        args = data.get("args", [])
        if kind not in {"chat", "command", "workspace_question"}:
            return self._route_fallback(text)
        if kind == "command" and not command.startswith("/"):
            return self._route_fallback(text)
        if not isinstance(args, list):
            args = []
        args = [str(item).strip() for item in args if str(item).strip()]
        confidence = data.get("confidence", 0.0)
        try:
            confidence = float(confidence)
        except Exception:
            confidence = 0.0
        reason = str(data.get("reason", "")).strip() or "model route"
        return {
            "kind": kind,
            "command": command,
            "args": args,
            "confidence": confidence,
            "reason": reason,
            "source": "model",
        }

    def route_user_message(self, user_message: str) -> dict[str, Any]:
        """Consulta al modelo si el texto activa un comando o sigue como chat."""
        return self._route_from_model(user_message)

    def _needs_task_response_contract(self, intent: str) -> bool:
        return intent in TASK_INTENTS

    def _capture_conversational_goal(self, user_message: str, intent: str) -> bool:
        """Capture the first substantive work request as the session goal.

        The goal is session-scoped context, not a second form the user must
        fill in.  Only affirmative work/execute turns seed it; short replies
        such as ``sí`` or ``continúa`` therefore keep the existing objective.
        An explicit goal already set by the user always wins.
        """
        if intent not in {"work", "execute"}:
            return False
        goal = str(getattr(self, "persistent_goal", "") or "").strip()
        candidate = " ".join(str(user_message or "").split()).strip()
        if goal or len(candidate) < 12:
            return False
        setter = getattr(self, "set_goal", None)
        if not callable(setter):
            return False
        setter(candidate[:2000])
        store = getattr(self, "store", None)
        if store is not None and hasattr(store, "update_meta"):
            try:
                store.update_meta({"persistent_goal": candidate[:2000]})
            except Exception:
                # Goal capture must never make a chat turn fail.
                pass
        return True

    def _task_response_contract_block(self, intent: str, user_message: str) -> str:
        return task_response_guidance(intent, user_message=user_message) if self._needs_task_response_contract(intent) else ""

    def build_reflexive_context(self, user_message: str = "", *, history_limit: int = 8) -> dict[str, Any]:
        """Build the session context consumed by the Reflexive Interpreter."""
        history_items: list[str] = []
        try:
            history = list(self.store.get_history(limit=history_limit) or [])
        except Exception:
            history = []
        for item in history:
            role = str(item.get("role", "")).strip().lower() or "unknown"
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            history_items.append(f"{role}: {content[:500]}")

        constraints: list[str] = [
            f"provider={getattr(self, 'provider', '')}",
            f"model={getattr(self, 'model', '')}",
            f"bago_mode={getattr(self, 'bago_mode', '')}",
            f"workspace={getattr(self, 'base_path', '')}",
        ]
        goal = str(getattr(self, "persistent_goal", "") or "").strip()
        if goal:
            constraints.append(f"goal={goal}")

        return {
            "domain": "bago-session",
            "conversation_history": history_items,
            "constraints": constraints,
            "metadata": {
                "session_id": getattr(self, "session_id", ""),
                "provider": getattr(self, "provider", ""),
                "model": getattr(self, "model", ""),
                "project_root": str(getattr(self, "project_root", getattr(self, "base_path", ""))),
                "workspace_state_root": str(getattr(self, "workspace_state_root", "")),
                "message_excerpt": (user_message or "")[:500],
            },
        }

    def analyze_reflexive_turn(self, user_message: str, *, question_id: str | None = None) -> dict[str, Any]:
        """Return a serializable Reflexive Interpreter analysis for a turn."""
        return analyze_question(
            user_message,
            self.build_reflexive_context(user_message),
            question_id=question_id,
        ).to_dict()

    def _record_reflexive_audit(
        self,
        *,
        receipt: ContextReceipt,
        analysis: dict[str, Any],
        response_content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist a Reflexive Interpreter audit record and return its link."""
        try:
            ledger = getattr(self, "_reflexive_audit_ledger", None)
            if ledger is None:
                ledger = ReflexiveAuditLedger(getattr(self, "state_root", getattr(self, "state_dir", ".")))
                self._reflexive_audit_ledger = ledger
            return ledger.append(
                session_id=getattr(self, "session_id", ""),
                provider=getattr(self, "provider", ""),
                model=getattr(self, "model", ""),
                receipt_id=receipt.envelope_id,
                analysis=analysis,
                response_content=response_content,
                metadata=metadata or {},
            )
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def reflexive_audit_tail(self, limit: int = 10) -> dict[str, Any]:
        """Return recent Reflexive Interpreter audit records."""
        ledger = getattr(self, "_reflexive_audit_ledger", None)
        if ledger is None:
            ledger = ReflexiveAuditLedger(getattr(self, "state_root", getattr(self, "state_dir", ".")))
            self._reflexive_audit_ledger = ledger
        items = ledger.tail(limit)
        return {
            "ok": True,
            "path": str(ledger.path),
            "count": len(items),
            "items": items,
        }

    def record_reflexive_command_audit(
        self,
        *,
        analysis: dict[str, Any],
        response_content: str,
        command: str = "/interpret",
    ) -> dict[str, Any]:
        """Persist a Reflexive Interpreter audit produced by a slash command."""
        ledger = getattr(self, "_reflexive_audit_ledger", None)
        if ledger is None:
            ledger = ReflexiveAuditLedger(getattr(self, "state_root", getattr(self, "state_dir", ".")))
            self._reflexive_audit_ledger = ledger
        return ledger.append(
            session_id=getattr(self, "session_id", ""),
            provider=getattr(self, "provider", ""),
            model=getattr(self, "model", ""),
            receipt_id=f"command:{command}:{analysis.get('question_id', '')}",
            analysis=analysis,
            response_content=response_content,
            metadata={"command": command},
        )

    def _canonical_task_failure_payload(
        self,
        *,
        intent: str,
        user_message: str,
        errors: list[dict[str, Any]],
        warnings: list[str],
        previous_content: str = "",
    ) -> str:
        objective = self.persistent_goal.strip() or user_message.strip()
        payload = {
            "intent": intent,
            "objective": objective,
            "facts": [],
            "assumptions": [],
            "files_required": [],
            "symbols_required": [],
            "evidence": [
                {
                    "type": "validation_error",
                    "errors": errors,
                    "previous_response_excerpt": previous_content[:400],
                }
            ],
            "risks": ["invalid_model_response"],
            "proposed_changes": [],
            "validation_actions": ["repair_response", "revalidate_contract"],
            "missing_information": [item.get("detail", "missing information") for item in errors] or warnings,
            "confidence": 0.0,
        }
        return canonicalize_task_response(payload)

    def _validate_task_response(
        self,
        *,
        intent: str,
        user_message: str,
        content: str,
        warnings: list[str] | None = None,
    ) -> tuple[bool, str, dict[str, Any]]:
        if not self._needs_task_response_contract(intent):
            return True, content, {"ok": True, "skipped": True}
        report = validate_task_response(content, intent=intent)
        if report.ok:
            return True, canonicalize_task_response(report.data), report.to_dict()
        fallback = self._canonical_task_failure_payload(
            intent=intent,
            user_message=user_message,
            errors=list(report.errors),
            warnings=list(warnings or []) + list(report.warnings),
            previous_content=content,
        )
        return False, fallback, report.to_dict()

    def _repair_task_response(
        self,
        *,
        adapter: Any,
        envelope: Any,
        normalized: list[dict[str, Any]],
        intent: str,
        user_message: str,
        response_content: str,
        call_kwargs: dict[str, Any],
    ) -> tuple[bool, str, dict[str, Any]]:
        report = validate_task_response(response_content, intent=intent)
        if report.ok:
            return True, canonicalize_task_response(report.data), report.to_dict()

        repair_block = "\n".join([
            "TASK RESPONSE REPAIR REQUIRED",
            "Your previous response did not satisfy the JSON contract.",
            "Return only a valid JSON object with the required keys.",
            f"Validation errors: {json.dumps(list(report.errors), ensure_ascii=False)}",
            f"Validation warnings: {json.dumps(list(report.warnings), ensure_ascii=False)}",
            "Do not repeat prose. Do not use markdown fences.",
        ])
        repair_messages = list(normalized)
        repair_messages.append({"role": "assistant", "content": response_content})
        repair_messages.append({"role": "system", "content": repair_block})
        repaired = adapter.chat(
            repair_messages,
            self.model,
            system=envelope.system_prompt,
            tools=None,
            **call_kwargs,
        )
        repaired_report = validate_task_response(repaired.content, intent=intent)
        if repaired_report.ok:
            return True, canonicalize_task_response(repaired_report.data), repaired_report.to_dict()
        fallback = self._canonical_task_failure_payload(
            intent=intent,
            user_message=user_message,
            errors=list(repaired_report.errors),
            warnings=list(repair_block.splitlines()),
            previous_content=repaired.content,
        )
        return False, fallback, repaired_report.to_dict()

    def send(self, user_message: str, **kwargs: Any) -> str:
        """Send a user message to the active provider and persist the turn."""
        self.last_clarification = None
        self.last_response_state = "running"
        route_info = kwargs.pop("route_info", None) or self.route_user_message(user_message)
        code_task = self._classify_code_request(user_message)
        self.last_code_task = code_task.to_dict() if code_task is not None else None
        self.last_code_task_contract = self._compile_code_task_contract(code_task, objective=user_message) if code_task is not None else None
        if code_task is not None and code_task.blocked:
            _dangerous_reasons = {"dangerous_or_sensitive_request", "allowed_files_violation"}
            _is_dangerous = bool(_dangerous_reasons & set(code_task.reasons))
            if _is_dangerous:
                # Hard refusal for genuinely unsafe requests
                refusal = code_task.refusal_message()
                self.store.append_user(user_message, provider=self.provider, model=self.model)
                self.store.append_response(
                    refusal,
                    provider=self.provider,
                    model=self.model,
                    metadata={"code_task": self.last_code_task, "blocked": True},
                )
                return refusal
            else:
                # Ambiguous request — ask user to choose action
                import json as _json
                _clarify = _json.dumps({
                    "question": "¿Qué quieres que haga con esto?",
                    "options": [
                        {"id": "crear", "label": "Crear / escribir un archivo", "prefix": "Crea un archivo"},
                        {"id": "modificar", "label": "Modificar un archivo existente", "prefix": "Modifica el archivo"},
                        {"id": "explicar", "label": "Explicar o resumir", "prefix": "Explica"},
                        {"id": "chat", "label": "Solo conversar sobre el tema", "prefix": "Cuéntame sobre"},
                    ],
                    "original": user_message,
                }, ensure_ascii=False)
                clarify_payload = _json.loads(_clarify)
                clarify_response = clarify_payload["question"]
                self.last_clarification = clarify_payload
                self.last_response_state = "needs_confirmation"
                self.store.append_user(user_message, provider=self.provider, model=self.model)
                self.store.append_response(
                    clarify_response,
                    provider=self.provider,
                    model=self.model,
                    metadata={"code_task": self.last_code_task, "clarify": True, "clarification": clarify_payload, "response_state": self.last_response_state},
                )
                return clarify_response

        workspace_question = route_info.get("kind") == "workspace_question"

        adapter = self._ensure_adapter()
        start = time.time()

        history = self.store.get_history()
        normalized = self._sanitize_provider_history(self.msg_adapter.to_provider(history, self.provider))
        normalized.append({"role": "user", "content": user_message})

        intent = "chat" if workspace_question else classify_intent(user_message)
        self._capture_conversational_goal(user_message, intent)
        _is_file_write_request = _is_file_creation_request(user_message)
        try:
            reflexive_analysis = self.analyze_reflexive_turn(user_message)
        except Exception as exc:
            reflexive_analysis = {
                "ok": False,
                "error": str(exc),
                "literal_reading": user_message,
                "intent": intent,
                "confidence": 0.0,
            }
        dynamic_system = self.effective_system_prompt()
        if intent != "chat":
            dynamic_system += "\n\n" + intent_guidance(intent)
            dynamic_system += get_few_shot_examples(intent, max_examples=2)
        else:
            dynamic_system += "\n\n" + intent_guidance("chat")

        workspace_block = self._workspace_question_block(user_message) if workspace_question else ""
        if workspace_block:
            dynamic_system += "\n\n" + workspace_block

        bc_block = self._bc_policy_block(user_message)
        if bc_block:
            dynamic_system += "\n\n" + bc_block

        task_contract_block = self._task_response_contract_block(intent, user_message)
        if task_contract_block:
            dynamic_system += "\n\n" + task_contract_block

        if code_task is not None and code_task.is_code_request:
            dynamic_system += (
                "\n\nCode Forge classifier: "
                f"kind={code_task.kind}; "
                f"targets={', '.join(code_task.target_files) if code_task.target_files else 'none'}; "
                f"blocked={code_task.blocked}"
            )

        rag_fragments, code_context = self._workspace_context_pack(user_message, code_task)
        rag_block = format_rag_context(rag_fragments)
        if rag_block:
            dynamic_system += "\n\n" + rag_block

        gabo_block = self._gabo_block()
        if gabo_block:
            dynamic_system += "\n\n" + gabo_block

        # CLI-backed providers run their own workspace tools. Keep their
        # envelope compact, but never tell them to avoid edits: a BAGO task
        # may explicitly require the CLI to create or validate project files.
        uses_cli_bridge = False
        try:
            uses_cli_bridge = self.provider in {"copilot", "codex"} and bool(adapter._use_cli())
        except Exception:
            uses_cli_bridge = False
        uses_compact_human_bridge = uses_cli_bridge or self.provider == "ollama-local"
        if uses_compact_human_bridge and task_contract_block:
            compact_blocks = [
                "You are BAGO's execution model for the authorized workspace.",
                "When the user requests project changes or validation, use your workspace tools to execute them and then report the result concisely.",
                "Do not return an internal JSON contract.",
            ]
            dynamic_system = "\n\n".join(block for block in compact_blocks if block)

        tools = None
        if (
            self._tool_calling_enabled()
            and adapter.supports_tools()
            and len(self.tool_registry) > 0
            and should_enable_tools(intent)
            and not _requests_no_execution(user_message)
        ):
            tools = self.tool_registry.to_openai()
            if self.provider == "ollama-local":
                dynamic_system += (
                    "\n\nOLLAMA LOCAL TOOL FORMAT\n"
                    "If native tool_calls are available, use them. If not, request exactly one tool with:\n"
                    "<tool_call>{\"name\":\"file-read\",\"arguments\":{\"path\":\"relative/path\"}}</tool_call>\n"
                    "Use search-symbol, search-text, find-dependents, read-lines, dir-list and file-read before file-write or file-edit when existing context matters. "
                    "Do not invent file contents; read the file first."
                )

        ctx_tokens = self._get_model_context_tokens()
        budget = compute_budget(
            dynamic_system, normalized, tools, model_context_tokens=ctx_tokens,
        )
        if budget.is_critical:
            normalized, tools, budget = truncate_context(
                dynamic_system, normalized, tools,
                model_context_tokens=ctx_tokens, preserve_last_n=6,
            )
        self.last_budget_report = budget

        envelope = self._build_context_envelope(
            system_prompt=dynamic_system,
            user_message=user_message,
            intent=intent,
            normalized=normalized,
            tools=tools,
            budget=budget,
            code_task=code_task,
            code_task_contract=self.last_code_task_contract,
            rag_fragments=rag_fragments,
            code_context=code_context,
            streaming=False,
        )

        call_kwargs = self._provider_call_kwargs(intent, kwargs)
        resp = adapter.chat(
            envelope.messages,
            self.model,
            system=envelope.system_prompt,
            tools=envelope.tools,
            **call_kwargs,
        )
        self.store.append_user(user_message, provider=self.provider, model=self.model)

        tool_rounds = 0
        max_tool_rounds = int(self.config.get("tools.max_rounds", 4) or 4)
        tools_executed: list[dict[str, Any]] = []
        while resp.tool_calls and tool_rounds < max_tool_rounds:
            tool_rounds += 1
            assistant_msg = {"role": "assistant", "content": resp.content or ""}
            if resp.tool_calls:
                assistant_msg["tool_calls"] = resp.tool_calls
            normalized.append(assistant_msg)
            self.store.append_response(
                assistant_msg.get("content", "") + "\n[tool_calls]",
                provider=self.provider,
                model=resp.model_used,
                metadata={"tool_calls": resp.tool_calls},
            )

            if not self._tool_approval_auto_allowed():
                self._pending_tools = resp.tool_calls
                self._pending_normalized = normalized.copy()
                self._pending_user_message = user_message
                self._pending_tools_kwargs = kwargs.copy()
                lines = ["⏸️ El modelo quiere usar estas herramientas:"]
                for tc in resp.tool_calls:
                    func = tc.get("function", {})
                    lines.append(f"  • {func.get('name', 'unknown')}: {func.get('arguments', '{}')}")
                lines.append("\nSelecciona una acción o usa /allow [once|always] /deny [once|ask].")
                return "\n".join(lines)

            for tc in resp.tool_calls:
                parsed_calls = self.tool_registry.parse_tool_calls({"tool_calls": [tc]})
                if not parsed_calls:
                    continue
                call = parsed_calls[0]

                guard_result = self.path_guard.check(call.name, call.arguments)
                if guard_result.blocked:
                    tools_executed.append({
                        "call_id": call.call_id,
                        "name": call.name,
                        "ok": False,
                        "blocked": True,
                        "reason": guard_result.reason,
                        "latency_ms": 0.0,
                    })
                    self.tool_logger.log(
                        session_id=self.session_id,
                        tool_name=call.name,
                        arguments=call.arguments,
                        ok=False,
                        returncode=1,
                        latency_ms=0.0,
                        content=guard_result.reason,
                        blocked=True,
                        block_reason=guard_result.reason,
                    )
                    tool_msg = {
                        "role": "tool",
                        "tool_call_id": call.call_id,
                        "content": f"BLOQUEADO: {guard_result.reason}",
                    }
                    normalized.append(tool_msg)
                    self.store.append_message(ContextMessage(
                        role="tool",
                        content=f"BLOQUEADO: {guard_result.reason}",
                        metadata={"tool_call_id": call.call_id, "name": call.name, "blocked": True, "reason": guard_result.reason},
                    ))
                    continue

                tool_start = time.time()
                result = self.tool_registry.execute_call(call)
                tool_elapsed = (time.time() - tool_start) * 1000

                tools_executed.append({
                    "call_id": result.call_id,
                    "name": result.name,
                    "ok": result.ok,
                    "returncode": result.returncode,
                    "latency_ms": round(tool_elapsed, 3),
                })
                self.tool_logger.log(
                    session_id=self.session_id,
                    tool_name=call.name,
                    arguments=call.arguments,
                    ok=result.ok,
                    returncode=result.returncode,
                    latency_ms=tool_elapsed,
                    content=result.content,
                )

                tool_msg = {
                    "role": "tool",
                    "tool_call_id": result.call_id,
                    "content": result.content,
                }
                normalized.append(tool_msg)
                self.store.append_message(ContextMessage(
                    role="tool",
                    content=result.content,
                    metadata={"tool_call_id": result.call_id, "name": result.name},
                ))

            resp = adapter.chat(
                normalized,
                self.model,
                system=envelope.system_prompt,
                tools=envelope.tools,
                **call_kwargs,
            )
        if resp.tool_calls:
            resp = ProviderResponse(
                content=f"BLOQUEADO: límite de rondas de herramientas alcanzado ({max_tool_rounds}).",
                model_used=resp.model_used or self.model,
                provider=resp.provider or self.provider,
                finish_reason="tool_round_limit",
                usage=resp.usage,
                metadata={"blocked": True, "tool_rounds": tool_rounds},
                tool_calls=[],
            )

        task_contract_meta: dict[str, Any] = {"ok": True, "skipped": True}
        final_content = resp.content
        response_state = "done"
        provider_failed = resp.finish_reason == "error" or bool(resp.metadata.get("error"))
        provider_error = resp.content if provider_failed else ""
        task_contract_required = self._needs_task_response_contract(intent) and not uses_compact_human_bridge
        if task_contract_required and tool_rounds == 0 and not _is_file_write_request and not provider_failed:
            ok, validated_content, contract_meta = self._validate_task_response(
                intent=intent,
                user_message=user_message,
                content=resp.content,
            )
            task_contract_meta = contract_meta
            if not ok:
                ok, validated_content, contract_meta = self._repair_task_response(
                    adapter=adapter,
                    envelope=envelope,
                    normalized=normalized,
                    intent=intent,
                    user_message=user_message,
                    response_content=resp.content,
                    call_kwargs=call_kwargs,
                )
                task_contract_meta = contract_meta
            resp = ProviderResponse(
                content=validated_content,
                model_used=resp.model_used,
                provider=resp.provider,
                finish_reason=resp.finish_reason,
                usage=resp.usage,
                metadata={**resp.metadata, "task_contract": task_contract_meta, "code_task": self.last_code_task, "code_task_contract": self.last_code_task_contract},
                tool_calls=resp.tool_calls,
            )
        elif task_contract_required:
            task_contract_meta = {
                "ok": not provider_failed,
                "skipped": True,
                "reason": "provider_error" if provider_failed else "tool_rounds_used",
                "tool_rounds": tool_rounds,
            }
        elif self._needs_task_response_contract(intent) and uses_compact_human_bridge:
            task_contract_meta = {
                "ok": not provider_failed,
                "skipped": True,
                "reason": "compact_human_response",
            }

        claim_check = self.claim_validator.validate(resp.content, self.tool_logger)
        claim_warning = claim_check.has_claim and not claim_check.has_evidence
        claim_verification: dict[str, Any] = {
            "claims": [],
            "verified": [],
            "inferred": [],
            "assumed": [],
            "unverified": [],
            "contradicted": [],
            "disputed": [],
            "obsolete": [],
            "undetermined": [],
            "evidence_items": [],
            "verified_without_evidence_blocked": [],
        }
        if hasattr(self, "claim_verifier") and self.claim_verifier:
            try:
                claim_payload: dict[str, Any] = {}
                if isinstance(resp.content, str) and resp.content.strip().startswith("{"):
                    try:
                        claim_payload = json.loads(resp.content)
                    except Exception:
                        claim_payload = {}
                claims = claim_payload.get("facts") or claim_payload.get("claims") or []
                evidence = claim_payload.get("evidence") or []
                claim_verification = self.claim_verifier.verify(claims, evidence=evidence, response_text=resp.content)
            except Exception:
                claim_verification = {
                    "claims": [],
                    "verified": [],
                    "inferred": [],
                    "assumed": [],
                    "unverified": [],
                    "contradicted": [],
                    "disputed": [],
                    "obsolete": [],
                    "undetermined": [],
                    "evidence_items": [],
                    "verified_without_evidence_blocked": [],
                }
        if claim_verification.get("unverified"):
            claim_warning = True
        if provider_failed:
            response_state = "failed"
            provider_detail = str(resp.content or "").strip()
            if ":" in provider_detail:
                provider_detail = provider_detail.split(":", 1)[1].strip()
            provider_detail = " ".join(provider_detail.split())[:500]
            final_content = f"{self.provider} no pudo completar la solicitud."
            if provider_detail:
                final_content += f" Motivo: {provider_detail}"
            final_content += " Puedes reintentar o elegir otro modelo."
        elif task_contract_required and not task_contract_meta.get("skipped"):
            contract_data = task_contract_meta.get("data") if isinstance(task_contract_meta.get("data"), dict) else {}
            contract_ok = bool(task_contract_meta.get("ok"))
            response_state = task_response_state(contract_data, contract_ok=contract_ok)
            final_content = present_task_response(contract_data, user_message=user_message, contract_ok=contract_ok)
        else:
            final_content = resp.content
        if claim_check.warning:
            final_content += claim_check.warning
        self.last_response_state = response_state
        workspace_fallback_used = False
        if workspace_question and not self._workspace_answer_mentions_active_project(final_content):
            final_content = self._workspace_fallback_reply()
            workspace_fallback_used = True

        # Auto-write any [WRITE:path]content[/WRITE] blocks in the response
        # Use project_root (user project), falling back to workspace_scope_root. Never use the temp mirror.
        _write_root_str = (
            str(getattr(self, "project_root", None) or "")
            or str(getattr(self, "workspace_scope_root", None) or "")
            or str(Path.cwd())
        )
        _write_root = Path(_write_root_str).resolve()
        _files_written, final_content = _extract_and_write_files(final_content, _write_root)

        elapsed_ms = (time.time() - start) * 1000

        receipt = ContextReceipt.from_response(
            envelope=envelope,
            response_content=final_content,
            model_used=resp.model_used or self.model,
            finish_reason=resp.finish_reason,
            usage_input=resp.usage.input_tokens,
            usage_output=resp.usage.output_tokens,
            usage_total=resp.usage.total_tokens,
            latency_ms=elapsed_ms,
            extra_metadata={
                "intent": intent,
                "tool_calls_used": tool_rounds > 0,
                "tool_rounds": tool_rounds,
                "rag_fragments": len(rag_fragments),
                "task_contract": task_contract_meta,
                "response_state": response_state,
                "provider_error": provider_error,
                "code_task": self.last_code_task,
                "code_task_contract": self.last_code_task_contract,
                "claim_warning": claim_warning,
                "claim_verification": claim_verification,
                "workspace_fallback_used": workspace_fallback_used,
                "reflexive_interpretation": reflexive_analysis,
                **(getattr(self, "last_context_retrieval", {}) or {}),
            },
            context_details={
                "session_id": self.session_id,
                "framework_root": str(getattr(self, "framework_root", "")),
                "project_root": str(getattr(self, "project_root", self.base_path)),
                "workspace_used": str(self.base_path),
                "workspace_state_root": str(getattr(self, "workspace_state_root", self.base_path / Path(".gabo"))),
                "workspace_scope_root": str(getattr(self, "workspace_scope_root", getattr(self, "project_root", self.base_path))),
                "workspace_mirror_root": str(getattr(self, "workspace_mirror_root", self.base_path)),
                "workspace_id": str(getattr(self, "workspace_id", "")),
                "request_id": str(getattr(self, "last_context_route", {}).get("request_id", "") or ""),
                "context_revision": envelope.envelope_id(),
                "provider_used": self.provider,
                "adapter_used": envelope.adapter or self.provider,
                "runtime_used": envelope.runtime or "unknown",
                "tokens_sent": resp.usage.input_tokens + resp.usage.output_tokens,
                "tokens_reserved": budget.output_reserve,
                "files_represented": envelope.files_represented,
                "fragments_recovered": envelope.retrieved_fragments,
                "considered_fragments": list((getattr(self, "last_context_retrieval", {}) or {}).get("considered_fragments", []) or []),
                "accepted_fragments": list((getattr(self, "last_context_retrieval", {}) or {}).get("accepted_fragments", []) or []),
                "rejected_fragments": list((getattr(self, "last_context_retrieval", {}) or {}).get("rejected_fragments", []) or []),
                "deduplicated_fragments": list((getattr(self, "last_context_retrieval", {}) or {}).get("deduplicated_fragments", []) or []),
                "compressed_fragments": list((getattr(self, "last_context_retrieval", {}) or {}).get("compressed_fragments", []) or []),
                "retrieval_queries": list((getattr(self, "last_context_retrieval", {}) or {}).get("retrieval_queries", []) or []),
                "retrieval_results": list((getattr(self, "last_context_retrieval", {}) or {}).get("retrieval_results", []) or []),
                "cache_hits": list((getattr(self, "last_context_retrieval", {}) or {}).get("cache_hits", []) or []),
                "cache_misses": list((getattr(self, "last_context_retrieval", {}) or {}).get("cache_misses", []) or []),
                "invalidation_causes": list((getattr(self, "last_context_retrieval", {}) or {}).get("invalidation_causes", []) or []),
                "latency_by_source_ms": dict((getattr(self, "last_context_retrieval", {}) or {}).get("latency_by_source_ms", {}) or {}),
                "tokens_by_source": dict((getattr(self, "last_context_retrieval", {}) or {}).get("tokens_by_source", {}) or {}),
                "cost_by_source": dict((getattr(self, "last_context_retrieval", {}) or {}).get("cost_by_source", {}) or {}),
                "contradictions": list((getattr(self, "last_context_retrieval", {}) or {}).get("contradictions", []) or []),
                "assumptions_used": list((getattr(self, "last_context_retrieval", {}) or {}).get("assumptions_used", []) or []),
                "assertions": list((getattr(self, "last_context_retrieval", {}) or {}).get("assertions", []) or []),
                "evidence_by_assertion": list((getattr(self, "last_context_retrieval", {}) or {}).get("evidence_by_assertion", []) or []),
                "tools_executed": tools_executed or list((getattr(self, "last_context_retrieval", {}) or {}).get("tools_executed", []) or []),
                "changes_made": list((getattr(self, "last_context_retrieval", {}) or {}).get("changes_made", []) or []),
                "tests_executed": list((getattr(self, "last_context_retrieval", {}) or {}).get("tests_executed", []) or []),
                "result": {
                    "response_excerpt": final_content[:240],
                    "finish_reason": resp.finish_reason,
                    "claim_warning": claim_warning,
                    "workspace_fallback_used": workspace_fallback_used,
                },
                "verification_state": "verified" if claim_verification.get("verified") and not claim_verification.get("unverified") else "unverified" if claim_verification.get("unverified") else "undetermined",
                "errors": list((getattr(self, "last_context_retrieval", {}) or {}).get("errors", []) or []),
                "limitations": list((getattr(self, "last_context_retrieval", {}) or {}).get("limitations", []) or []),
                "session_summary_loaded": envelope.session_summary,
                "tools_available": envelope.tools_available,
                "warnings": envelope.restrictions,
                "limiting_factor": str(budget.alert_level),
            },
        )
        reflexive_audit = self._record_reflexive_audit(
            receipt=receipt,
            analysis=reflexive_analysis,
            response_content=final_content,
            metadata={
                "tool_rounds": tool_rounds,
                "claim_warning": claim_warning,
                "workspace_fallback_used": workspace_fallback_used,
                "task_contract_ok": bool(task_contract_meta.get("ok", False)),
            },
        )
        receipt.metadata["reflexive_audit"] = reflexive_audit
        receipt.metadata["claim_verification"] = claim_verification
        self.last_receipt = receipt
        self.context_revision = receipt.envelope_id
        self.store.update_meta({
            "context_revision": self.context_revision,
            "last_receipt": receipt.to_dict(),
            "last_envelope": envelope.to_dict(),
        })

        self.store.append_response(
            final_content,
            provider=self.provider,
            model=resp.model_used,
            metadata={
                "finish_reason": resp.finish_reason,
                "envelope_id": receipt.envelope_id,
                "claim_warning": claim_warning,
                "workspace_fallback_used": workspace_fallback_used,
                "task_contract": task_contract_meta,
                "response_state": response_state,
                "provider_error": provider_error,
                "code_task": self.last_code_task,
                "code_task_contract": self.last_code_task_contract,
                "reflexive_interpretation": reflexive_analysis,
                "reflexive_audit": reflexive_audit,
            },
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
                user_message=user_message,
                response=final_content,
                response_time_ms=elapsed_ms,
                tokens_used=resp.usage.total_tokens,
            )

        return final_content

    def orchestrate(self, user_message: str, providers: list[str] | None = None) -> dict[str, dict[str, Any]]:
        """Send the same prompt to active bridges and persist all responses."""
        selected = normalize_bridges(providers or self.active_bridges, primary=self.provider)
        history = self.store.get_history()
        responses: dict[str, dict[str, Any]] = {}
        self.store.append_user(user_message, provider="orchestrator", model="")
        for provider_name in selected:
            cls = ADAPTER_REGISTRY[provider_name]
            adapter = cls(config=self._build_adapter_config(provider_name))
            models = adapter.list_models()
            target_model = self.model if provider_name == self.provider else (models[0].model_id if models else self.model)
            normalized = self.msg_adapter.to_provider(history, provider_name)
            normalized.append({"role": "user", "content": user_message})
            response = adapter.chat(normalized, target_model, system=self.effective_system_prompt(), tools=None)
            failed = bool(response.metadata.get("error")) or response.finish_reason == "error"
            responses[provider_name] = {"ok": not failed, "content": response.content, "model": response.model_used or target_model}
            self.store.append_response(
                response.content,
                provider=provider_name,
                model=response.model_used or target_model,
                metadata={"orchestrated": True, "error": failed, "finish_reason": response.finish_reason},
            )
            self.store.record_tokens(
                provider=provider_name,
                model=response.model_used or target_model,
                tokens_in=response.usage.input_tokens,
                tokens_out=response.usage.output_tokens,
            )
            self.total_tokens += response.usage.total_tokens
            self.total_calls += 1
        return responses

    def send_stream(self, user_message: str, **kwargs: Any):
        """Send a user message with streaming and persist the completed turn."""
        self.last_clarification = None
        self.last_response_state = "running"
        route_info = kwargs.pop("route_info", None) or self.route_user_message(user_message)
        code_task = self._classify_code_request(user_message)
        self.last_code_task = code_task.to_dict() if code_task is not None else None
        self.last_code_task_contract = self._compile_code_task_contract(code_task, objective=user_message) if code_task is not None else None
        if code_task is not None and code_task.blocked:
            yield self.send(user_message, route_info=route_info, **kwargs)
            return

        if route_info.get("kind") == "workspace_question":
            yield self.send(user_message, route_info=route_info, **kwargs)
            return

        adapter = self._ensure_adapter()
        intent = "chat" if route_info.get("kind") == "workspace_question" else classify_intent(user_message)
        self._capture_conversational_goal(user_message, intent)
        try:
            reflexive_analysis = self.analyze_reflexive_turn(user_message)
        except Exception as exc:
            reflexive_analysis = {
                "ok": False,
                "error": str(exc),
                "literal_reading": user_message,
                "intent": intent,
                "confidence": 0.0,
            }

        if (
            self._tool_calling_enabled()
            and adapter.supports_tools()
            and len(self.tool_registry) > 0
            and should_enable_tools(intent)
            and not _requests_no_execution(user_message)
        ):
            result = self.send(user_message, **kwargs)
            yield result
            return

        start = time.time()

        history = self.store.get_history()
        normalized = self._sanitize_provider_history(self.msg_adapter.to_provider(history, self.provider))
        normalized.append({"role": "user", "content": user_message})

        system_prompt = self.effective_system_prompt()
        if intent != "chat":
            system_prompt += "\n\n" + intent_guidance(intent)
            system_prompt += get_few_shot_examples(intent, max_examples=2)
        else:
            system_prompt += "\n\n" + intent_guidance("chat")

        task_contract_block = self._task_response_contract_block(intent, user_message)
        if task_contract_block:
            system_prompt += "\n\n" + task_contract_block

        workspace_block = self._workspace_question_block(user_message) if route_info.get("kind") == "workspace_question" else ""
        if workspace_block:
            system_prompt += "\n\n" + workspace_block

        bc_block = self._bc_policy_block(user_message)
        if bc_block:
            system_prompt += "\n\n" + bc_block

        if code_task is not None and code_task.is_code_request:
            system_prompt += (
                "\n\nCode Forge classifier: "
                f"kind={code_task.kind}; "
                f"targets={', '.join(code_task.target_files) if code_task.target_files else 'none'}; "
                f"blocked={code_task.blocked}"
            )

        if self._needs_task_response_contract(intent):
            yield self.send(user_message, **kwargs)
            return

        rag_fragments, code_context = self._workspace_context_pack(user_message, code_task)
        rag_block = format_rag_context(rag_fragments)
        if rag_block:
            system_prompt += "\n\n" + rag_block

        gabo_block = self._gabo_block()
        if gabo_block:
            system_prompt += "\n\n" + gabo_block

        ctx_tokens = self._get_model_context_tokens()
        budget = compute_budget(
            system_prompt, normalized, None, model_context_tokens=ctx_tokens,
        )
        if budget.is_critical:
            normalized, _, budget = truncate_context(
                system_prompt, normalized, None,
                model_context_tokens=ctx_tokens, preserve_last_n=6,
            )
        self.last_budget_report = budget

        envelope = self._build_context_envelope(
            system_prompt=system_prompt,
            user_message=user_message,
            intent=intent,
            normalized=normalized,
            tools=None,
            budget=budget,
            code_task=code_task,
            code_task_contract=self.last_code_task_contract,
            rag_fragments=rag_fragments,
            code_context=code_context,
            streaming=True,
        )

        buffer = []
        stream_failed = False
        try:
            call_kwargs = self._provider_call_kwargs(intent, kwargs)
            for chunk in adapter.chat_stream(
                envelope.messages,
                self.model,
                system=envelope.system_prompt,
                tools=None,
                **call_kwargs,
            ):
                buffer.append(chunk)
                yield chunk
        except Exception:
            stream_failed = True
            raise
        if stream_failed:
            return

        full_response = "".join(buffer)
        self.last_response_state = "done"
        elapsed_ms = (time.time() - start) * 1000

        est_in = len(user_message) // 4
        est_out = max(len(full_response) // 4, 1)
        claim_verification: dict[str, Any] = {
            "claims": [],
            "verified": [],
            "inferred": [],
            "assumed": [],
            "unverified": [],
            "contradicted": [],
            "disputed": [],
            "obsolete": [],
            "undetermined": [],
            "evidence_items": [],
            "verified_without_evidence_blocked": [],
        }
        if hasattr(self, "claim_verifier") and self.claim_verifier:
            try:
                claim_payload: dict[str, Any] = {}
                if isinstance(full_response, str) and full_response.strip().startswith("{"):
                    try:
                        claim_payload = json.loads(full_response)
                    except Exception:
                        claim_payload = {}
                claims = claim_payload.get("facts") or claim_payload.get("claims") or []
                evidence = claim_payload.get("evidence") or []
                claim_verification = self.claim_verifier.verify(claims, evidence=evidence, response_text=full_response)
            except Exception:
                pass
        receipt = ContextReceipt.from_response(
            envelope=envelope,
            response_content=full_response,
            model_used=self.model,
            finish_reason="stop",
            usage_input=est_in,
            usage_output=est_out,
            usage_total=est_in + est_out,
            latency_ms=elapsed_ms,
            extra_metadata={
                "intent": intent,
                "streaming": True,
                "response_state": "done",
                "reflexive_interpretation": reflexive_analysis,
                "claim_verification": claim_verification,
                **(getattr(self, "last_context_retrieval", {}) or {}),
            },
            context_details={
                "session_id": self.session_id,
                "framework_root": str(getattr(self, "framework_root", "")),
                "project_root": str(getattr(self, "project_root", self.base_path)),
                "workspace_used": str(self.base_path),
                "workspace_state_root": str(getattr(self, "workspace_state_root", self.base_path / Path(".gabo"))),
                "workspace_scope_root": str(getattr(self, "workspace_scope_root", getattr(self, "project_root", self.base_path))),
                "workspace_mirror_root": str(getattr(self, "workspace_mirror_root", self.base_path)),
                "workspace_id": str(getattr(self, "workspace_id", "")),
                "request_id": str(getattr(self, "last_context_route", {}).get("request_id", "") or ""),
                "context_revision": envelope.envelope_id(),
                "provider_used": self.provider,
                "adapter_used": envelope.adapter or self.provider,
                "runtime_used": envelope.runtime or "unknown",
                "tokens_sent": est_in + est_out,
                "tokens_reserved": budget.output_reserve,
                "files_represented": envelope.files_represented,
                "fragments_recovered": envelope.retrieved_fragments,
                "considered_fragments": list((getattr(self, "last_context_retrieval", {}) or {}).get("considered_fragments", []) or []),
                "accepted_fragments": list((getattr(self, "last_context_retrieval", {}) or {}).get("accepted_fragments", []) or []),
                "rejected_fragments": list((getattr(self, "last_context_retrieval", {}) or {}).get("rejected_fragments", []) or []),
                "deduplicated_fragments": list((getattr(self, "last_context_retrieval", {}) or {}).get("deduplicated_fragments", []) or []),
                "compressed_fragments": list((getattr(self, "last_context_retrieval", {}) or {}).get("compressed_fragments", []) or []),
                "retrieval_queries": list((getattr(self, "last_context_retrieval", {}) or {}).get("retrieval_queries", []) or []),
                "retrieval_results": list((getattr(self, "last_context_retrieval", {}) or {}).get("retrieval_results", []) or []),
                "cache_hits": list((getattr(self, "last_context_retrieval", {}) or {}).get("cache_hits", []) or []),
                "cache_misses": list((getattr(self, "last_context_retrieval", {}) or {}).get("cache_misses", []) or []),
                "invalidation_causes": list((getattr(self, "last_context_retrieval", {}) or {}).get("invalidation_causes", []) or []),
                "latency_by_source_ms": dict((getattr(self, "last_context_retrieval", {}) or {}).get("latency_by_source_ms", {}) or {}),
                "tokens_by_source": dict((getattr(self, "last_context_retrieval", {}) or {}).get("tokens_by_source", {}) or {}),
                "cost_by_source": dict((getattr(self, "last_context_retrieval", {}) or {}).get("cost_by_source", {}) or {}),
                "contradictions": list((getattr(self, "last_context_retrieval", {}) or {}).get("contradictions", []) or []),
                "assumptions_used": list((getattr(self, "last_context_retrieval", {}) or {}).get("assumptions_used", []) or []),
                "assertions": list((getattr(self, "last_context_retrieval", {}) or {}).get("assertions", []) or []),
                "evidence_by_assertion": list((getattr(self, "last_context_retrieval", {}) or {}).get("evidence_by_assertion", []) or []),
                "tools_executed": list((getattr(self, "last_context_retrieval", {}) or {}).get("tools_executed", []) or []),
                "changes_made": list((getattr(self, "last_context_retrieval", {}) or {}).get("changes_made", []) or []),
                "tests_executed": list((getattr(self, "last_context_retrieval", {}) or {}).get("tests_executed", []) or []),
                "result": {
                    "response_excerpt": full_response[:240],
                    "finish_reason": "stop",
                    "streaming": True,
                },
                "verification_state": "verified" if claim_verification.get("verified") and not claim_verification.get("unverified") else "unverified" if claim_verification.get("unverified") else "undetermined",
                "errors": list((getattr(self, "last_context_retrieval", {}) or {}).get("errors", []) or []),
                "limitations": list((getattr(self, "last_context_retrieval", {}) or {}).get("limitations", []) or []),
                "session_summary_loaded": envelope.session_summary,
                "tools_available": envelope.tools_available,
                "warnings": envelope.restrictions,
                "limiting_factor": str(budget.alert_level),
            },
        )
        reflexive_audit = self._record_reflexive_audit(
            receipt=receipt,
            analysis=reflexive_analysis,
            response_content=full_response,
            metadata={"streaming": True},
        )
        receipt.metadata["reflexive_audit"] = reflexive_audit
        receipt.metadata["claim_verification"] = claim_verification
        self.last_receipt = receipt
        self.context_revision = receipt.envelope_id

        self.store.append_user(user_message, provider=self.provider, model=self.model)
        self.store.append_response(
            full_response,
            provider=self.provider,
            model=self.model,
            metadata={
                "finish_reason": "stop",
                "envelope_id": receipt.envelope_id,
                "budget_alert": str(budget.alert_level),
                "reflexive_interpretation": reflexive_analysis,
                "reflexive_audit": reflexive_audit,
                "code_task": self.last_code_task,
                "code_task_contract": self.last_code_task_contract,
                "response_state": "done",
            },
        )
        est_tokens = max(len(full_response) // 4, 1)
        self.store.record_tokens(
            provider=self.provider,
            model=self.model,
            tokens_in=len(user_message) // 4,
            tokens_out=est_tokens,
        )
        self.total_tokens += est_tokens
        self.total_calls += 1
        if bool(self.config.get("features.rl_learning", True)):
            self.rl_feedback.implicit(
                session_id=self.session_id,
                provider=self.provider,
                model=self.model,
                user_message=user_message,
                response=full_response,
                response_time_ms=elapsed_ms,
                tokens_used=est_tokens,
            )

        self.store.update_meta({
            "context_revision": self.context_revision or receipt.envelope_id,
            "last_receipt": receipt.to_dict(),
            "last_envelope": envelope.to_dict(),
        })
