#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
session_manager.py — BAGO 4.1.5 Session Manager

Orquesta todo el ciclo de vida de una sesión de chat:
- Carga/guarda contexto via ContextStore
- Mantiene el provider/modelo activo
- Coordina switches con SwitchEngine
- Expone la API que usa el REPL.

El SessionManager es la única puerta de entrada al core desde el chat.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
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
from context_store import ContextStore, ContextMessage, TimelineEvent
from context_compressor import ContextCompressor, LayerStore
from state_paths import resolve_state_root
from model_equivalence import EquivalenceMap, TransferVerdict, TransferStrategy
from message_adapter import MessageAdapter
from rl_engine import FeedbackCollector, PreferenceModel
from config_manager import ConfigManager
from credential_manager import CredentialManager
from script_registry import ScriptRegistry
from tool_registry import ToolRegistry
from intent_engine import classify_intent, should_enable_tools, get_few_shot_examples, intent_guidance
from plan_engine import PlanEngine
from agent_gateway import AgentGateway
from knowledge_base import KnowledgeBase
from embedding_store import EmbeddingStore

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "providers"))
from ollama_local import OllamaLocalAdapter
from ollama_cloud import OllamaCloudAdapter
from copilot import CopilotAdapter
from anthropic import AnthropicAdapter
from codex import CodexAdapter
from openrouter import OpenRouterAdapter
from opencode import OpenCodeAdapter
from cpp_local import CppLocalAdapter
from provider_adapter import ProviderAdapter, ProviderResponse


# Registry de adapters disponibles
ADAPTER_REGISTRY: dict[str, type[ProviderAdapter]] = {
    "ollama-local": OllamaLocalAdapter,
    "ollama-cloud": OllamaCloudAdapter,
    "copilot": CopilotAdapter,
    "anthropic": AnthropicAdapter,
    "codex": CodexAdapter,
    "openrouter": OpenRouterAdapter,
    "opencode": OpenCodeAdapter,
    "cpp-local": CppLocalAdapter,
}

BAGO_MODES: dict[str, str] = {
    "B": "Balanceado: aclara objetivo, alcance, riesgos y criterio de exito.",
    "A": "Adaptativo: inspecciona el estado real y elige estrategia.",
    "G": "Generativo: produce artefactos utiles y verificables.",
    "O": "Organizativo: verifica, registra estado y deja continuidad.",
}


