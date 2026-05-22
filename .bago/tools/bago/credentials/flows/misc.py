"""bago.credentials.flows.misc — Flujos genéricos: API key, HuggingFace, send.cm."""

import subprocess
from pathlib import Path

from ...ui import console, _stdin_prompt
from ..accounts import AccountManager


def pt_prompt(text: str, is_password: bool = False) -> str:
    return _stdin_prompt(text, is_password=is_password)


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
        import urllib.request, urllib.error, json as _json
        req = urllib.request.Request(
            "https://huggingface.co/api/whoami-v2",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read())
            username = data.get("name") or data.get("login") or "?"
        console.print(f"  [green]✓ Verificado: @{username}[/green]")
    except urllib.error.HTTPError as e:
        return f"[red]✗ Token Hugging Face rechazado (HTTP {e.code}). No guardado.[/red]"
    except urllib.error.URLError:
        username = "?"
        console.print("  [yellow]⚠  Sin conexión, guardando sin verificar.[/yellow]")
    except Exception:
        username = "?"
        console.print("  [yellow]⚠  No verificado, guardando de todas formas.[/yellow]")

    mgr.set("huggingface", token)
    return f"[green]✓ Hugging Face token guardado (@{username}  {token[:6]}…)[/green]"


def flow_sendcm(mgr) -> str:
    """send.cm: pegar API key desde el dashboard (sin login email+password).

    send.cm es una plataforma XFileSharing — no tiene endpoint público
    de login con credenciales. La API usa ?key=<api_key> en cada request.
    El usuario debe sacar su API key de https://send.cm/?op=my_account
    """
    import urllib.request, urllib.parse, json as _json

    console.print(
        "[bold]send.cm — API key[/bold]\n"
        "[dim]  send.cm no permite login email+password por API.[/dim]\n"
        "[dim]  Obtén tu API key en: https://send.cm/?op=my_account "
        "(sección 'API Key')[/dim]\n"
        "[dim]  Regístrate gratis en https://send.cm si aún no tienes cuenta.[/dim]\n"
    )

    existing = mgr._creds.get("sendcm", {}).get("api_key", "")
    if existing:
        console.print(f"  [dim]Token actual: {existing[:6]}…{existing[-4:]}[/dim]")
        overwrite = pt_prompt("¿Reemplazar token existente? [s/N]: ").strip().lower()
        if overwrite not in ("s", "si", "sí", "y", "yes"):
            return "[dim]Login cancelado — token existente conservado.[/dim]"

    api_key = pt_prompt("send.cm API Key: ", is_password=True).strip()
    if not api_key:
        return "Cancelado."

    # Verificar la key contra /api/account/info?key=...
    email = "?"
    try:
        url = f"https://send.cm/api/account/info?key={urllib.parse.quote(api_key)}"
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = _json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return f"[red]send.cm rechazó la API key (HTTP {e.code}).[/red]"
    except Exception as e:
        console.print(f"  [yellow]⚠  No se pudo verificar (sin conexión): {e}[/yellow]")
        data = None

    if data is not None:
        status = data.get("status") or data.get("server_status") or 200
        if status != 200:
            msg = data.get("msg") or data.get("message") or str(data)
            return f"[red]API key inválida: {msg}[/red]"
        result = data.get("result") or data.get("data") or {}
        email = result.get("email") or result.get("login") or "?"
        console.print(f"  [green]✓ Verificado: {email}[/green]")

    mgr._creds.setdefault("sendcm", {})["api_key"] = api_key
    if email != "?":
        mgr._creds["sendcm"]["email"] = email
    mgr._save()
    return f"[green]✓ send.cm autenticado: {email}  (key {api_key[:6]}…{api_key[-4:]})[/green]"


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
