"""handlers_vision.py — POST /vision for the BAGO HTTP bridge.

Accepts a base64-encoded image and a prompt, sends them to a vision
model via Ollama's /api/generate endpoint (stream=false), and returns
the textual description without blocking the main HTTP thread.

Configuration (all read from ~/.bago/state/config.json, no hardcoded values):
  providers.ollama-local.base_url  — Ollama base URL (fallback: OLLAMA_HOST env var)
  vision.model                     — vision model name (fallback: "minicpm-v")
  vision.timeout_s                 — timeout in seconds (fallback: 180)
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _config_path() -> Path:
    return Path.home() / ".bago" / "state" / "config.json"


def _load_config() -> dict:
    p = _config_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _ollama_base_url(cfg: dict) -> str:
    """Read Ollama base URL from config, then OLLAMA_HOST env, else raise."""
    url = (
        cfg.get("providers", {}).get("ollama-local", {}).get("base_url", "")
        or os.environ.get("OLLAMA_HOST", "")
    ).rstrip("/")
    if not url:
        raise RuntimeError(
            "No se encontró la URL de Ollama en la configuración "
            "(providers.ollama-local.base_url) ni en la variable de entorno OLLAMA_HOST."
        )
    return url


def _ollama_models_paths(cfg: dict) -> list[str]:
    """Return user-configured model root paths (may be empty)."""
    raw = cfg.get("ollama", {}).get("models_path", "")
    if not raw:
        return []
    # Support comma-separated list for users with multiple locations
    return [p.strip() for p in str(raw).split(",") if p.strip()]


def _vision_defaults(cfg: dict, ollama_url: str, extra_roots: list[str]) -> tuple[str, float]:
    """Return (vision_model, timeout_s).

    Model resolution order:
      1. config vision.model  (user-set, takes priority)
      2. auto-discover: API /api/tags + disk scan (including ollama.models_path)
         filtering by known vision model families
      3. Nothing found → RuntimeError asking user to configure vision.model.
    """
    vision_cfg = cfg.get("vision", {})
    timeout_s = float(vision_cfg.get("timeout_s") or 180.0)

    explicit_model = str(vision_cfg.get("model") or "").strip()
    if explicit_model:
        return explicit_model, timeout_s

    # Auto-discover using API + disk (includes user-configured models path)
    try:
        from ollama_discovery import discover_ollama_model_names  # noqa: PLC0415
        model_names = discover_ollama_model_names(
            base_url=ollama_url,
            extra_roots=extra_roots if extra_roots else None,
        )
    except Exception as exc:
        raise RuntimeError(
            f"No se pudo descubrir modelos de Ollama ({ollama_url}): {exc}. "
            "Configura 'vision.model' en ~/.bago/state/config.json."
        ) from exc

    VISION_FAMILIES = (
        "minicpm-v", "llava", "moondream", "bakllava", "cogvlm",
        "vision", "qwen-vl", "internvl", "phi-3-vision", "pixtral",
    )
    for name in model_names:
        if any(family in name.lower() for family in VISION_FAMILIES):
            return name, timeout_s

    raise RuntimeError(
        "No se encontró ningún modelo de visión instalado. "
        "Instala uno compatible (llava, minicpm-v, moondream…) o configura "
        "'vision.model' en ~/.bago/state/config.json."
    )


def _call_ollama_vision(
    ollama_url: str,
    image_base64: str,
    prompt: str,
    model: str,
    timeout_s: float,
    result_holder: list,
) -> None:
    """Thread target: call Ollama /api/generate and store result in result_holder[0]."""
    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "images": [image_base64],
            "stream": False,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{ollama_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8")
            result_holder.append({"ok": True, "raw": raw})
    except Exception as exc:  # noqa: BLE001
        result_holder.append({"ok": False, "error": str(exc)})


def handle(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    from request_context import RequestContext  # noqa: PLC0415

    ctx = RequestContext(handler)

    cfg = _load_config()

    # Resolve Ollama URL from config (never hardcoded)
    try:
        ollama_url = _ollama_base_url(cfg)
    except RuntimeError as exc:
        ctx.send_json({"ok": False, "error": str(exc)}, status=503)
        return

    # Resolve vision model from config or auto-discover from Ollama
    extra_roots = _ollama_models_paths(cfg)
    try:
        default_model, default_timeout = _vision_defaults(cfg, ollama_url, extra_roots)
    except RuntimeError as exc:
        ctx.send_json({"ok": False, "error": str(exc)}, status=503)
        return

    image_base64: str = str(body.get("image_base64") or "").strip()
    prompt: str = str(
        body.get("prompt") or "¿Qué se ve en esta imagen? Descríbela brevemente en español."
    ).strip()
    model: str = str(body.get("model") or default_model).strip()
    timeout_s: float = float(body.get("timeout_s") or default_timeout)

    if not image_base64:
        ctx.send_json({"ok": False, "error": "image_base64 es requerido"}, status=400)
        return

    started = time.time()
    result_holder: list = []
    thread = threading.Thread(
        target=_call_ollama_vision,
        args=(ollama_url, image_base64, prompt, model, timeout_s, result_holder),
        daemon=True,
    )
    thread.start()
    thread.join(timeout=timeout_s + 5.0)  # +5 s de gracia

    elapsed_ms = int((time.time() - started) * 1000)

    if not result_holder:
        ctx.send_json(
            {
                "ok": False,
                "error": f"Timeout: el modelo de visión ({model}) no respondió en {int(timeout_s)}s",
                "duration_ms": elapsed_ms,
            },
            status=504,
        )
        return

    result = result_holder[0]
    if not result.get("ok"):
        ctx.send_json(
            {
                "ok": False,
                "error": result.get("error", "Error desconocido en el modelo de visión"),
                "duration_ms": elapsed_ms,
            },
            status=502,
        )
        return

    try:
        data = json.loads(result["raw"])
        response_text = data.get("response", "")
        ctx.send_json(
            {
                "ok": True,
                "response": response_text,
                "model": data.get("model", model),
                "duration_ms": elapsed_ms,
                "eval_count": data.get("eval_count"),
            }
        )
    except Exception as exc:  # noqa: BLE001
        ctx.send_json(
            {
                "ok": False,
                "error": f"No se pudo parsear la respuesta de Ollama: {exc}",
                "duration_ms": elapsed_ms,
            },
            status=502,
        )
