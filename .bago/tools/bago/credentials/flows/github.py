"""bago.credentials.flows.github — Flujo de login para GitHub / Copilot."""

import subprocess

from ...ui import console, _stdin_prompt


def pt_prompt(text: str, is_password: bool = False) -> str:
    return _stdin_prompt(text, is_password=is_password)


def flow_github(mgr) -> str:
    """GitHub: PAT directo (sin navegador) o gh auth login (abre browser)."""
    console.print(
        "[bold]GitHub — elige método:[/bold]\n"
        "  [yellow]1[/yellow]  Personal Access Token  (pegar token — sin navegador)\n"
        "  [yellow]2[/yellow]  gh auth login          (flujo OAuth — puede abrir navegador)\n"
    )
    choice = pt_prompt("Opción [1/2]: ").strip()

    if choice == "1":
        console.print("[dim]Genera tu token en: GitHub → Settings → Developer settings → Personal access tokens[/dim]")
        console.print("[dim]Permisos mínimos recomendados: repo, read:org, gist[/dim]")
        token = pt_prompt("GitHub Personal Access Token: ", is_password=True).strip()
        if not token:
            return "Cancelado."
        try:
            import urllib.request, urllib.error, json as _json
            req = urllib.request.Request(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                user = _json.loads(resp.read())["login"]
            console.print(f"  [green]✓ Verificado: @{user}[/green]")
        except urllib.error.HTTPError as e:
            return f"[red]✗ Token GitHub rechazado (HTTP {e.code}). Revisa permisos/expiración. No guardado.[/red]"
        except urllib.error.URLError:
            console.print("  [yellow]⚠  Sin conexión a api.github.com — guardando sin verificar.[/yellow]")
            user = "?"
        except Exception:
            console.print("  [yellow]⚠  No se pudo verificar el token, guardando de todas formas.[/yellow]")
            user = "?"
        mgr.set("github", token)
        existing = mgr._accounts.accounts_for("github")
        if existing:
            mgr._accounts.update(existing[0]["id"], credential=token)
        else:
            mgr._accounts.add("github", f"GitHub @{user}", token, "token")
        mgr._accounts.apply_active_credentials()
        return f"[green]✓ GitHub PAT guardado  (@{user}  {token[:4]}…{token[-4:]})[/green]"

    # Opción 2: gh auth login
    try:
        result = subprocess.run(["gh", "auth", "login"])
    except FileNotFoundError:
        return "[red]gh CLI no encontrado. Instalalo desde https://cli.github.com y reintenta.[/red]"
    if result.returncode != 0:
        return "Login GitHub fallido."
    try:
        token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
        mgr.set("github", token)
        existing = mgr._accounts.accounts_for("github")
        if existing:
            mgr._accounts.update(existing[0]["id"], credential=token)
        else:
            mgr._accounts.add("github", "GitHub Personal", token, "token")
        mgr._accounts.apply_active_credentials()
        return f"[green]✓ GitHub token guardado ({token[:4]}…{token[-4:]})[/green]"
    except Exception as e:
        return f"Token obtenido pero no guardado: {e}"
