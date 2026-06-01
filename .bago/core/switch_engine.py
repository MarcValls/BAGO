#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
switch_engine.py — BAGO 4.1.5 Switch Engine

Motor de cambio de provider/modelo.
- Valida configuración del destino
- Revisa equivalencia y sugiere modelos
- Adapta contexto si es necesario
- Commit del cambio vía SessionManager

Este módulo encapsula toda la lógica de /switch para mantener
SessionManager limpio y testeable.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from enum import Enum
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
from model_equivalence import EquivalenceMap, TransferVerdict, TransferStrategy
from provider_adapter import ProviderAdapter, ModelInfo, HealthStatus, ProviderResponse


class SwitchError(Exception):
    pass


@dataclass
class SwitchResult:
    ok: bool
    message: str
    old_provider: str
    old_model: str
    new_provider: str
    new_model: str
    verdict: TransferVerdict
    warnings: list[str]
    suggestions: list[str]
    strategy: TransferStrategy


class SwitchEngine:
    """Motor de cambio de provider con lógica de equivalencia."""

    def __init__(self, adapter_registry: dict[str, Any]):
        self._adapters = adapter_registry
        self.equiv = EquivalenceMap()

    @property
    def adapters(self) -> dict[str, Any]:
        return self._adapters

    @adapters.setter
    def adapters(self, value: dict[str, Any]) -> None:
        self._adapters = value

    def validate_target(self, provider: str, model: str | None) -> tuple[bool, str]:
        """Valida si el provider/modelo destino es usable."""
        if provider not in self.adapters:
            return False, f"Provider '{provider}' no registrado."

        adapter_cls = self.adapters[provider]
        adapter = adapter_cls()
        if not adapter.is_configured():
            return False, f"Provider '{provider}' no está configurado (faltan credenciales)."

        if model:
            available = {m.model_id for m in adapter.list_models()}
            if available and model not in available:
                return False, f"Modelo '{model}' no disponible en '{provider}'. Disponibles: {available}"
        return True, "OK"

    def suggest_models(self, current_model: str, target_provider: str) -> list[str]:
        """Sugiere modelos equivalentes en el provider destino."""
        adapter_cls = self.adapters.get(target_provider)
        if not adapter_cls:
            return []
        adapter = adapter_cls()
        candidates = adapter.list_models()
        if not candidates:
            return []

        # Ordenar por equivalencia: mismo tier primero
        current_tier = self.equiv.get_tier(current_model)
        scored = []
        for m in candidates:
            t = self.equiv.get_tier(m.model_id)
            score = 0
            if t == current_tier:
                score = 100
            elif t is not None and current_tier is not None:
                score = 100 - abs(t - current_tier) * 30
            scored.append((score, m.model_id))

        scored.sort(key=lambda x: (-x[0], x[1]))
        return [m for _, m in scored[:5]]

    def prepare_switch(
        self,
        current_provider: str,
        current_model: str,
        new_provider: str,
        new_model: str | None,
        force: bool = False,
    ) -> SwitchResult:
        """Prepara y valida un switch, sin ejecutarlo."""
        warnings: list[str] = []
        suggestions: list[str] = []

        # Validar destino
        ok, msg = self.validate_target(new_provider, new_model)
        if not ok:
            return SwitchResult(
                ok=False, message=msg,
                old_provider=current_provider, old_model=current_model,
                new_provider=new_provider, new_model=new_model or "",
                verdict=TransferVerdict.NOT_RECOMMENDED,
                warnings=[], suggestions=[], strategy=TransferStrategy.DIRECT,
            )

        # Si no se dio modelo, sugerir
        if not new_model:
            suggestions = self.suggest_models(current_model, new_provider)
            if suggestions:
                new_model = suggestions[0]
                warnings.append(f"Modelo no especificado; usando sugerido: {new_model}")
            else:
                return SwitchResult(
                    ok=False, message="No se pudo determinar modelo destino.",
                    old_provider=current_provider, old_model=current_model,
                    new_provider=new_provider, new_model="",
                    verdict=TransferVerdict.NOT_RECOMMENDED,
                    warnings=[], suggestions=[], strategy=TransferStrategy.DIRECT,
                )

        # Veredicto de equivalencia
        verdict = self.equiv.transfer_verdict(current_model, new_model)
        strategy = TransferStrategy.recommended(verdict)

        if verdict == TransferVerdict.NOT_RECOMMENDED and not force:
            return SwitchResult(
                ok=False,
                message=f"Switch no recomendado: {current_model} → {new_model}. Usa --force para forzar.",
                old_provider=current_provider, old_model=current_model,
                new_provider=new_provider, new_model=new_model,
                verdict=verdict, warnings=[], suggestions=suggestions, strategy=strategy,
            )

        if verdict == TransferVerdict.DOWNGRADE:
            warnings.append(f"Downgrade detectado ({current_model} → {new_model}). Posible pérdida de matices.")
        elif verdict == TransferVerdict.UPGRADE:
            warnings.append(f"Upgrade detectado ({current_model} → {new_model}). El nuevo modelo puede reinterpretar contexto anterior.")
        elif verdict == TransferVerdict.EQUIVALENT:
            warnings.append(f"Transferencia equivalente ({current_model} → {new_model}).")

        if strategy != TransferStrategy.DIRECT:
            warnings.append(f"Se aplicará estrategia de contexto: {strategy.name}")

        return SwitchResult(
            ok=True,
            message=f"Switch validado: {current_provider}/{current_model} → {new_provider}/{new_model}",
            old_provider=current_provider, old_model=current_model,
            new_provider=new_provider, new_model=new_model,
            verdict=verdict, warnings=warnings, suggestions=suggestions, strategy=strategy,
        )

    def execute(
        self,
        session_manager: Any,
        new_provider: str,
        new_model: str | None,
        force: bool = False,
    ) -> SwitchResult:
        """Ejecuta el switch completo sobre un SessionManager."""
        result = self.prepare_switch(
            session_manager.provider,
            session_manager.model,
            new_provider,
            new_model,
            force=force,
        )
        if not result.ok:
            return result

        # Delegar al SessionManager
        switch_result = session_manager.switch(result.new_provider, result.new_model, force=force)
        if not switch_result.get("ok"):
            return SwitchResult(
                ok=False, message=switch_result.get("error", "Switch falló"),
                old_provider=result.old_provider, old_model=result.old_model,
                new_provider=result.new_provider, new_model=result.new_model,
                verdict=result.verdict, warnings=result.warnings,
                suggestions=result.suggestions, strategy=result.strategy,
            )

        return SwitchResult(
            ok=True,
            message=f"Switch completado: {result.old_provider}/{result.old_model} → {result.new_provider}/{result.new_model}",
            old_provider=result.old_provider, old_model=result.old_model,
            new_provider=result.new_provider, new_model=result.new_model,
            verdict=result.verdict, warnings=result.warnings,
            suggestions=result.suggestions, strategy=result.strategy,
        )


