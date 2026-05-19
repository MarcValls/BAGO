"""bago.llm.call — Llamada a LiteLLM con fallback automático por modelo Ollama."""

import litellm

from ..constants import BAGO_SYSTEM
from ..ui import pe, pi

from .errors import OllamaNoModelAvailable, _is_ollama_model_not_found
from .routing import _build_escalation_chain

litellm.suppress_debug_info = True
litellm.set_verbose = False


def _parse_chain_label(label: str) -> "tuple[str, str]":
    """Extrae (provider, model) del label 'provider / model' de la cadena de fallback."""
    if " / " in label:
        prov, mdl = label.split(" / ", 1)
        return prov.strip(), mdl.strip()
    return label, label


def _llm_call(lm, kw, messages, *, session=None, _provider=None, _model=None):
    """Llamada a LiteLLM con fallback automático si el modelo Ollama no existe.

    Si el modelo no está instalado, recorre la cadena:
      otros Ollama locales → copilot → codex
    antes de lanzar OllamaNoModelAvailable.

    audit-4: los tokens se registran contra el provider/model real que responde,
    no contra el modelo original que falló.
    """
    def _do_call(lm_name, kw_args, *, prov_override=None, mdl_override=None):
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

    try:
        return _do_call(lm, kw)
    except Exception as exc:
        is_missing, missing_name = _is_ollama_model_not_found(exc)
        if not is_missing:
            raise  # otro tipo de error → propagar normal

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
            try:
                result = _do_call(lm_wire, kw_fallback,
                                  prov_override=fb_prov, mdl_override=fb_mdl)
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
