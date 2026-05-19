"""bago.credentials.flows.misc — Flujos genéricos: API key, HuggingFace, send.cm."""

import subprocess
from pathlib import Path

from prompt_toolkit import prompt as pt_prompt

from ...ui import console
from ..accounts import AccountManager


def flow_api_key(mgr, name: str, info: dict) -> str:
    """Flujo genérico para providers con API key (anthropic, gemini, groq…)."""
    url = info.get("url", "")
    if url:
        console.print(f"[dim]Obtén tu clave en: {url}[/dim]")
    console.print(f"[bold]{info['desc']}[/bold]")
    key = pt_prompt("API Key: ", is_password=True).strip()
    if not key:
        return "Cancelado."
    mgr.set(name, key)
    am_provider = _bago_to_am(name)
    if am_provider in AccountManager.PROVIDER_ENV:
        existing = mgr._accounts.accounts_for(am_provider)
        if existing:
            mgr._accounts.update(existing[0]["id"], credential=key)
        else:
            mgr._accounts.add(am_provider, info["desc"], key, "api_key")
        mgr._accounts.apply_active_credentials()
    return f"[green]✓ {info['desc']} — API key guardada.[/green]"


def flow_huggingface(mgr) -> str:
    """Hugging Face: pegar token o usar huggingface-cli login."""
    console.print(
        "[bold]Hugging Face — elige método:[/bold]\n"
        "  [yellow]1[/yellow]  Token directo     (pegar token — sin navegador)\n"
        "  [yellow]2[/yellow]  huggingface-cli   (si está instalado)\n"
    )
    choice = pt_prompt("Opción [1/2]: ").strip()

    if choice == "2":
        try:
            result = subprocess.run(["huggingface-cli", "login"])
            if result.returncode == 0:
                hf_cache = Path.home() / ".cache" / "huggingface" / "token"
                if hf_cache.exists():
                    token = hf_cache.read_text().strip()
                    mgr.set("huggingface", token)
                    return "[green]✓ Hugging Face autenticado via CLI[/green]"
                return "[green]✓ Hugging Face CLI login OK[/green]"
            return "[red]huggingface-cli login fallido.[/red]"
        except FileNotFoundError:
            console.print("  [yellow]huggingface-cli no encontrado. Usando opción 1.[/yellow]")

    console.print("[dim]Genera tu token en: https://huggingface.co/settings/tokens[/dim]")
    console.print("[dim]Tipo recomendado: 'read' para inferencia, 'write' para subir modelos[/dim]")
    token = pt_prompt("Hugging Face Token (hf_...): ", is_password=True).strip()
    if not token:
        return "Cancelado."

    try:
        import urllib.request, json as _json
        req = urllib.request.Request(
            "https://huggingface.co/api/whoami-v2",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read())
            username = data.get("name") or data.get("login") or "?"
        console.print(f"  [green]✓ Verificado: @{username}[/green]")
    except Exception:
        username = "?"
        console.print("  [yellow]⚠  No verificado (sin conexión), guardando de todas formas.[/yellow]")

    mgr.set("huggingface", token)
    return f"[green]✓ Hugging Face token guardado (@{username}  {token[:6]}…)[/green]"


def flow_sendcm(mgr) -> str:
    """send.cm: login por email+contraseña directo a la API — sin navegador."""
    console.print(
        "[bold]send.cm — login directo por API[/bold]\n"
        "[dim]  No necesitas abrir el navegador. Introduce tus credenciales de send.cm.[/dim]\n"
        "[dim]  Regístrate gratis en https://send.cm si aún no tienes cuenta.[/dim]\n"
    )

    existing = mgr._creds.get("sendcm", {}).get("api_key", "")
    if existing:
        console.print(f"  [dim]Token actual: {existing[:6]}…{existing[-4:]}[/dim]")
        overwrite = pt_prompt("¿Reemplazar token existente? [s/N]: ").strip().lower()
        if overwrite not in ("s", "si", "sí", "y", "yes"):
            return "[dim]Login cancelado — token existente conservado.[/dim]"

    email = pt_prompt("Email send.cm: ").strip()
    if not email:
        return "Cancelado."
    password = pt_prompt("Contraseña: ", is_password=True).strip()
    if not password:
        return "Cancelado."

    try:
        import urllib.request, json as _json
        payload = _json.dumps({"email": email, "password": password}).encode()
        req = urllib.request.Request(
            "https://send.cm/api/v2/login",
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read().decode())
    except Exception as e:
        return f"[red]Error de conexión con send.cm: {e}[/red]"

    token = (
        data.get("data", {}).get("token")
        or data.get("data", {}).get("api_key")
        or data.get("token")
        or data.get("api_key")
        or ""
    )
    if not token:
        msg = data.get("message") or data.get("error") or str(data)
        return f"[red]Login fallido: {msg}[/red]"

    mgr._creds.setdefault("sendcm", {})["api_key"] = token
    mgr._creds["sendcm"]["email"] = email
    mgr._save()
    return f"[green]✓ send.cm autenticado: {email}  (token {token[:6]}…{token[-4:]})[/green]"


def _bago_to_am(name: str) -> str:
    """Convierte nombre de CredentialManager a tipo de AccountManager."""
    return {
        "github":       "github",
        "openai":       "openai",
        "anthropic":    "anthropic",
        "openrouter":   "openrouter",
        "gemini":       "gemini",
        "ollama_cloud": "ollama_cloud",
    }.get(name, name)
