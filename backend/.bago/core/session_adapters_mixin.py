#!/usr/bin/env python3
"""session_adapters_mixin.py — Adapter management mixin for SessionManager.

Extracted from session_manager.py during modularization.
Contains adapter config building, adapter init/correction, provider listing,
model catalog, and provider switching with context compression.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session_utils import ADAPTER_REGISTRY, normalize_bridges, model_quality_key
from context_compressor import ContextCompressor, LayerStore
from context_store import ContextMessage
from model_equivalence import TransferVerdict, TransferStrategy
from provider_adapter import ProviderAdapter
from translation_adapter import TranslationAdapter
import translation_middleware as _tm


class SessionAdaptersMixin:
    """Mixin: adapter lifecycle, provider listing, model catalog, switching."""

    def _build_adapter_config(self, provider_name: str | None = None) -> dict:
        """Construye dict de config para el adapter activo desde ConfigManager + CredentialManager."""
        target_provider = provider_name or self.provider
        cfg = self.config.provider_config(target_provider)
        creds = {}
        for key in self.credentials.required_keys(target_provider):
            val = self.credentials.get(target_provider, key)
            if val:
                creds[key] = val
                upper = key.upper()
                if "API_KEY" in upper or "KEY" in upper:
                    creds.setdefault("api_key", val)
                if "TOKEN" in upper:
                    creds.setdefault("token", val)
                if "URL" in upper and "BASE" in upper:
                    creds.setdefault("base_url", val)
                if upper == "OLLAMA_CLOUD_URL":
                    creds.setdefault("base_url", val)
        merged = dict(cfg)
        merged.update(creds)
        merged.setdefault("base_path", str(self.base_path))
        merged.setdefault("timeout_seconds", self.config.get("timeout_seconds", 60.0))
        return merged

    def _init_adapter(self) -> dict:
        """Inicializa adapter y auto-corrige modelo si no está disponible.

        Retorna dict con: corrected (bool), requested (str), actual (str), available (list).
        """
        cls = ADAPTER_REGISTRY.get(self.provider)
        if cls is None:
            raise ValueError(f"Provider '{self.provider}' no registrado.")
        adapter_config = self._build_adapter_config()
        adapter = cls(config=adapter_config)
        available = self.list_models(self.provider)
        corrected = False
        requested = self.model
        if available and self.model not in available:
            self.model = self._select_fallback_model(available)
            corrected = True

        # ── Translation middleware ────────────────────────────────────────
        # Si el modelo activo está en la lista de modelos a traducir, envolvemos
        # el adapter con TranslationAdapter. El middleware traduce ES↔EN usando
        # el modelo traductor configurado.
        tm_cfg = _tm.load_config(
            self.config.get("translation_middleware", {}) if self.config else {}
        )
        if _tm.should_translate_for(self.model, tm_cfg.get("target_models", [])):
            # Modelos en la lista pueden ser lentos (granite3.2:8b ~90s).
            # Subimos el timeout del adapter subyacente para no cortar antes
            # de que el modelo termine.
            try:
                if hasattr(adapter, "timeout_seconds"):
                    current = float(getattr(adapter, "timeout_seconds", 60.0))
                    target = float(tm_cfg.get("adapter_timeout_s", 180.0))
                    if current < target:
                        adapter.timeout_seconds = target
            except Exception:
                pass
            # Pre-cargar el modelo subyacente con un keep_alive largo en
            # background (no bloqueamos el switch; granite3.2 tarda 3-5min
            # en arrancar desde cero).
            try:
                _keep = int(tm_cfg.get("target_keep_alive_minutes", 30))
                if _keep > 0:
                    import threading as _thr
                    import urllib.request as _ur
                    import json as _j
                    _model = self.model
                    _base = str(tm_cfg.get("translator_base_url", "http://127.0.0.1:11434"))
                    def _preload():
                        try:
                            body = _j.dumps({
                                "model": _model,
                                "prompt": "hi",
                                "stream": False,
                                "options": {"num_predict": 1},
                                "keep_alive": f"{_keep}m",
                            }).encode()
                            req = _ur.Request(
                                f"{_base}/api/generate", data=body,
                                headers={"Content-Type": "application/json"},
                                method="POST")
                            with _ur.urlopen(req, timeout=300) as r:
                                _ = r.read()
                        except Exception as exc:
                            import sys
                            print(f"[translation_middleware] preload fail {_model}: {exc}", file=sys.stderr)
                    _thr.Thread(target=_preload, daemon=True).start()
            except Exception:
                pass

            adapter = TranslationAdapter(adapter, tm_cfg)
            self._translation_middleware_active = True
        else:
            self._translation_middleware_active = False

        self._adapter = adapter
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

    def _select_fallback_model(self, available: list[str]) -> str:
        if not available:
            return self.model
        preferred = self.config.default_model
        if preferred in available:
            return preferred
        return max(available, key=model_quality_key)

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

    def invalidate_providers_cache(self) -> None:
        """Invalida el cache de providers. Llamar tras POST /providers/configure."""
        self._providers_cache = None
        self._providers_cache_at = 0.0

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

    def switch(self, new_provider: str, new_model: str | None = None, force: bool = False) -> dict:
        """Cambia de provider/modelo con validación de equivalencia.

        Retorna dict con: ok, verdict, warnings, old_provider, new_provider.
        """
        if new_provider not in ADAPTER_REGISTRY:
            return {"ok": False, "error": f"Provider '{new_provider}' no registrado."}

        old_provider = self.provider
        old_model = self.model
        new_model = new_model or self.model

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

        strategy = TransferStrategy.recommended(verdict)
        if strategy != TransferStrategy.DIRECT:
            self.store.record_switch(old_provider, old_model, new_provider, new_model, reason=strategy.name)
            warnings.append(f"Contexto adaptado con estrategia: {strategy.name}")

            if strategy in (TransferStrategy.COMPRESS, TransferStrategy.REHYDRATE) and bool(self.config.get("features.compression_on_downgrade", True)):
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
                self.store.clear_history()
                for msg in compressor.to_history(compressed):
                    self.store.append_message(ContextMessage(
                        role=msg["role"],
                        content=msg["content"],
                        metadata=msg.get("metadata", {}),
                    ))
                warnings.append(f"Contexto comprimido por capas: {len(layers)} → {len(compressed)} capas")
            elif strategy in (TransferStrategy.COMPRESS, TransferStrategy.REHYDRATE):
                warnings.append("Compresión por downgrade desactivada en config; se conserva el historial original.")

        self.provider = new_provider
        self.model = new_model
        self.active_bridges = normalize_bridges(self.active_bridges, primary=new_provider)
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
        self._record_backend_activity(
            "function_change",
            f"Cambio de función: {old_provider}/{old_model} → {new_provider}/{new_model}",
            detail=f"strategy={strategy.name}; verdict={verdict.name}",
        )

        return {
            "ok": True,
            "verdict": verdict.name,
            "warnings": warnings,
            "old_provider": old_provider,
            "new_provider": new_provider,
        }

    @property
    def adapters(self) -> dict[str, type[ProviderAdapter]]:
        return ADAPTER_REGISTRY.copy()
