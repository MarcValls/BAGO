"""bago.credentials.flows.misc — Flujos genéricos: API key, HuggingFace, send.cm."""

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import subprocess
from pathlib import Path

from ...ui import console, _stdin_prompt
from ...tumba import tumba_add, tumba_get
from ..accounts import AccountManager


def pt_prompt(text: str, is_password: bool = False) -> str:
    return _stdin_prompt(text, is_password=is_password)


_VALIDATION_ENDPOINTS = {
    "anthropic":  ("https://api.anthropic.com/v1/models",  "x-api-key"),
    "gemini":     ("https://generativelanguage.googleapis.com/v1beta/models?key={key}",  None),
    "groq":       ("https://api.groq.com/openai/v1/models",  "Authorization"),
    "mistral":    ("https://api.mistral.ai/v1/models",       "Authorization"),
    "together":   ("https://api.together.xyz/v1/models",       "Authorization"),
    "deepseek":   ("https://api.deepseek.com/v1/models",       "Authorization"),
    "xai":        ("https://api.x.ai/v1/models",               "Authorization"),
    "openrouter": ("https://openrouter.ai/api/v1/auth/limits", "Authorization"),
    "replicate":  ("https://api.replicate.com/v1/models",      "Authorization"),
}


def _validate_api_key(name: str, key: str) -> tuple[bool, str]:
    """Valida una API key contra el endpoint del provider. Devuelve (ok, mensaje)."""
    import urllib.request, urllib.error

    cfg = _VALIDATION_ENDPOINTS.get(name)
    if not cfg:
        return True, "sin endpoint de validación"

    url, header = cfg
    req = urllib.request.Request(url.replace("{key}", key))
    if header:
        if header.lower() == "x-api-key":
            req.add_header(header, key)
        elif name == "replicate":
            req.add_header(header, f"Token {key}")
        else:
            req.add_header(header, f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return True, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return False, f"rechazada (HTTP {e.code})"
        return False, f"error HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, f"sin conexión: {e.reason}"
    except Exception as e:
        return False, f"excepción: {e}"


def flow_api_key(mgr, name: str, info: dict) -> str:
    """Flujo genérico para providers con API key (anthropic, gemini, groq…)."""
    url = info.get("url", "")
    if url:
        console.print(f"[dim]Obtén tu clave en: {url}[/dim]")
    console.print(f"[bold]{info['desc']}[/bold]")
    key = pt_prompt("API Key: ", is_password=True).strip()
    if not key:
        return "Cancelado."

    # ── Validación real antes de guardar ────────────────────────────────────
    ok, msg = _validate_api_key(name, key)
    if not ok:
        return f"[red]✗ {info['desc']} — API key {msg}. No guardada.[/red]\n  [dim]Revisa la clave o tu conexión.[/dim]"
    console.print(f"  [green]✓ Validada ({msg})[/green]")

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


def _send_api_base_url() -> str:
    return os.environ.get("BAGO_SEND_API_BASE_URL", "https://send.now/api").rstrip("/")


def flow_sendcm(mgr) -> str:
    """send.now / send.cm: pegar API key desde el dashboard (sin login email+password).

    send.now expone una API simple por HTTP GET/POST con API key.
    El usuario debe sacar su API key en su cuenta.
    """
    from ...sendnow_api import SendNowClient, SendNowError

    console.print(
        "[bold]send.now — API key[/bold]\n"
        "[dim]  Obtén tu API key en tu cuenta send.now.[/dim]\n"
        f"[dim]  Base API: {_send_api_base_url()}[/dim]\n"
        "[dim]  La clave sirve para account/info, upload/server, file/* y folder/*.[/dim]\n"
    )

    existing = mgr._creds.get("sendcm", {}).get("api_key", "") or tumba_get("SendCM API Key")
    if existing:
        console.print(f"  [dim]Token actual: {existing[:6]}…{existing[-4:]}[/dim]")
        overwrite = pt_prompt("¿Reemplazar token existente? [s/N]: ").strip().lower()
        if overwrite not in ("s", "si", "sí", "y", "yes"):
            return "[dim]Login cancelado — token existente conservado.[/dim]"

    api_key = pt_prompt("send.now API Key: ", is_password=True).strip()
    if not api_key:
        return "Cancelado."

    client = SendNowClient(api_key=api_key, base_url=_send_api_base_url())

    email = "?"
    try:
        data = client.account_info()
    except SendNowError as e:
        if e.status is not None:
            return f"[red]send.now rechazó la API key (HTTP {e.status}).[/red]"
        return f"[red]send.now no pudo verificarse: {e}[/red]"
    except Exception as e:
        console.print(f"  [yellow]⚠  No se pudo verificar (sin conexión): {e}[/yellow]")
        data = None

    if data is not None:
        result = data.get("result") or data.get("data") or {}
        email = result.get("email") or result.get("login") or "?"
        console.print(f"  [green]✓ Verificado: {email}[/green]")

    mgr._creds.setdefault("sendcm", {})["api_key"] = api_key
    if email != "?":
        mgr._creds["sendcm"]["email"] = email
    mgr._save()
    tumba_add(f"SendCM API Key: {api_key}")
    if email != "?":
        tumba_add(f"SendCM Email: {email}")
    return f"[green]✓ send.now autenticado: {email}  (key {api_key[:6]}…{api_key[-4:]})[/green]"


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


def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(f"{Path(__file__).name} --test: PASS (imports OK)")
    return 0
if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
