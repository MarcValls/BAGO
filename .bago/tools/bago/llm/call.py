"""bago.llm.call — Llamada a LiteLLM con fallback automático por modelo Ollama."""

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import logging
import os

logging.getLogger("LiteLLM").setLevel(logging.ERROR)
try:
    if os.environ.get("BAGO_NO_LITELLM", "0") == "1":
        raise ModuleNotFoundError("litellm disabled by BAGO_NO_LITELLM=1")
    import litellm
except ModuleNotFoundError as exc:
    litellm = None
    _LITELLM_IMPORT_ERROR = exc
else:
    _LITELLM_IMPORT_ERROR = None

from ..constants import BAGO_SYSTEM
from ..codex_auth import resolve_openai_credential
from ..codex_runtime import run_codex_exec
from ..cwd import get_user_cwd
from ..providers import resolve_codex_route_candidates, resolve_litellm
from ..ui import pe, pi

from .errors import OllamaNoModelAvailable, _is_ollama_model_not_found, classify_provider_error
from .routing import _build_escalation_chain, _provider_error_fallbacks

if litellm is not None:
    litellm.suppress_debug_info = True
    litellm.set_verbose = False


def _require_litellm() -> None:
    if litellm is not None:
        return
    detail = f" ({_LITELLM_IMPORT_ERROR})" if _LITELLM_IMPORT_ERROR else ""
    raise RuntimeError(
        "litellm no está instalado y BAGO no puede llamar a modelos LLM en este equipo"
        f"{detail}. Instala la dependencia con: python -m pip install litellm"
    )


def _parse_chain_label(label: str) -> "tuple[str, str]":
    """Extrae (provider, model) del label 'provider / model' de la cadena de fallback."""
    if " / " in label:
        prov, mdl = label.split(" / ", 1)
        return prov.strip(), mdl.strip()
    return label, label


def _codex_login_ready() -> bool:
    credential, mode = resolve_openai_credential()
    return bool(credential) and mode == "oauth"