# ── Quick test ──────────────────────────────────────────────────────

def _run_tests() -> int:
    # Mock adapter para tests independientes de red
    class MockAdapter(ProviderAdapter):
        def __init__(self, config=None):
            super().__init__("mock", config)
        def chat(self, messages, model, *, system="", temperature=0.7, max_tokens=None, stream=False, tools=None):
            return ProviderResponse(content="mock", provider="mock", model_used=model)
        def list_models(self):
            return [
                ModelInfo("llama32", "llama32", "mock", 128000, 8192, "general", "free"),
                ModelInfo("llama32-1b", "llama32-1b", "mock", 128000, 4096, "classification", "free"),
            ]
        def health_check(self, timeout=5.0):
            return HealthStatus(ok=True, provider="mock")
        def is_configured(self):
            return True
        def supports_tools(self):
            return True
        def supports_streaming(self):
            return True

    registry = {"mock": MockAdapter}
    engine = SwitchEngine(registry)

    # Test validación destino no registrado
    ok, msg = engine.validate_target("fantasma", None)
    assert not ok and "no registrado" in msg

    # Test sugerencias (mock tiene 1 modelo)
    sugs = engine.suggest_models("mock-m", "mock")
    assert isinstance(sugs, list)

    # Test prepare equivalent
    res = engine.prepare_switch("mock", "llama32", "mock", "llama32", force=True)
    assert res.ok
    assert res.verdict == TransferVerdict.EQUIVALENT

    # Test prepare downgrade
    res = engine.prepare_switch("mock", "llama32", "mock", "llama32-1b", force=True)
    assert res.ok
    assert res.verdict == TransferVerdict.DOWNGRADE

    print("switch_engine.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
