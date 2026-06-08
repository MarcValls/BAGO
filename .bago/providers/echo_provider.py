#!/usr/bin/env python3
"""
echo_provider.py — BAGO Demo / Offline Provider Adapter

Provider de demostración que siempre está disponible.
No requiere credenciales, red, ni software externo.
Útil para probar BAGO en una instalación limpia antes de configurar providers reales.
"""

from __future__ import annotations

import sys
import os

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from provider_adapter import ProviderAdapter, ModelInfo, ProviderResponse, TokenUsage, HealthStatus


class EchoAdapter(ProviderAdapter):
    """Adapter demo que repite/parafasea el input del usuario. Siempre disponible."""

    def __init__(self, config: dict | None = None):
        super().__init__("echo", config)

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
        """Genera una respuesta demo basada en el último mensaje del usuario."""
        if not messages:
            content = "(echo) No recibí ningún mensaje."
        else:
            last = messages[-1].get("content", "")
            if not last or not last.strip():
                content = "(echo) Recibí un mensaje vacío."
            else:
                # Respuestas demo según el contenido
                lower = last.strip().lower()
                if any(w in lower for w in ("hola", "hello", "hi", "hey", "buenas")):
                    content = (
                        "¡Hola! Soy el provider de demostración de BAGO.\n\n"
                        "Actualmente estás usando el modo 'echo', que no conecta con ningún modelo de IA real.\n"
                        "Para usar BAGO con un modelo real, tenés estas opciones:\n"
                        "  1. Instalar Ollama localmente (gratis, privado)\n"
                        "  2. Configurar GitHub Copilot (si tenés suscripción)\n"
                        "  3. Configurar OpenRouter, Anthropic u otro provider cloud\n\n"
                        "Escribí /switch para abrir el asistente de providers."
                    )
                elif any(w in lower for w in ("help", "ayuda", "como", "cómo", "?")):
                    content = (
                        "Comandos útiles para empezar:\n"
                        "  /switch      — Cambiar de provider/modelo\n"
                        "  /providers   — Ver providers disponibles\n"
                        "  /credentials set — Registrar una API key\n"
                        "  /status      — Ver estado actual\n"
                        "  /help        — Ayuda completa\n\n"
                        "Para salir del modo demo, configurá un provider real con /switch."
                    )
                elif lower.startswith("/"):
                    content = f"(echo) Comando recibido: {last.strip()}"
                else:
                    content = (
                        f"Recibí: '{last[:200]}'\n\n"
                        "(Este es el provider de demostración. No estoy procesando tu mensaje con un modelo real. "
                        "Configurá un provider desde el menú para obtener respuestas de IA.)"
                    )

        usage = TokenUsage(input_tokens=len(str(messages)), output_tokens=len(content), total_tokens=len(str(messages)) + len(content))
        return ProviderResponse(
            content=content,
            model_used=model or "echo-v1",
            provider=self.provider_name,
            finish_reason="stop",
            usage=usage,
        )

    def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(
                model_id="echo-v1",
                wire_name="echo-v1",
                provider=self.provider_name,
                context_tokens=8192,
                max_output_tokens=4096,
                best_for="demo",
                cost="free",
                available=True,
            ),
        ]

    def health_check(self, timeout: float = 5.0) -> HealthStatus:
        return HealthStatus(ok=True, provider=self.provider_name, detail="Demo provider siempre disponible", latency_ms=0.0, models_available=1)

    def is_configured(self) -> bool:
        return True  # Siempre disponible, sin configuración

    def supports_tools(self) -> bool:
        return False

    def supports_streaming(self) -> bool:
        return False


def _run_tests() -> int:
    adapter = EchoAdapter()
    assert adapter.provider_name == "echo"
    assert adapter.is_configured()
    assert len(adapter.list_models()) == 1

    resp = adapter.chat([{"role": "user", "content": "hola"}], "echo-v1")
    assert "provider de demostración" in resp.content
    assert resp.provider == "echo"

    resp2 = adapter.chat([{"role": "user", "content": "/help"}], "echo-v1")
    assert "Comandos útiles" in resp2.content

    print("echo_provider.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