def _llm_call(lm, kw, messages, *, session=None, _provider=None, _model=None):
    """Llamada a LiteLLM con fallback automático si el modelo Ollama no existe.

    Si el modelo no está instalado, recorre la cadena:
      otros Ollama locales → copilot → codex
    antes de lanzar OllamaNoModelAvailable.

    audit-4: los tokens se registran contra el provider/model real que responde,
    no contra el modelo original que falló.
    """
    def _do_call(lm_name, kw_args, *, prov_override=None, mdl_override=None):
        provider_name = prov_override or _provider or getattr(session, "provider", "")
        model_name = mdl_override or _model or getattr(session, "model_name", "")
        if provider_name in ("codex", "openai"):
            wire_name = model_name or lm_name.split("/", 1)[-1]
            provider_key = "codex" if provider_name in ("codex", "openai") else provider_name
            candidates = resolve_codex_route_candidates(wire_name)
            if not candidates:
                raise RuntimeError("codex auth required: codex login requerido; ruta API deshabilitada")

            def _usage_pair(usage):
                if not usage:
                    return 0, 0
                if isinstance(usage, dict):
                    return (
                        int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0),
                        int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0),
                    )
                return (
                    int(getattr(usage, "prompt_tokens", 0) or getattr(usage, "input_tokens", 0) or 0),
                    int(getattr(usage, "completion_tokens", 0) or getattr(usage, "output_tokens", 0) or 0),
                )

            last_exc = None
            for candidate in candidates:
                backend = candidate.get("backend", "litellm")
                service = candidate.get("service", "")
                route = candidate.get("route", "")
                try:
                    pi(f"   → codex [{service or route}] {wire_name}")
                    if backend == "codex-cli":
                        text, usage = run_codex_exec(
                            messages,
                            candidate.get("lm", wire_name),
                            workdir=get_user_cwd(),
                        )
                    else:
                        _require_litellm()
                        r = litellm.completion(
                            model=candidate.get("lm", wire_name),
                            messages=messages,
                            **(candidate.get("kw", {}) or {}),
                        )
                        text = r.choices[0].message.content
                        usage = getattr(r, "usage", None)

                    if session is not None:
                        tokens_in, tokens_out = _usage_pair(usage)
                        if tokens_in or tokens_out:
                            session.record_tokens(provider_key, model_name or wire_name, tokens_in, tokens_out)
                        if hasattr(session, "_update_model_origin"):
                            source = session._update_model_origin(
                                provider_key,
                                model_name or wire_name,
                                candidate.get("lm", wire_name),
                                route=route,
                                service=service,
                            )
                        else:
                            source = {
                                "service": service,
                                "route": route,
                                "backend": backend,
                            }
                        session.last_route = {
                            "mode": "auto" if getattr(session, "autoroute", False) else "manual",
                            "provider": provider_key,
                            "model": model_name or wire_name,
                            "reason": f"codex-route {service or route or backend}",
                            "service": source.get("service", service),
                            "route": source.get("route", route),
                            "backend": source.get("backend", backend),
                        }
                    return text
                except Exception as exc:
                    last_exc = exc
                    pi(f"   [dim red]✗ codex [{service or route}]: {type(exc).__name__}[/dim red]")

            raise last_exc or RuntimeError("codex route unavailable")

        _require_litellm()
        r = litellm.completion(model=lm_name, messages=messages, **kw_args)
        text = r.choices[0].message.content
        if session is not None:
            usage = getattr(r, "usage", None)
            if usage:
                prov = prov_override or _provider or session.provider
                mdl  = mdl_override  or _model  or session.model_name
                session.record_tokens(
                    prov, mdl,
                    getattr(usage, "prompt_tokens", 0) or 0,
                    getattr(usage, "completion_tokens", 0) or 0,
                )
        return text

    # === MODO SINGLE MODEL: sin fallback ni escalado ===
    if session is not None and getattr(session, "single_model", False):
        return _do_call(lm, kw)

    try:
        return _do_call(lm, kw)
    except Exception as exc:
        is_missing, missing_name = _is_ollama_model_not_found(exc)
        if not is_missing:
            if session is None:
                raise  # sin sesión no podemos degradar ni reintentar

            failed_provider = _provider or session.provider
            failed_model = _model or session.model_name
            reason = classify_provider_error(exc, model=lm)
            if reason not in {"quota", "auth", "connection", "ollama_connection"}:
                raise
            if failed_provider in ("codex", "openai") and reason == "auth":
                raise

            session.mark_provider_degraded(failed_provider, exc, model=failed_model)
            fallbacks = _provider_error_fallbacks(session, messages[-1].get("content", ""), failed_provider)
            if not fallbacks:
                raise

            pi(
                f"[yellow]⚠  {failed_provider}/{failed_model} degradado por {reason}; "
                "probando fallback...[/yellow]"
            )
            last_exc = exc
            for fb_model, fb_wire, fb_provider in fallbacks:
                lm_fb, kw_fb = resolve_litellm(fb_provider, fb_wire)
                try:
                    pi(f"   → fallback [bold cyan]{fb_provider}/{fb_model}[/bold cyan]")
                    text = _do_call(
                        lm_fb, kw_fb,
                        prov_override=fb_provider,
                        mdl_override=fb_model,
                    )
                    session.provider = fb_provider
                    session.model_name = fb_model
                    session.wire_name = fb_wire
                    source = session._update_model_origin(fb_provider, fb_model, fb_wire)
                    session.switches += 1
                    session.last_route = {
                        "mode": "auto",
                        "provider": fb_provider,
                        "model": fb_model,
                        "reason": f"fallback-{reason} desde {failed_provider}/{failed_model}",
                        "service": source.get("service", ""),
                        "route": source.get("route", ""),
                        "backend": source.get("backend", ""),
                    }
                    pi(f"   [green]✓ usando {fb_provider}/{fb_model}[/green]")
                    return text
                except Exception as exc_fb:
                    fb_reason = classify_provider_error(exc_fb, model=lm_fb)
                    if fb_reason in {"quota", "auth", "connection", "ollama_connection"}:
                        session.mark_provider_degraded(fb_provider, exc_fb, model=fb_model)
                    pi(f"   [dim red]✗ {fb_provider}/{fb_model}: {type(exc_fb).__name__}[/dim red]")
                    last_exc = exc_fb
            raise last_exc

        # Modelo Ollama no instalado: recorrer cadena de escalado
        target = missing_name or lm
        chain, available = _build_escalation_chain(target)

        if not chain:
            raise OllamaNoModelAvailable(target, [])

        pi(f"[yellow]⚠  Modelo [bold]{target}[/bold] no instalado.[/yellow]")
        if available:
            pi(f"   Ollama local tiene: {', '.join(available)}")

        last_exc = exc
        for lm_wire, kw_fallback, label in chain:
            pi(f"   → Intentando [bold cyan]{label}[/bold cyan]...")
            fb_prov, fb_mdl = _parse_chain_label(label)
            fb_wire = lm_wire.split("/", 1)[-1]
            try:
                result = _do_call(lm_wire, kw_fallback,
                                  prov_override=fb_prov, mdl_override=fb_mdl)
                if session is not None:
                    session.provider = fb_prov
                    session.model_name = fb_mdl
                    session.wire_name = fb_wire
                    source = session._update_model_origin(fb_prov, fb_mdl, fb_wire)
                    session.switches += 1
                    session.last_route = {
                        "mode": "auto" if getattr(session, "autoroute", False) else "manual",
                        "provider": fb_prov,
                        "model": fb_mdl,
                        "reason": f"fallback-missing-model {target}",
                        "service": source.get("service", ""),
                        "route": source.get("route", ""),
                        "backend": source.get("backend", ""),
                    }
                pi(f"   [green]✓ Respondiendo con {label}[/green]")
                return result
            except Exception as exc_fb:
                pi(f"   [dim red]✗ {label}: {type(exc_fb).__name__}[/dim red]")
                last_exc = exc_fb

        tried_labels = [lbl for _, _, lbl in chain]
        pe(
            f"[bold red]🚨 Sin modelo disponible.[/bold red]\n"
            f"  Cadena intentada: {', '.join(tried_labels) or 'ninguna'}\n"
            f"  Instala un modelo: ollama pull qwen2.5-coder:7b"
        )
        raise OllamaNoModelAvailable(target, tried_labels)
