"""bago.credentials.flows.git — Flujo genérico para providers Git con token.

Cubre GitLab, Codeberg/Gitea y cualquier instancia Gitea.
Soporta dos métodos:
  1. Personal Access Token (pegar — sin navegador)
  2. Email + contraseña → genera token por API (solo Gitea/Codeberg)
"""

from prompt_toolkit import prompt as pt_prompt

from ...ui import console


def flow_gittoken(
    mgr,
    provider: str,
    label: str,
    verify_url: str,
    auth_header: str,
    prefix: str = "",
) -> str:
    """Flujo genérico para repos Git con token (GitLab, Codeberg/Gitea)."""
    import urllib.request, json as _json

    console.print(
        f"[bold]{label} — elige método:[/bold]\n"
        f"  [yellow]1[/yellow]  Personal Access Token  (pegar token — sin navegador)\n"
        f"  [yellow]2[/yellow]  Email + contraseña     (BAGO genera token por API — sin navegador)\n"
    )
    choice = pt_prompt("Opción [1/2]: ").strip()

    token: str = ""
    username: str = "?"

    if choice == "2":
        base = verify_url.rsplit("/", 2)[0]
        email = pt_prompt(f"Email {label}: ").strip()
        if not email:
            return "Cancelado."
        password = pt_prompt("Contraseña: ", is_password=True).strip()
        if not password:
            return "Cancelado."

        if "codeberg" in verify_url or "gitea" in verify_url:
            try:
                import base64 as _b64
                cred = _b64.b64encode(f"{email}:{password}".encode()).decode()
                req = urllib.request.Request(
                    f"{base}/api/v1/user",
                    headers={"Authorization": f"Basic {cred}", "Accept": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    username = _json.loads(resp.read())["login"]
                payload = _json.dumps({"name": "bago_token"}).encode()
                req2 = urllib.request.Request(
                    f"{base}/api/v1/users/{username}/tokens",
                    data=payload,
                    headers={
                        "Authorization": f"Basic {cred}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req2, timeout=10) as resp2:
                    data = _json.loads(resp2.read())
                token = data.get("sha1") or data.get("token") or ""
                if not token:
                    return f"[red]No se pudo obtener token de {label}: {data}[/red]"
                console.print(f"  [green]✓ Token generado para @{username}[/green]")
            except Exception as e:
                return f"[red]Error generando token en {label}: {e}[/red]"
        else:
            # GitLab no permite crear PAT por contraseña vía API pública
            console.print(f"  [yellow]{label} no permite crear tokens por contraseña vía API.[/yellow]")
            url = mgr.PROVIDERS.get(provider, {}).get("url", "")
            if url:
                console.print(f"  [dim]Ve a: {url}[/dim]")
            token = pt_prompt(f"{label} Personal Access Token: ", is_password=True).strip()
            if not token:
                return "Cancelado."
    else:
        url = mgr.PROVIDERS.get(provider, {}).get("url", "")
        if url:
            console.print(f"[dim]Genera tu token en: {url}[/dim]")
        token = pt_prompt(f"{label} Token: ", is_password=True).strip()
        if not token:
            return "Cancelado."

    # Verificar token
    try:
        req = urllib.request.Request(
            verify_url,
            headers={auth_header: f"{prefix}{token}", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            user_data = _json.loads(resp.read())
            username = (
                user_data.get("username")
                or user_data.get("login")
                or user_data.get("name")
                or "?"
            )
        console.print(f"  [green]✓ Verificado: @{username}[/green]")
    except Exception:
        console.print(f"  [yellow]⚠  Token no verificado (sin conexión), guardando de todas formas.[/yellow]")

    # Guardar
    env_key = mgr.PROVIDERS.get(provider, {}).get("env")
    if env_key:
        import os
        os.environ[env_key] = token
    mgr._creds.setdefault(provider, {})["token"] = token
    mgr._creds[provider]["username"] = username
    mgr._save()
    return f"[green]✓ {label} autenticado: @{username}  ({token[:4]}…{token[-4:]})[/green]"
