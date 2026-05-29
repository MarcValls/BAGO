"""Cálculo puro del estado de autenticación y su vista derivada."""

from __future__ import annotations

import os
from dataclasses import dataclass

from ..codex_auth import resolve_openai_credential


@dataclass(frozen=True)
class ProviderLoginView:
    name: str
    mark: str
    state: str
    desc: str


@dataclass(frozen=True)
class ProviderStatusView:
    name: str
    status: str
    quota: str
    desc: str


def is_valid_api_key(key: str) -> bool:
    """Heurística mínima para distinguir una credencial plausible de ruido."""
    k = key.strip()
    if len(k) < 8:
        return False
    obvious_invalid = {"ollama", "none", "null", "undefined", "false", "test", "demo", "placeholder"}
    return k.lower() not in obvious_invalid


def active_bago_providers(manager) -> list[str]:
    """Devuelve los providers BAGO activos a partir del estado actual."""
    active = []
    local_mode = os.environ.get("BAGO_ENABLE_LOCAL_MODE") == "1"
    for name, info in manager.PROVIDERS.items():
        if not manager.is_provider_enabled(name):
            continue
        if name == "ollama":
            if local_mode and manager._ollama_ok():
                active.append("ollama-local")
        elif name == "ollama_cloud":
            has_env = bool(os.environ.get("OLLAMA_CLOUD_API_KEY") or os.environ.get("OLLAMA_API_KEY"))
            has_file = bool(manager._creds.get("ollama_cloud"))
            has_signin = manager._creds.get("ollama_cloud_via") == "ollama_signin"
            if local_mode and (has_env or has_file or has_signin):
                active.append("ollama-cloud")
        elif name == "openai":
            _, mode = resolve_openai_credential()
            if mode == "oauth":
                active.append("codex")
        elif name == "github":
            gh = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
            gh_file = manager._creds.get("github", "")
            if (gh and is_valid_api_key(gh)) or (gh_file and is_valid_api_key(gh_file)):
                active.append("copilot")
                active.append("github-models")
        elif name == "opencode":
            if manager._creds.get("opencode_via"):
                active.append("opencode")
        elif name == "sendcm":
            pass
        else:
            env_key = info.get("env")
            bago_prov = info.get("bago_provider", name)
            if env_key and os.environ.get(env_key):
                active.append(bago_prov)
                continue
            cred_val = manager._creds.get(name) or manager._creds.get(env_key)
            if isinstance(cred_val, str) and is_valid_api_key(cred_val):
                active.append(bago_prov)
    return active


def build_login_view(manager, name: str, info: dict, active: list[str]) -> ProviderLoginView | None:
    if not manager.is_provider_enabled(name) and os.environ.get("BAGO_SHOW_DISABLED_PROVIDERS") != "1":
        return None
    bp = info.get("bago_provider")
    ok = (bp in active) if bp else False
    mark = "✓" if ok else "·"
    if name == "github":
        state = "configurado" if ok else "sin credencial"
    elif name == "openai":
        _, mode = resolve_openai_credential()
        if mode == "oauth":
            state = "codex login (GPT Plus)"
        elif mode == "api_key":
            state = "API key presente (login requerido)"
        elif mode == "invalid_api_key":
            state = "API key presente (inválida)"
        else:
            state = "sin credencial"
    elif name == "ollama":
        state = "activo" if ok else "no disponible"
    elif name == "ollama_cloud":
        k = os.environ.get("OLLAMA_CLOUD_API_KEY", "")
        if k:
            state = "API key configurada"
        elif ok:
            state = "ollama signin"
        else:
            state = "sin credencial"
    elif name == "opencode":
        state = "autenticado" if ok else "sin auth"
    elif name == "sendcm":
        token = manager._creds.get("sendcm", {}).get("api_key", "")
        if token:
            state = "configurado"
            mark = "✓"
        else:
            state = "sin credencial"
    else:
        env_key = info.get("env")
        val = os.environ.get(env_key, "") if env_key else ""
        state = "configurado" if val else "sin credencial"
    if not manager.is_provider_enabled(name):
        mark = "·"
        state = "desactivado"
    return ProviderLoginView(name=name, mark=mark, state=state, desc=info["desc"])


def build_status_view(manager, name: str, info: dict) -> ProviderStatusView | None:
    if not manager.is_provider_enabled(name) and os.environ.get("BAGO_SHOW_DISABLED_PROVIDERS") != "1":
        return None
    quota = "[dim]no comprobada[/dim]"
    if not manager.is_provider_enabled(name):
        return ProviderStatusView(name=name, status="[dim]desactivado[/dim]", quota="[dim]omitido[/dim]", desc=info["desc"])
    if name == "ollama":
        ok = manager._ollama_ok()
        status = "[green]✓ activo[/green]" if ok else "[red]✗ no disponible[/red]"
        quota = "[green]sin gasto API[/green]"
    elif name == "openai":
        _, mode = resolve_openai_credential()
        if mode == "oauth":
            status = "[green]✓ codex login (GPT Plus)[/green]"
            quota = "[yellow]separado de OpenAI API[/yellow]"
        elif mode == "api_key":
            status = "[yellow]API key presente, pero codex login requerido[/yellow]"
            quota = "[yellow]ruta API deshabilitada[/yellow]"
        elif mode == "invalid_api_key":
            status = "[red]✗ API key inválida[/red]"
        else:
            status = "[red]✗ sin credencial[/red]"
    elif name == "ollama_cloud":
        k = os.environ.get("OLLAMA_CLOUD_API_KEY", "")
        if k:
            status = "[green]✓ API key configurada[/green]"
            quota = "[yellow]cuota Ollama Cloud no verificada[/yellow]"
        elif manager._creds.get("ollama_cloud_via") == "ollama_signin":
            status = "[green]✓ ollama signin (cuenta ollama.com)[/green]"
            quota = "[yellow]separado de login[/yellow]"
        else:
            status = "[red]✗ sin credencial[/red]"
    elif name == "opencode":
        via = manager._creds.get("opencode_via")
        status = f"[green]✓ {via}[/green]" if via else "[red]✗ no instalado / sin auth[/red]"
    else:
        env_key = info.get("env")
        val = os.environ.get(env_key, "") if env_key else ""
        if val:
            status = "[green]✓ configurado[/green]"
            if name == "github":
                quota = "[yellow]GitHub/Copilot API separado[/yellow]"
        else:
            status = "[red]✗ sin credencial[/red]"
    return ProviderStatusView(name=name, status=status, quota=quota, desc=info["desc"])