class SessionManager:
    """Gestiona una sesión de chat multi-provider."""

    def __init__(
        self,
        session_id: str | None = None,
        provider: str = "ollama-local",
        model: str = "qwen2.5:14b",
        base_path: str | None = None,
        state_root: str | None = None,
        system_prompt: str = "",
        bago_mode: str = "B",
        active_agent: str = "default",
        active_bridges: list[str] | None = None,
    ):
        self.session_id = session_id or str(uuid.uuid4())[:12]
        self.provider = provider
        self.model = model
        self.system_prompt = system_prompt
        self.bago_mode = self._normalize_bago_mode(bago_mode)
        self.active_bridges = self._normalize_bridges(active_bridges or [provider], primary=provider)
        self.base_path = Path(base_path or os.getcwd())
        self.state_root = resolve_state_root(state_root)
        self.state_dir = self.state_root
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.config = ConfigManager(base_path=str(self.base_path), state_root=str(self.state_root))
        self.credentials = CredentialManager(base_path=str(self.base_path), state_root=str(self.state_root))

        self.store = ContextStore(self.session_id, base_dir=self.state_dir)
        if not self.store.get_meta():
            self.store.update_meta({
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_provider": "",
                "last_model": "",
                "switch_count": 0,
                "bago_version": "4.1.5",
            })
            self.store.add_timeline_event(TimelineEvent("session", "start", f"Session {self.session_id} created"))
        self.equiv = EquivalenceMap()
        self.msg_adapter = MessageAdapter()
        self.rl_pref = PreferenceModel(base_dir=self.base_path, state_root=str(self.state_root))
        self.rl_feedback = FeedbackCollector(self.rl_pref)
        self.script_registry = ScriptRegistry(repo_root=self.base_path)
        self.tool_registry = ToolRegistry(script_registry=self.script_registry)
        self.plan_engine = PlanEngine()
        self.agent_gateway = AgentGateway()
        self.agent_gateway.activate(active_agent)
        self.knowledge = KnowledgeBase(base_path=str(self.base_path), state_root=str(self.state_root))
        self.embedding_store = EmbeddingStore(base_path=str(self.base_path), state_root=str(self.state_root))
        self._adapter: ProviderAdapter | None = None
        self._init_info: dict = self._init_adapter()

        # Metadata
        self.created_at = time.time()
        self.total_tokens = 0
        self.total_calls = 0
        self.last_switch_at: float | None = None
        self.switch_log: list[dict] = []

        # Pending tool calls (Allow All = False)
        self._pending_tools: list[dict] | None = None
        self._pending_normalized: list[dict] | None = None
        self._pending_user_message: str = ""
        self._pending_tools_kwargs: dict[str, Any] = {}
        self._providers_cache: list[dict[str, Any]] | None = None
        self._providers_cache_at = 0.0
        self._providers_cache_ttl = 30.0

    @staticmethod
    def _normalize_bago_mode(mode: str) -> str:
        normalized = str(mode or "B").strip().upper().strip("[]")
        if normalized not in BAGO_MODES:
            raise ValueError(f"Modo BAGO invalido: {mode}. Usa B, A, G u O.")
        return normalized

    def effective_system_prompt(self) -> str:
        """Compone gobierno BAGO y agente sin alterar provider/modelo."""
        parts = [
            self.system_prompt.strip(),
            (
                f"MODO BAGO ACTIVO [{self.bago_mode}]\n"
                f"- {BAGO_MODES[self.bago_mode]}\n"
                "- La sesion y la evidencia son la fuente de verdad.\n"
                "- El provider y el modelo son motores de ejecucion; no cambies ninguno sin peticion explicita."
            ),
        ]
        agent = self.agent_gateway.active
        if agent.name != "default" or not self.system_prompt.strip():
            parts.append(f"AGENTE ACTIVO [{agent.name}]\n{agent.system_prompt.strip()}")
        return "\n\n".join(part for part in parts if part)

    def set_bago_mode(self, mode: str) -> dict:
        previous = self.bago_mode
        self.bago_mode = self._normalize_bago_mode(mode)
        return {"ok": True, "mode": self.bago_mode, "previous_mode": previous}

    @staticmethod
    def _normalize_bridges(providers: list[str], primary: str = "") -> list[str]:
        normalized: list[str] = []
        for name in ([primary] if primary else []) + list(providers or []):
            clean = str(name or "").strip()
            if clean and clean in ADAPTER_REGISTRY and clean not in normalized:
                normalized.append(clean)
        return normalized

    def set_active_bridges(self, providers: list[str]) -> dict:
        previous = list(self.active_bridges)
        self.active_bridges = self._normalize_bridges(providers, primary=self.provider)
        return {"ok": True, "bridges": list(self.active_bridges), "previous_bridges": previous}

    def _train_bc_policy(self) -> dict:
        """Entrena la política BC (Behavioral Cloning) desde el historial real.
        Capa shadow: solo aprende a recomendar, nunca ejecuta acciones.
        No es fatal: ante cualquier problema devuelve {ok: False, ...}."""
        try:
            bago_core = self.base_path / "bago_core"
            if str(bago_core) not in sys.path:
                sys.path.insert(0, str(bago_core))
            from rl_policies import train_bc_policy, numpy_available

            if not numpy_available():
                return {"ok": False, "reason": "numpy no disponible"}
            report = train_bc_policy(self.base_path, n_actions=4, n_features=4)
            return {"ok": report.get("status") == "trained", **report}
        except Exception as exc:
            return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}

    def auto_evolve(self) -> dict:
        """Ciclo de autoevolución de BAGO.

        Reentrena el clasificador de intenciones con TODO el historial acumulado
        (mismo primitivo que se ejecuta antes de cada compresión de contexto) y
        recarga el dataset few-shot en caliente, de modo que la mejora surte
        efecto en la sesión actual.

        Devuelve un dict:
          {ok: True, message, counts: {intent: n}, total}
        o, ante fallo (culpa técnica explícita):
          {ok: False, message, responsable, causa, prevencion}
        """
        try:
            import intent_engine

            message = self.tool_registry.retrain_intents()
            counts = intent_engine.reload_examples()
            result = {
                "ok": True,
                "message": message,
                "counts": counts,
                "total": sum(counts.values()),
            }
            # Entrenamiento de la política BC desde el historial (capa shadow, nunca ejecuta).
            result["bc"] = self._train_bc_policy()
            return result
        except Exception as exc:
            # Culpa técnica: registrar responsable, causa y prevención (preferencia del usuario)
            return {
                "ok": False,
                "message": f"Autoevolución no completada: {exc}",
                "responsable": "SessionManager.auto_evolve / ToolRegistry.retrain_intents",
                "causa": f"{type(exc).__name__}: {exc}",
                "prevencion": (
                    "Verificar acceso de lectura a la base de sesiones "
                    "(~/.copilot/session-store.db) y permisos de escritura en "
                    "~/.bago/state/intent_examples.json"
                ),
            }

    def _build_adapter_config(self, provider_name: str | None = None) -> dict:
        """Construye dict de config para el adapter activo desde ConfigManager + CredentialManager."""
        target_provider = provider_name or self.provider
        cfg = self.config.provider_config(target_provider)
        creds = {}
        for key in self.credentials.required_keys(target_provider):
            val = self.credentials.get(target_provider, key)
            if val:
                creds[key] = val
                # Alias estándar para compatibilidad con adapters
                upper = key.upper()
                if "API_KEY" in upper or "KEY" in upper:
                    creds.setdefault("api_key", val)
                if "TOKEN" in upper:
                    creds.setdefault("token", val)
                if "URL" in upper and "BASE" in upper:
                    creds.setdefault("base_url", val)
                if upper == "OLLAMA_CLOUD_URL":
                    creds.setdefault("base_url", val)
        # Merge: credenciales tienen prioridad sobre config generica
        merged = dict(cfg)
        merged.update(creds)
        merged.setdefault("base_path", str(self.base_path))
        return merged

    @staticmethod
    def _model_quality_key(model_id: str) -> tuple[float, int, int]:
        match = re.search(r"(\d+(?:\.\d+)?)b\b", model_id.lower())
        size_score = float(match.group(1)) if match else 0.0
        latest_bonus = 1 if ":latest" in model_id.lower() else 0
        return (size_score, latest_bonus, len(model_id))

    def _select_fallback_model(self, available: list[str]) -> str:
        if not available:
            return self.model
        preferred = self.config.default_model
        if preferred in available:
            return preferred
        return max(available, key=self._model_quality_key)

    def _init_adapter(self) -> dict:
        """Inicializa adapter y auto-corrige modelo si no está disponible.

        Retorna dict con: corrected (bool), requested (str), actual (str), available (list).
        """
        cls = ADAPTER_REGISTRY.get(self.provider)
        if cls is None:
            raise ValueError(f"Provider '{self.provider}' no registrado.")
        adapter_config = self._build_adapter_config()
        self._adapter = cls(config=adapter_config)
        available = self.list_models(self.provider)
        corrected = False
        requested = self.model
        if available and self.model not in available:
            self.model = self._select_fallback_model(available)
            corrected = True
        return {
            "corrected": corrected,
            "requested": requested,
            "actual": self.model,
            "available": available,
        }

    def _ensure_adapter(self) -> ProviderAdapter:
        if self._adapter is None:
            self._init_info = self._init_adapter()
        return self._adapter  # type: ignore[return-value]

    def _tool_calling_enabled(self) -> bool:
        return bool(self.config.get("features.tool_calling", False))

    # ── Core API ──────────────────────────────────────────────────────

    def send(self, user_message: str, **kwargs: Any) -> str:
        """Envía mensaje al provider activo y guarda respuesta en contexto.

        Si el provider soporta tools y hay herramientas registradas, las pasa
        al modelo. Si el modelo responde con tool_calls, las ejecuta y reenvía
        automáticamente para obtener la respuesta final.
        """
        adapter = self._ensure_adapter()
        start = time.time()

        # Normalizar mensajes para el provider destino
        history = self.store.get_history()
        normalized = self.msg_adapter.to_provider(history, self.provider)
        normalized.append({"role": "user", "content": user_message})

        # --- Auto-training intent engine ----------------------------------
        intent = classify_intent(user_message)
        dynamic_system = self.effective_system_prompt()
        if intent != "chat":
            dynamic_system += "\n\n" + intent_guidance(intent)
            dynamic_system += get_few_shot_examples(intent, max_examples=2)
        else:
            dynamic_system += "\n\n" + intent_guidance("chat")

        # Pasar tools solo si la intención NO es chat
        tools = None
        if (
            self._tool_calling_enabled()
            and adapter.supports_tools()
            and len(self.tool_registry) > 0
            and should_enable_tools(intent)
        ):
            tools = self.tool_registry.to_openai()

        # Llamar al provider
        resp: ProviderResponse = adapter.chat(
            normalized,
            self.model,
            system=dynamic_system,
            tools=tools,
            **kwargs,
        )

        self.store.append_user(user_message, provider=self.provider, model=self.model)

        # Si el modelo pidió tool calls, ejecutarlas y reenviar
        if resp.tool_calls:
            # Guardar el assistant message con tool_calls
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

            # Si auto_allow_tools es False, pausar para aprobación
            if not self.config.get("features.auto_allow_tools", True):
                self._pending_tools = resp.tool_calls
                self._pending_normalized = normalized.copy()
                self._pending_user_message = user_message
                self._pending_tools_kwargs = kwargs.copy()
                lines = ["⏸️ El modelo quiere usar estas herramientas:"]
                for tc in resp.tool_calls:
                    func = tc.get("function", {})
                    lines.append(f"  • {func.get('name', 'unknown')}: {func.get('arguments', '{}')}")
                lines.append("\nEscribe /allow para ejecutarlas o /deny para rechazarlas.")
                return "\n".join(lines)

            # Ejecutar cada tool call
            for tc in resp.tool_calls:
                call = self.tool_registry.parse_tool_calls({"tool_calls": [tc]})[0]
                result = self.tool_registry.execute_call(call)
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

            # Reenviar al modelo con los resultados
            resp = adapter.chat(
                normalized,
                self.model,
                system=self.effective_system_prompt(),
                tools=tools,
                **kwargs,
            )

        elapsed_ms = (time.time() - start) * 1000

        # Guardar en contexto universal
        self.store.append_response(
            resp.content,
            provider=self.provider,
            model=resp.model_used,
            metadata={
                "finish_reason": resp.finish_reason,
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

        # RL: recompensa implícita
        self.rl_feedback.implicit(
            session_id=self.session_id,
            provider=self.provider,
            model=resp.model_used or self.model,
            user_message=user_message,
            response=resp.content,
            response_time_ms=elapsed_ms,
            tokens_used=resp.usage.total_tokens,
        )

        return resp.content

    def orchestrate(self, user_message: str, providers: list[str] | None = None) -> dict[str, dict[str, Any]]:
        """Envia el mismo mensaje a los bridges activos y persiste todas las respuestas."""
        selected = self._normalize_bridges(providers or self.active_bridges, primary=self.provider)
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
        """Envía mensaje al provider con streaming real.

        Yield chunks de texto (str). Al finalizar, persiste el historial
        completo y registra tokens/RL automáticamente.
        """
        adapter = self._ensure_adapter()

        # Si hay herramientas registradas y el adapter las soporta,
        # el streaming con tool calls es complejo; delegamos a send().
        if self._tool_calling_enabled() and adapter.supports_tools() and len(self.tool_registry) > 0:
            result = self.send(user_message, **kwargs)
            yield result
            return

        start = time.time()

        history = self.store.get_history()
        normalized = self.msg_adapter.to_provider(history, self.provider)
        normalized.append({"role": "user", "content": user_message})

        buffer = []
        stream_failed = False
        try:
            for chunk in adapter.chat_stream(
                normalized,
                self.model,
                system=self.effective_system_prompt(),
                tools=None,
                **kwargs,
            ):
                buffer.append(chunk)
                yield chunk
        except Exception:
            stream_failed = True
            raise
        if stream_failed:
            return

        full_response = "".join(buffer)
        elapsed_ms = (time.time() - start) * 1000
        self.store.append_user(user_message, provider=self.provider, model=self.model)
        # Persistir
        self.store.append_response(
            full_response,
            provider=self.provider,
            model=self.model,
            metadata={"finish_reason": "stop"},
        )
        # Estimar tokens (heurística: ~4 chars/token)
        est_tokens = max(len(full_response) // 4, 1)
        self.store.record_tokens(
            provider=self.provider,
            model=self.model,
            tokens_in=len(user_message) // 4,
            tokens_out=est_tokens,
        )
        self.total_tokens += est_tokens
        self.total_calls += 1
        # RL implícito
        self.rl_feedback.implicit(
            session_id=self.session_id,
            provider=self.provider,
            model=self.model,
            user_message=user_message,
            response=full_response,
            response_time_ms=elapsed_ms,
            tokens_used=est_tokens,
        )

    def approve_tools(self) -> str:
        """Ejecuta las tool calls pendientes y reenvía al modelo.

        Retorna la respuesta final del modelo.
        """
        if not self._pending_tools or not self._pending_normalized:
            return "No hay herramientas pendientes de aprobación."

        adapter = self._ensure_adapter()
        tools = None
        if adapter.supports_tools() and len(self.tool_registry) > 0:
            tools = self.tool_registry.to_openai()

        # Ejecutar cada tool call pendiente
        for tc in self._pending_tools:
            call = self.tool_registry.parse_tool_calls({"tool_calls": [tc]})[0]
            result = self.tool_registry.execute_call(call)
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

        # Reenviar al modelo con los resultados
        resp = adapter.chat(
            self._pending_normalized,
            self.model,
            system=self.effective_system_prompt(),
            tools=tools,
            **self._pending_tools_kwargs,
        )

        # Persistir respuesta final
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

        # RL implícito
        self.rl_feedback.implicit(
            session_id=self.session_id,
            provider=self.provider,
            model=resp.model_used or self.model,
            user_message=self._pending_user_message,
            response=resp.content,
            response_time_ms=0,
            tokens_used=resp.usage.total_tokens,
        )

        # Limpiar estado pendiente
        self._pending_tools = None
        self._pending_normalized = None
        self._pending_user_message = ""
        self._pending_tools_kwargs = {}

        return resp.content

    def deny_tools(self) -> str:
        """Rechaza las tool calls pendientes y limpia el estado."""
        if not self._pending_tools:
            return "No hay herramientas pendientes de aprobación."

        self.store.append_message(ContextMessage(
            role="system",
            content="[El usuario rechazó la ejecución de herramientas]",
        ))

        self._pending_tools = None
        self._pending_normalized = None
        self._pending_user_message = ""
        self._pending_tools_kwargs = {}
        return "Herramientas rechazadas."

    def feedback(self, rating: float, user_message: str = "") -> None:
        """Registra feedback explícito del usuario para la última interacción."""
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

    def switch(self, new_provider: str, new_model: str | None = None, force: bool = False) -> dict:
        """Cambia de provider/modelo con validación de equivalencia.

        Retorna dict con: ok, verdict, warnings, old_provider, new_provider.
        """
        if new_provider not in ADAPTER_REGISTRY:
            return {"ok": False, "error": f"Provider '{new_provider}' no registrado."}

        old_provider = self.provider
        old_model = self.model
        new_model = new_model or self.model  # Mantener modelo anterior si no se especifica

        # Validar equivalencia
        verdict = self.equiv.transfer_verdict(old_model, new_model)
        warnings: list[str] = []

        if verdict == TransferVerdict.NOT_RECOMMENDED and not force:
            warnings.append(
                f"Switch de {old_model} → {new_model} no recomendado. "
                "Usa force=True para forzar."
            )
            return {
                "ok": False,
                "verdict": verdict.name,
                "warnings": warnings,
                "old_provider": old_provider,
                "new_provider": new_provider,
            }

        # Preparar adaptación de contexto si hay cambio de formato
        strategy = TransferStrategy.recommended(verdict)
        if strategy != TransferStrategy.DIRECT:
            self.store.record_switch(old_provider, old_model, new_provider, new_model, reason=strategy.name)
            warnings.append(f"Contexto adaptado con estrategia: {strategy.name}")

            # Compresión por capas para downgrade
            if strategy in (TransferStrategy.COMPRESS, TransferStrategy.REHYDRATE):
                # Reentrenar intenciones con todo el historial acumulado antes de compactar
                try:
                    retrain_msg = self.tool_registry.retrain_intents()
                    warnings.append(retrain_msg)
                except Exception:
                    pass
                compressor = ContextCompressor(target_tokens=4096)
                history = self.store.get_history()
                layers = compressor.build_layers(history)
                layer_store = LayerStore(str(self.base_path))
                layer_store.save_layers(layers, self.session_id)
                compressed = compressor.compress_layers(layers)
                # Reescribir contexto con historial comprimido
                self.store.clear_history()
                for msg in compressor.to_history(compressed):
                    self.store.append_message(ContextMessage(
                        role=msg["role"],
                        content=msg["content"],
                        metadata=msg.get("metadata", {}),
                    ))
                warnings.append(f"Contexto comprimido por capas: {len(layers)} → {len(compressed)} capas")

        # Instanciar nuevo adapter
        self.provider = new_provider
        self.model = new_model
        self.active_bridges = self._normalize_bridges(self.active_bridges, primary=new_provider)
        self._init_info = self._init_adapter()
        self._providers_cache = None
        self._providers_cache_at = 0.0
        self.last_switch_at = time.time()

        entry = {
            "at": self.last_switch_at,
            "from": {"provider": old_provider, "model": old_model},
            "to": {"provider": new_provider, "model": new_model},
            "verdict": verdict.name,
            "strategy": strategy.name,
        }
        self.switch_log.append(entry)

        return {
            "ok": True,
            "verdict": verdict.name,
            "warnings": warnings,
            "old_provider": old_provider,
            "new_provider": new_provider,
        }

    def status(self) -> dict:
        """Estado actual de la sesión."""
        adapter = self._ensure_adapter()
        health = adapter.health_check()
        return {
            "session_id": self.session_id,
            "provider": self.provider,
            "model": self.model,
            "bago_mode": self.bago_mode,
            "active_agent": self.agent_gateway.active.name,
            "active_bridges": list(self.active_bridges),
            "health": {
                "ok": health.ok,
                "detail": health.detail,
                "latency_ms": health.latency_ms,
            },
            "messages": len(self.store.get_history()),
            "total_tokens": self.total_tokens,
            "total_calls": self.total_calls,
            "created_at": self.created_at,
            "last_switch_at": self.last_switch_at,
            "switches": len(self.switch_log),
        }

    def activate_agent(self, name: str) -> dict:
        """Activa un agente especializado.

        Retorna dict con: ok, agent, previous_agent, warnings.
        """
        try:
            previous = self.agent_gateway.active.name
            agent = self.agent_gateway.activate(name)
            warnings: list[str] = []

            # Si el agente prefiere provider/modelo, sugerir cambio
            if agent.preferred_provider and agent.preferred_provider != self.provider:
                warnings.append(f"Agente '{name}' prefiere provider: {agent.preferred_provider}")
            if agent.preferred_model and agent.preferred_model != self.model:
                warnings.append(f"Agente '{name}' prefiere modelo: {agent.preferred_model}")

            return {
                "ok": True,
                "agent": agent.name,
                "previous_agent": previous,
                "warnings": warnings,
            }
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

    def available_providers(self) -> list[dict]:
        """Lista providers registrados con estado de configuración."""
        if self._providers_cache is not None and (time.time() - self._providers_cache_at) < self._providers_cache_ttl:
            return [
                {"name": item["name"], "configured": item["configured"], "models": list(item["models"])}
                for item in self._providers_cache
            ]

        result = []
        for name, cls in ADAPTER_REGISTRY.items():
            try:
                inst = cls(config=self._build_adapter_config(name))
            except TypeError:
                inst = cls()
            except Exception:
                result.append({"name": name, "configured": False, "models": []})
                continue
            try:
                configured = inst.is_configured()
            except Exception:
                configured = False
            models: list[str] = []
            if configured or name == self.provider:
                try:
                    models = [m["id"] for m in self.list_model_catalog(name)]
                except Exception:
                    models = []
            result.append({
                "name": name,
                "configured": configured,
                "models": models,
            })
        self._providers_cache = [
            {"name": item["name"], "configured": item["configured"], "models": list(item["models"])}
            for item in result
        ]
        self._providers_cache_at = time.time()
        return result

    def save(self) -> None:
        """Persiste metadata de sesión en disco."""
        self.store.update_meta({
            "last_provider": self.provider,
            "last_model": self.model,
            "bago_mode": self.bago_mode,
            "active_agent": self.agent_gateway.active.name,
            "active_bridges": list(self.active_bridges),
            "switch_count": self.store.get_meta().get("switch_count", 0),
            "last_switch_at": self.last_switch_at,
        })
        path = self.state_dir / "sessions" / f"{self.session_id}.json"
        data = {
            "session_id": self.session_id,
            "provider": self.provider,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "bago_mode": self.bago_mode,
            "active_agent": self.agent_gateway.active.name,
            "active_bridges": list(self.active_bridges),
            "created_at": self.created_at,
            "total_tokens": self.total_tokens,
            "total_calls": self.total_calls,
            "last_switch_at": self.last_switch_at,
            "switch_log": self.switch_log,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def memory_add_hybrid(self, content: str) -> dict[str, Any]:
        adapter = self._ensure_adapter()
        if not adapter.supports_embeddings():
            raise RuntimeError(f"{self.provider} no soporta memoria híbrida")
        vector = adapter.embed([content], model=self.model)[0]
        memory_id = self.knowledge.add(content, source_session=self.session_id)
        try:
            embedding_id = self.embedding_store.add(
                memory_id=str(memory_id),
                content=content,
                vector=vector,
                source_session=self.session_id,
                provider=self.provider,
                model=self.model,
            )
        except Exception:
            self.knowledge.delete(memory_id)
            raise
        return {"memory_id": memory_id, "embedding_id": embedding_id}

    def memory_search_hybrid(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        adapter = self._ensure_adapter()
        if not adapter.supports_embeddings():
            raise RuntimeError(f"{self.provider} no soporta memoria híbrida")
        query_vector = adapter.embed([query], model=self.model)[0]
        return self.embedding_store.search(query_vector=query_vector, limit=limit)

    def close(self) -> None:
        """Cierra conexiones abiertas (Knowledge Base, etc.)."""
        if hasattr(self, "knowledge") and self.knowledge:
            self.knowledge.close()
        if hasattr(self, "embedding_store") and self.embedding_store:
            self.embedding_store.close()

    @property
    def adapters(self) -> dict[str, type[ProviderAdapter]]:
        return ADAPTER_REGISTRY.copy()

    @classmethod
    def load(cls, session_id: str, base_path: str | None = None, state_root: str | None = None) -> "SessionManager":
        """Carga una sesión desde disco."""
        bp = Path(base_path or os.getcwd())
        sr = resolve_state_root(state_root)
        legacy_root = bp / ".bago" / "state"
        path = sr / "sessions" / f"{session_id}.json"
        if not path.exists():
            legacy_path = legacy_root / "sessions" / f"{session_id}.json"
            if legacy_path.exists():
                path = legacy_path
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            mgr = cls(
                session_id=data["session_id"],
                provider=data["provider"],
                model=data["model"],
                base_path=str(bp),
                state_root=str(sr),
                system_prompt=data.get("system_prompt", ""),
                bago_mode=data.get("bago_mode", "B"),
                active_agent=data.get("active_agent", "default"),
                active_bridges=data.get("active_bridges"),
            )
            mgr.total_tokens = data.get("total_tokens", 0)
            mgr.total_calls = data.get("total_calls", 0)
            mgr.last_switch_at = data.get("last_switch_at")
            mgr.switch_log = data.get("switch_log", [])
            return mgr

        store_base = sr
        if not (sr / "sessions" / f"{session_id}.json").exists() and (legacy_root / "sessions" / f"{session_id}.json").exists():
            store_base = legacy_root
        store = ContextStore.load(session_id, base_dir=store_base)
        meta = store.get_meta()
        defaults = ConfigManager(base_path=str(bp), state_root=str(sr))
        provider = meta.get("last_provider") or defaults.default_provider
        model = meta.get("last_model") or defaults.default_model
        mgr = cls(
            session_id=session_id,
            provider=provider,
            model=model,
            base_path=str(bp),
            state_root=str(sr),
            system_prompt=meta.get("system_prompt", ""),
            bago_mode=meta.get("bago_mode", "B"),
            active_agent=meta.get("active_agent", "default"),
            active_bridges=meta.get("active_bridges"),
        )
        mgr.store = store
        token_summary = store.get_token_summary()
        mgr.total_tokens = sum(
            int(model_data.get("in", 0)) + int(model_data.get("out", 0))
            for provider_data in token_summary.values()
            for model_data in provider_data.values()
        )
        mgr.total_calls = sum(
            int(model_data.get("calls", 0))
            for provider_data in token_summary.values()
            for model_data in provider_data.values()
        )
        mgr.last_switch_at = meta.get("last_switch_at")
        mgr.switch_log = meta.get("switch_log", [])
        return mgr

    def list_models(self, provider: str | None = None) -> list[str]:
        """Lista modelos del provider activo o del especificado."""
        return [item["id"] for item in self.list_model_catalog(provider)]

    def list_model_catalog(self, provider: str | None = None, mode: str | None = None) -> list[dict[str, Any]]:
        """Lista modelos con metadata y filtro opcional por disponibilidad."""
        target = provider or self.provider
        cls = ADAPTER_REGISTRY.get(target)
        if cls is None:
            return []
        try:
            inst = cls(config=self._build_adapter_config(target))
        except TypeError:
            inst = cls()
        mode = mode or str(self.config.get("model_catalog.mode", "all"))
        catalog = []
        for item in inst.list_models():
            available = bool(getattr(item, "available", True))
            record = {
                "id": item.model_id,
                "wire_name": item.wire_name,
                "provider": item.provider,
                "context_tokens": item.context_tokens,
                "max_output_tokens": item.max_output_tokens,
                "best_for": item.best_for,
                "cost": item.cost,
                "available": available,
            }
            if mode == "available-only" and not available:
                continue
            catalog.append(record)
        return catalog


# ── Quick test ──────────────────────────────────────────────────────

def _run_tests() -> int:
    import tempfile
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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

    class MockCppRuntimeHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def _write_json(self, payload: dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                self._write_json({"ok": True, "detail": "mock cpp-local", "models_available": 1})
                return
            if self.path == "/models":
                self._write_json({"models": [{"id": "bago-cpp:stub"}]})
                return
            self._write_json({"error": "not found"}, status=404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            if self.path == "/chat_stream":
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                for line in (b'{"delta":"hola "}\n', b'{"delta":"stream"}\n', b'{"done":true}\n'):
                    self.wfile.write(line)
                    self.wfile.flush()
                return
            if self.path == "/embed":
                texts = [str(item) for item in list(payload.get("texts") or [])]
                vectors = []
                for text in texts:
                    base = 0.9 if "directorio" in text.lower() else 0.1
                    vectors.append([base, 0.0, 0.0])
                self._write_json({"embeddings": vectors})
                return
            if self.path == "/chat":
                messages = list(payload.get("messages") or [])
                has_tool_result = any(item.get("role") == "tool" for item in messages if isinstance(item, dict))
                user_text = ""
                for item in reversed(messages):
                    if isinstance(item, dict) and item.get("role") == "user":
                        user_text = str(item.get("content", ""))
                        break
                if has_tool_result:
                    tool_content = next(
                        (str(item.get("content", "")) for item in reversed(messages)
                         if isinstance(item, dict) and item.get("role") == "tool"),
                        "",
                    )
                    self._write_json({
                        "content": f"Tool integrado: {tool_content}",
                        "model_used": "bago-cpp:stub",
                        "finish_reason": "stop",
                        "usage": {"input_tokens": 4, "output_tokens": 4, "total_tokens": 8, "calls": 1},
                    })
                    return
                if payload.get("tools") and "directorio" in user_text.lower():
                    self._write_json({
                        "content": "",
                        "model_used": "bago-cpp:stub",
                        "finish_reason": "tool_calls",
                        "usage": {"input_tokens": 4, "output_tokens": 1, "total_tokens": 5, "calls": 1},
                        "tool_calls": [{
                            "id": "call-1",
                            "type": "function",
                            "function": {"name": "list_directory", "arguments": "{\"path\":\".\"}"},
                        }],
                    })
                    return
                self._write_json({
                    "content": f"cpp-local::{user_text}",
                    "model_used": "bago-cpp:stub",
                    "finish_reason": "stop",
                    "usage": {"input_tokens": 3, "output_tokens": 3, "total_tokens": 6, "calls": 1},
                })

        def log_message(self, format: str, *args: Any) -> None:
            return

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

        server = ThreadingHTTPServer(("127.0.0.1", 0), MockCppRuntimeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            hybrid = SessionManager(base_path=td, state_root=str(state_root), provider="cpp-local", model="bago-cpp:stub")
            hybrid.config.set("providers.cpp-local.enabled", True)
            hybrid.config.set("providers.cpp-local.base_url", f"http://127.0.0.1:{server.server_port}")
            hybrid.config.set("providers.cpp-local.supports_streaming", True)
            hybrid.config.set("providers.cpp-local.supports_tools", True)
            hybrid.config.set("providers.cpp-local.supports_embeddings", True)
            hybrid._adapter = None
            hybrid._init_info = hybrid._init_adapter()

            assert hybrid.send("hola") == "cpp-local::hola"
            assert "".join(hybrid.send_stream("streaming")) == "hola stream"
            hybrid.config.set("features.tool_calling", True)
            hybrid.config.set("features.auto_allow_tools", True)
            tool_reply = hybrid.send("ejecuta lista directorio con herramienta")
            assert "Tool integrado:" in tool_reply
            hybrid_result = hybrid.memory_add_hybrid("directorio estable")
            assert hybrid_result["embedding_id"] > 0
            hybrid_hits = hybrid.memory_search_hybrid("directorio")
            assert hybrid_hits[0]["memory_id"] == str(hybrid_result["memory_id"])
            hybrid.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

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
