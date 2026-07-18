"""handlers_providers.py — GET /providers + POST /providers/configure.

GET /providers  — returns provider list enriched with description/state.
POST /providers/configure — enable/disable a provider, set URL or API key.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler

_PROVIDER_META = {
    "ollama-local":   {"description": "Ollama local (CPU/GPU)",      "icon": "local"},
    "ollama-cloud":   {"description": "Ollama Cloud",                 "icon": "cloud"},
    "anthropic":      {"description": "Anthropic Claude (API key)",   "icon": "cloud"},
    "openai":         {"description": "OpenAI GPT (API key)",         "icon": "cloud"},
    "copilot":        {"description": "GitHub Copilot",               "icon": "cloud"},
    "codex":          {"description": "OpenAI Codex",                 "icon": "cloud"},
    "openrouter":     {"description": "OpenRouter (API key)",         "icon": "cloud"},
    "opencode":       {"description": "OpenCode (local server)",      "icon": "local"},
    "cpp-local":      {"description": "llama.cpp local server",       "icon": "local"},
}


def _mgr(handler):
    from api_state import get_mgr
    return get_mgr(handler)


def _config_path() -> "Path":
    from pathlib import Path
    return Path.home() / ".bago" / "state" / "config.json"


def _load_config() -> dict:
    import json
    p = _config_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_config(cfg: dict) -> None:
    import json, os
    p = _config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(str(tmp), str(p))


def _provider_secret_ref(provider_id: str, kind: str = "api_key") -> str:
    """Referencia al secreto en el SecretStore. No contiene el secreto."""
    return f"bago://secrets/providers/{provider_id}/{kind}"


def _store_secret(provider_id: str, secret: str) -> str:
    """Guarda un secreto en el SecretStore y devuelve la referencia."""
    from secret_store import get_secret_store
    get_secret_store().set_secret(f"providers/{provider_id}/api_key", secret)
    return _provider_secret_ref(provider_id)


def _provider_state(configured: bool, name: str) -> str:
    if configured:
        return "confirmed"
    local_providers = {"ollama-local", "cpp-local", "opencode"}
    if name in local_providers:
        return "pending"
    return "blocked"


def _provider_config(mgr, provider_name: str) -> dict:
    config_manager = getattr(mgr, "config", None) if mgr is not None else None
    if config_manager is not None:
        try:
            return dict(config_manager.provider_config(provider_name))
        except (AttributeError, TypeError, ValueError):
            pass
    return dict(_load_config().get("providers", {}).get(provider_name, {}))


def _has_provider_secret(provider_name: str) -> bool:
    try:
        from secret_store import get_secret_store
        return get_secret_store().has_secret(f"providers/{provider_name}/api_key")
    except (ImportError, OSError, RuntimeError):
        return False


def build_providers_payload(mgr) -> dict:
    """Serializa el registro real de adapters para API y bootstrap UI."""
    raw_providers = mgr.available_providers()
    cfg = getattr(mgr, "config", None)
    mode = cfg.get("model_catalog.mode", "all") if cfg else "all"

    enriched = []
    for provider in raw_providers:
        name = provider.get("name", "")
        meta = _PROVIDER_META.get(name, {})
        configured = bool(provider.get("configured", False))
        provider_cfg = _provider_config(mgr, name)
        enabled = bool(provider_cfg.get("enabled", name == "ollama-local"))
        has_secret = _has_provider_secret(name)
        models = [str(model) for model in provider.get("models", []) if str(model).strip()]
        enriched.append({
            "id": name,
            "name": name,
            "description": meta.get("description", name),
            "state": "disabled" if not enabled else _provider_state(configured, name),
            "enabled": enabled,
            "configured": configured,
            "base_url": str(provider_cfg.get("base_url", "")),
            "default_model": str(provider_cfg.get("default_model", "")),
            "has_secret": has_secret,
            "models": models,
            "modelCount": len(models),
            "models_source": "session-manager",
        })
    return {"providers": enriched, "mode": mode}


def handle(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json
    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {
            "providers": [],
            "mode": "unavailable",
            "error": "SessionManager no disponible; el registro real no puede resolverse",
        })
        return

    send_json(handler, 200, build_providers_payload(mgr))


def handle_configure(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """POST /providers/configure — update provider config.

    Reglas de seguridad:
      - api_key NO se guarda en config.json. Va al SecretStore (DPAPI en
        Windows, cifrado por usuario del SO).
      - config.json solo guarda `secret_ref` con la ruta lógica.
      - Si llega api_key vacía, se conserva la referencia previa.
      - Si llega `clear_secret=true`, se borra del SecretStore.
    """
    from api_serializers import send_json

    provider_name = str(body.get("provider", "")).strip()
    if not provider_name or provider_name.lower() == "none":
        send_json(handler, 400, {"error": "provider requerido"})
        return

    mgr = _mgr(handler)
    p_cfg = _provider_config(mgr, provider_name)

    if "enabled" in body:
        p_cfg["enabled"] = bool(body["enabled"])
    if "base_url" in body and str(body["base_url"]).strip():
        p_cfg["base_url"] = str(body["base_url"]).strip()
    if "model" in body and str(body["model"]).strip():
        p_cfg["default_model"] = str(body["model"]).strip()

    # ── Secret handling (NO en config.json) ──────────────────────────
    if bool(body.get("clear_secret")):
        from secret_store import get_secret_store
        get_secret_store().delete_secret(f"providers/{provider_name}/api_key")
        p_cfg.pop("secret_ref", None)
    elif "api_key" in body and str(body["api_key"]).strip():
        secret = str(body["api_key"]).strip()
        ref = _store_secret(provider_name, secret)
        p_cfg["secret_ref"] = ref
        # Por compatibilidad legacy, NO se guarda api_key en config.json
        p_cfg.pop("api_key", None)
    elif "secret_ref" in body and str(body["secret_ref"]).strip():
        # Permitir que el cliente apunte a un secreto pre-existente
        p_cfg["secret_ref"] = str(body["secret_ref"]).strip()

    config_manager = getattr(mgr, "config", None) if mgr is not None else None
    if config_manager is not None:
        config_manager.set(f"providers.{provider_name}", p_cfg)
    else:
        cfg = _load_config()
        cfg.setdefault("providers", {})[provider_name] = p_cfg
        _save_config(cfg)

    # Devolver config SIN secretos (secret_ref sí, valor NO)
    safe_cfg = {k: v for k, v in p_cfg.items() if k != "api_key"}
    has_secret = _has_provider_secret(provider_name)
    safe_cfg["has_secret"] = has_secret
    if has_secret:
        safe_cfg.setdefault("secret_ref", _provider_secret_ref(provider_name))

    # Invalidate provider cache in session manager if available
    if mgr is not None:
        try:
            mgr.invalidate_providers_cache()
        except Exception:
            pass

    send_json(handler, 200, {"ok": True, "provider": provider_name, "config": safe_cfg})


def handle_cli_detect(handler: "BaseHTTPRequestHandler") -> None:
    """GET /providers/cli-detect?tool=codex|copilot

    Devuelve si el CLI está instalado y su ruta. Para providers
    auth_delegated_runtime (Codex CLI, Copilot CLI).
    """
    import os
    import shutil
    from urllib.parse import urlparse, parse_qs
    from api_serializers import send_json

    parsed = urlparse(handler.path)
    qs = parse_qs(parsed.query)
    tool = (qs.get("tool") or [""])[0].lower()

    candidates: list[str] = []
    if tool == "codex":
        candidates = ["codex", "codex.cmd", "codex.exe"]
    elif tool == "copilot":
        candidates = ["copilot", "copilot.cmd", "copilot.exe", "gh-copilot"]
    else:
        send_json(handler, 400, {"error": "tool requerido: codex | copilot"})
        return

    found_path = None
    found_via = ""
    for cand in candidates:
        p = shutil.which(cand)
        if p:
            found_path = p
            found_via = "PATH"
            break

    if found_path is None and os.name == "nt":
        appdata = os.environ.get("LOCALAPPDATA", "")
        userprofile = os.environ.get("USERPROFILE", "")
        if tool == "codex":
            extra = [
                os.path.join(appdata, "Programs", "codex", "codex.exe"),
                os.path.join(userprofile, ".codex", "bin", "codex.exe"),
                os.path.join(appdata, "npm", "codex.cmd"),
            ]
        else:
            extra = [
                os.path.join(appdata, "Programs", "GitHub Copilot CLI", "copilot.exe"),
                os.path.join(appdata, "npm", "copilot.cmd"),
            ]
        for p in extra:
            if p and os.path.isfile(p):
                found_path = p
                found_via = "known-path"
                break

    send_json(handler, 200, {
        "tool": tool,
        "installed": bool(found_path),
        "path": found_path,
        "via": found_via,
        "install_hint": {
            "codex": "npm i -g @openai/codex  o  descargar desde https://developers.openai.com/codex",
            "copilot": "gh extension install github/gh-copilot  o  descargar desde https://docs.github.com/copilot/cli",
        }.get(tool, ""),
    })



# ─── Catálogo de discovery (paralelo al del frontend) ─────────────────
# provider_id -> tipo de discovery. Mantener sincronizado con
# frontend/src/shared/provider-catalog.ts.
_DISCOVERY = {
    "ollama-local":  {"type": "ollama_tags",   "path": "/api/tags"},
    "ollama-cloud":  {"type": "openai_models", "path": "/v1/models"},
    "openai":        {"type": "openai_models", "path": "/models"},
    "anthropic":     {"type": "manual"},
    "openrouter":    {"type": "openai_models", "path": "/models"},
    "google-gemini": {"type": "manual"},
    "vertex-ai":     {"type": "manual"},
    "azure-openai":  {"type": "manual"},
    "aws-bedrock":   {"type": "manual"},
    "huggingface":   {"type": "openai_models", "path": "/models"},
    "mistral":       {"type": "openai_models", "path": "/models"},
    "groq":          {"type": "openai_models", "path": "/models"},
    "deepseek":      {"type": "manual"},
    "xai":           {"type": "openai_models", "path": "/models"},
    "llama-cpp-local": {"type": "openai_models", "path": "/models"},
    "vllm-local":    {"type": "openai_models", "path": "/models"},
    "codex":         {"type": "manual"},
    "github-copilot-oauth": {"type": "openai_models", "path": "/models"},
    "github-copilot-cli":   {"type": "manual"},
    "custom-openai-compatible": {"type": "openai_models", "path": "/models"},
}


def _provider_base_url(provider_id: str, cfg: dict) -> str:
    """Devuelve la base_url del provider desde config.json."""
    p = cfg.get("providers", {}).get(provider_id, {})
    url = p.get("base_url", "").strip()
    if url:
        return url.rstrip("/")
    # defaults razonables
    defaults = {
        "ollama-local": "http://localhost:11434",
        "ollama-cloud": "https://ollama.com",
        "openai": "https://api.openai.com/v1",
        "openrouter": "https://openrouter.ai/api/v1",
        "huggingface": "https://router.huggingface.co/v1",
        "mistral": "https://api.mistral.ai/v1",
        "groq": "https://api.groq.com/openai/v1",
        "deepseek": "https://api.deepseek.com",
        "xai": "https://api.x.ai/v1",
        "llama-cpp-local": "http://localhost:8080/v1",
        "vllm-local": "http://localhost:8000/v1",
        "github-copilot-oauth": "https://api.githubcopilot.com",
        "google-gemini": "https://generativelanguage.googleapis.com",
    }
    return defaults.get(provider_id, "")


def _get_api_key(provider_id: str) -> str:
    """Lee la API key del SecretStore."""
    from secret_store import get_secret_store
    return get_secret_store().get_secret(f"providers/{provider_id}/api_key") or ""


def _http_get_json(url: str, headers: dict, timeout: float = 8.0):
    """GET con timeout. Devuelve (data, error_string)."""
    import json
    import urllib.request
    import urllib.error
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        return json.loads(raw.decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return None, f"URL error: {e.reason}"
    except Exception as e:
        return None, str(e)


def _discover_models(provider_id: str) -> tuple[list[str], str | None, str]:
    """Descubre modelos según el tipo configurado. Devuelve (models, error, source)."""
    discovery = _DISCOVERY.get(provider_id, {"type": "manual"})
    kind = discovery.get("type", "manual")

    if kind == "manual":
        # El usuario teclea: devolvemos lista vacía
        return [], None, "manual"

    cfg = _load_config()
    base_url = _provider_base_url(provider_id, cfg)
    if not base_url:
        return [], "Sin base_url configurada", "manual"

    path = discovery.get("path", "/models")
    full_url = f"{base_url}{path}"
    api_key = _get_api_key(provider_id)

    headers = {"Accept": "application/json"}
    if api_key:
        if provider_id == "anthropic":
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
        elif provider_id == "google-gemini":
            # Google Gemini usa ?key=API_KEY
            full_url = f"{full_url}?key={api_key}"
        else:
            headers["Authorization"] = f"Bearer {api_key}"

    data, err = _http_get_json(full_url, headers)
    if err:
        return [], err, kind

    models: list[str] = []
    if isinstance(data, dict):
        if "models" in data and isinstance(data["models"], list):
            for item in data["models"]:
                if isinstance(item, dict):
                    mid = item.get("id") or item.get("name") or item.get("model")
                    if mid:
                        models.append(str(mid))
                elif isinstance(item, str):
                    models.append(item)
        elif "data" in data and isinstance(data["data"], list):
            # Formato OpenAI /v1/models
            for item in data["data"]:
                if isinstance(item, dict):
                    mid = item.get("id") or item.get("name")
                    if mid:
                        models.append(str(mid))
        elif "tags" in data and isinstance(data["tags"], list):
            # Formato Ollama
            for item in data["tags"]:
                if isinstance(item, dict):
                    mid = item.get("name")
                    if mid:
                        models.append(str(mid))
                elif isinstance(item, str):
                    models.append(item)
    return models, None, kind


def handle_list_models(handler: "BaseHTTPRequestHandler", provider_id: str) -> None:
    """GET /providers/<id>/models — lista modelos disponibles del provider."""
    from api_serializers import send_json
    import blacklist_models

    models, err, source = _discover_models(provider_id)
    cfg = _load_config()
    p_cfg = cfg.get("providers", {}).get(provider_id, {})

    # Enriquecer con default_model del config
    default_model = p_cfg.get("default_model", "")
    has_secret = bool(_get_api_key(provider_id))

    # Filtrar la blocklist local. La blocklist es por máquina, no global.
    bl_snapshot = blacklist_models.get_blacklist()
    bl_set = set(bl_snapshot.get("models", []))
    bl_reasons = bl_snapshot.get("reasons", {})
    visible: list[str] = []
    for m in models:
        if m in bl_set:
            continue
        visible.append(m)
    hidden = [m for m in models if m in bl_set]

    if err:
        send_json(handler, 200, {
            "ok": False,
            "provider": provider_id,
            "models": [],
            "discovery_source": source,
            "error": err,
            "default_model": default_model,
            "configured": has_secret or bool(p_cfg.get("enabled")),
        })
        return

    send_json(handler, 200, {
        "ok": True,
        "provider": provider_id,
        "models": visible,
        "hidden": hidden,
        "hidden_reasons": {m: bl_reasons.get(m, "") for m in hidden},
        "discovery_source": source,
        "default_model": default_model,
        "configured": has_secret or bool(p_cfg.get("enabled")),
    })


def _active_models_path(provider_id: str):
    """Archivo donde guardamos qué modelos están activos para el provider."""
    from pathlib import Path
    import re
    safe = re.sub(r"[^a-z0-9-]", "-", provider_id.lower()).strip("-")
    d = Path.home() / ".bago" / "state" / "active_models"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{safe}.json"


def _load_active_models(provider_id: str) -> list[str]:
    import json
    p = _active_models_path(provider_id)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [str(x) for x in data if isinstance(x, str)]
        except Exception:
            pass
    return []


def _save_active_models(provider_id: str, models: list[str]) -> None:
    import json
    p = _active_models_path(provider_id)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(sorted(set(models)), indent=2, ensure_ascii=False), encoding="utf-8")
    import os
    os.replace(str(tmp), str(p))


def handle_active_models_get(handler: "BaseHTTPRequestHandler", provider_id: str) -> None:
    """GET /providers/<id>/active-models — lista de modelos marcados activos."""
    from api_serializers import send_json
    active = _load_active_models(provider_id)
    send_json(handler, 200, {
        "ok": True,
        "provider": provider_id,
        "active_models": active,
    })


def handle_active_models_set(handler: "BaseHTTPRequestHandler", provider_id: str, body: dict) -> None:
    """POST /providers/<id>/active-models — body: {"models": [...]}."""
    from api_serializers import send_json

    if not isinstance(body, dict):
        send_json(handler, 400, {"ok": False, "error": "body debe ser objeto"})
        return

    raw = body.get("models", [])
    if not isinstance(raw, list):
        send_json(handler, 400, {"ok": False, "error": "models debe ser lista"})
        return

    models = [str(m) for m in raw if isinstance(m, (str, int))]
    _save_active_models(provider_id, models)

    # Invalidate provider cache
    mgr = _mgr(handler)
    if mgr is not None:
        try:
            mgr.invalidate_providers_cache()
        except Exception:
            pass

    # Buffer cleaner: si el provider es ollama-local, pre-carga el primer
    # modelo activo. Solo si no está ya cargado. No bloquea.
    buffer_report = None
    try:
        if mgr is not None and provider_id == "ollama-local" and models:
            from model_buffer import get_model_buffer
            buf = get_model_buffer()
            first_model = models[0]
            loaded_names = {m.name for m in buf.list_loaded()}
            if first_model not in loaded_names:
                buf.preload(first_model, keep_alive_minutes=10)
            buffer_report = {
                "preloaded": first_model,
                "loaded_now": [m.name for m in buf.list_loaded()],
            }
    except Exception as exc:
        buffer_report = {"error": str(exc)}

    response_body: dict = {
        "ok": True,
        "provider": provider_id,
        "active_models": sorted(set(models)),
        "count": len(set(models)),
    }
    if buffer_report is not None:
        response_body["buffer"] = buffer_report

    send_json(handler, 200, response_body)


# ─── Buffer cleaner API ────────────────────────────────────

def handle_buffer_status(handler: "BaseHTTPRequestHandler") -> None:
    """GET /providers/buffer/status — modelos cargados en Ollama local."""
    from api_serializers import send_json
    try:
        from model_buffer import get_model_buffer
        buf = get_model_buffer()
        loaded = buf.list_loaded()
        send_json(handler, 200, {
            "ok": True,
            "loaded": [
                {"name": m.name, "size_gb": round(m.size_gb, 2), "expires_at": m.expires_at}
                for m in loaded
            ],
            "total_loaded_gb": round(sum(m.size_gb for m in loaded), 2),
        })
    except Exception as exc:
        send_json(handler, 200, {"ok": False, "error": str(exc), "loaded": []})


def handle_buffer_unload(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """POST /providers/buffer/unload — descarga modelos manualmente.

    Body: {"model": "name"} para uno, o {} para descargar todos.
    """
    from api_serializers import send_json
    try:
        from model_buffer import get_model_buffer
        buf = get_model_buffer()
        target = (body or {}).get("model", "")
        if target:
            ok = buf.unload(target)
            send_json(handler, 200, {"ok": ok, "unloaded": target if ok else ""})
        else:
            # Descargar todos
            loaded = buf.list_loaded()
            unloaded = []
            for m in loaded:
                if buf.unload(m.name):
                    unloaded.append(m.name)
            send_json(handler, 200, {"ok": True, "unloaded": unloaded, "count": len(unloaded)})
    except Exception as exc:
        send_json(handler, 500, {"ok": False, "error": str(exc)})


def handle_buffer_prepare(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """POST /providers/buffer/prepare — prepara buffer para un modelo.

    Body: {"model": "name", "policy": "LRU"|"SAFE"|"KEEP_ACTIVE"|"HARD"}
    """
    from api_serializers import send_json
    try:
        from model_buffer import get_model_buffer
        buf = get_model_buffer()
        model = str((body or {}).get("model", "")).strip()
        policy = str((body or {}).get("policy", "LRU")).strip()
        if not model:
            send_json(handler, 400, {"ok": False, "error": "model requerido"})
            return
        if policy not in ("LRU", "SAFE", "HARD", "KEEP_ACTIVE"):
            send_json(handler, 400, {"ok": False, "error": f"policy inválida: {policy}"})
            return
        report = buf.prepare_for(model, policy=policy)  # type: ignore[arg-type]
        send_json(handler, 200, {
            "ok": True,
            "target": report.target,
            "policy": report.policy,
            "unloaded": report.unloaded,
            "kept": report.kept,
            "freed_gb": round(report.freed_gb, 2),
            "elapsed_ms": round(report.elapsed_ms, 1),
            "errors": report.errors,
        })
    except Exception as exc:
        send_json(handler, 500, {"ok": False, "error": str(exc)})


# ─── Blacklist local por máquina ───────────────────────────────────────

def handle_blacklist_get(handler: "BaseHTTPRequestHandler") -> None:
    """GET /providers/blacklist — modelos bloqueados en ESTA máquina.

    La blacklist vive en %USERPROFILE%/.bago/state/model_blacklist.json
    y se crea automáticamente con defaults sensatos la primera vez.
    """
    from api_serializers import send_json
    import blacklist_models
    data = blacklist_models.get_blacklist()
    send_json(handler, 200, {
        "ok": True,
        "version": data.get("version", 1),
        "models": data.get("models", []),
        "reasons": data.get("reasons", {}),
        "auto_blocked_on_first_run": bool(data.get("auto_blocked_on_first_run", False)),
        "path": str(blacklist_models._blacklist_path()),
    })


def handle_blacklist_modify(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """POST /providers/blacklist — body: {"action": "add"|"remove"|"reset",
    "model": "...", "reason": "..."}.
    """
    from api_serializers import send_json
    import blacklist_models
    if not isinstance(body, dict):
        send_json(handler, 400, {"ok": False, "error": "body debe ser objeto"})
        return
    action = str(body.get("action", "")).strip().lower()
    if action == "reset":
        data = blacklist_models.reset_to_defaults()
    elif action in ("add", "remove"):
        model = str(body.get("model", "")).strip()
        if not model:
            send_json(handler, 400, {"ok": False, "error": "model requerido"})
            return
        reason = str(body.get("reason", "")).strip()
        if action == "add":
            data = blacklist_models.add(model, reason)
        else:
            data = blacklist_models.remove(model)
    else:
        send_json(handler, 400, {"ok": False, "error": "action debe ser add|remove|reset"})
        return

    # Invalidate provider cache so the next /providers/<id>/models call
    # reflects the new blacklist.
    mgr = _mgr(handler)
    if mgr is not None:
        try:
            mgr.invalidate_providers_cache()
        except Exception:
            pass

    send_json(handler, 200, {
        "ok": True,
        "action": action,
        "version": data.get("version", 1),
        "models": data.get("models", []),
        "reasons": data.get("reasons", {}),
    })
