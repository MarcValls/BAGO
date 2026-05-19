"""bago.credentials.flows.github — Flujo de login para GitHub / Copilot."""

import subprocess

from prompt_toolkit import prompt as pt_prompt

from ...ui import console


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
            import urllib.request, json as _json
            req = urllib.request.Request(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                user = _json.loads(resp.read())["login"]
            console.print(f"  [green]✓ Verificado: @{user}[/green]")
        except Exception:
            console.print("  [yellow]⚠  No se pudo verificar el token (sin conexión), guardando de todas formas.[/yellow]")
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
    result = subprocess.run(["gh", "auth", "login"])
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
