"""translation_adapter.py — Wrap de un ProviderAdapter que aplica el
translation_middleware. Se construye y se enchufa en _init_adapter()
cuando el modelo activo está en la lista de modelos a traducir.
"""
from __future__ import annotations

import json
import time
from typing import Any, Iterator

import translation_middleware as tm
from bago_core.providers import HealthStatus, ModelInfo, ProviderAdapter, ProviderResponse


class TranslationAdapter(ProviderAdapter):
    """Envuelve un ProviderAdapter y traduce ES↔EN según `cfg`.

    - `chat(messages, model, ...)`: traduce el último mensaje user ES→EN
      si está en español, llama al adapter subyacente, y traduce la
      respuesta EN→ES.
    - `chat_stream(messages, model, ...)`: igual, pero acumula los chunks
      de la respuesta, los traduce al final, y emite el resultado como
      un único yield. (El modelo traductor no streamea para mantener
      simple; el chunk traducido se emite tras la traducción completa.)
    """

    def __init__(self, inner: ProviderAdapter, cfg: dict, *, source_lang: str = "es"):
        super().__init__(inner.provider_name, getattr(inner, "config", None))
        self._inner = inner
        self._cfg = cfg
        self._source_lang = source_lang  # idioma del usuario (default: español)
        self._last_translation_info: dict[str, Any] = {}
        self._target_model: str = ""  # el modelo subyacente que se está envolviendo

    def _maybe_unload_target(self, model: str) -> None:
        """Tras usar el modelo subyacente, intenta descargarlo de Ollama
        para liberar RAM. No falla si no se puede; loguea el resultado
        en el translation_info del siguiente turno.
        """
        if not self._cfg.get("unload_target_after_use", True):
            return
        if not model:
            return
        # No descargar el modelo traductor (es nuestro aliado)
        translator = str(self._cfg.get("translator_model", ""))
        if model == translator:
            return
        try:
            import urllib.request
            import json as _json
            base = str(self._cfg.get("translator_base_url", "http://127.0.0.1:11434"))
            body = _json.dumps({"model": model, "keep_alive": 0}).encode()
            req = urllib.request.Request(
                f"{base}/api/generate", data=body,
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=5) as r:
                # Ollama devuelve JSON con `done: true` cuando libera
                _ = r.read()
        except Exception as exc:
            # No es crítico; loguear para diagnóstico
            import sys
            print(f"[translation_middleware] unload fallo para {model}: {exc}", file=sys.stderr)

    # ─── Propiedades delegadas ────────────────────────────────────

    def is_configured(self) -> bool:
        return self._inner.is_configured()

    def supports_tools(self) -> bool:
        # Si traducimos, las tools con nombres en inglés pueden dar problemas.
        # Devolvemos False para que el caller NO active tool_calling cuando
        # el middleware está activo. Es la opción segura.
        return False

    def supports_streaming(self) -> bool:
        # Devolvemos False: el wrap traduce al final y emite un único yield.
        # Si el caller hace fallback a chat() (no stream), funcionará bien.
        return False

    def supports_embeddings(self) -> bool:
        return self._inner.supports_embeddings()

    def list_models(self) -> list[ModelInfo]:
        return self._inner.list_models()

    def health_check(self, timeout: float = 5.0) -> HealthStatus:
        return self._inner.health_check(timeout=timeout)

    # ─── Núcleo: traducción + delegación ──────────────────────────

    def _maybe_translate_input(self, messages: list[dict], system: str) -> tuple[list[dict], str, list[dict]]:
        """Traduce los mensajes user al inglés (target del modelo subyacente)."""
        if not self._cfg.get("enabled", True):
            return messages, system, []
        new_messages, infos = tm.translate_messages_input(messages, self._cfg)
        new_system, sys_info = tm.translate(system, target_lang="en", cfg=self._cfg)
        infos = [sys_info] + infos
        return new_messages, new_system, infos

    def _maybe_translate_output(self, text: str) -> tuple[str, dict]:
        """Traduce la respuesta del inglés al idioma del usuario.

        Si la respuesta ya está en el idioma del usuario, no se traduce.
        Esto cubre el caso de un usuario que escribió en inglés y obtuvo
        una respuesta en inglés: no se hace trabajo extra.
        """
        if not self._cfg.get("enabled", True):
            return text, {"translated": False, "skipped": True, "reason": "disabled"}
        # Detección previa: si el output ya está en el idioma del usuario,
        # saltamos la traducción para no malgastar tiempo del traductor.
        src = tm.detect_language(text)
        if src == self._source_lang and self._cfg.get("skip_if_same_language", True):
            return text, {
                "translated": False,
                "skipped": True,
                "reason": f"output_already_{self._source_lang}",
                "src_lang": src,
                "dst_lang": self._source_lang,
            }
        return tm.translate(text, target_lang=self._source_lang, cfg=self._cfg)

    def chat(
        self,
        messages: list[dict],
        model: str,
        *,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        tools: list[dict] | None = None,
    ) -> ProviderResponse:
        # 1. Pre-traducción
        new_messages, new_system, infos_in = self._maybe_translate_input(messages, system)

        # 2. Llamada subyacente
        self._target_model = model
        resp = self._inner.chat(
            new_messages, model,
            system=new_system, temperature=temperature,
            max_tokens=max_tokens, stream=False, tools=None,
        )

        # 3. Post-traducción
        translated_text, info_out = self._maybe_translate_output(resp.content or "")
        self._last_translation_info = {
            "input": infos_in,
            "output": info_out,
            "model_active": model,
        }

        # 4. Liberar RAM del modelo subyacente (granite3.2 = ~5GB)
        self._maybe_unload_target(model)

        # 5. Reconstruir respuesta con texto traducido
        if resp.content and info_out.get("translated"):
            return ProviderResponse(
                content=translated_text,
                model_used=resp.model_used,
                finish_reason=resp.finish_reason,
                usage=resp.usage,
                metadata={
                    **resp.metadata,
                    "translation_middleware": self._last_translation_info,
                },
            )
        return resp

    def chat_stream(
        self,
        messages: list[dict],
        model: str,
        *,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
    ):
        """Streaming: el modelo subyacente streamea en EN, acumulamos y
        traducimos al final. Emitimos un único yield con la respuesta
        traducida (o sin traducir si no aplica).
        """
        new_messages, new_system, infos_in = self._maybe_translate_input(messages, system)
        buffer: list[str] = []
        self._target_model = model
        for chunk in self._inner.chat_stream(
            new_messages, model,
            system=new_system, temperature=temperature,
            max_tokens=max_tokens, tools=None,
        ):
            buffer.append(chunk)
            # OJO: aquí NO emitimos los chunks EN al caller, porque el
            # usuario vería inglés mientras el modelo responde. Acumulamos
            # y emitimos la traducción al final. Si la traducción falla,
            # emitimos el texto EN crudo.
        full_en = "".join(buffer)
        if not full_en.strip():
            return
        translated, info_out = self._maybe_translate_output(full_en)
        self._last_translation_info = {
            "input": infos_in,
            "output": info_out,
            "model_active": model,
        }
        # Liberar RAM del modelo subyacente
        self._maybe_unload_target(model)
        yield translated

    def get_last_translation_info(self) -> dict[str, Any]:
        return self._last_translation_info
