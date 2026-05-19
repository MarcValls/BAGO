"""bago.credentials.flows.openai — Flujos de login para OpenAI / Codex."""

import subprocess

from ...ui import console, _stdin_prompt


def pt_prompt(text: str, is_password: bool = False) -> str:
    return _stdin_prompt(text, is_password=is_password)


def flow_openai(mgr) -> str:
    """OpenAI: codex login (GPT Plus) o API key directa."""
    console.print(
        "[bold]OpenAI / GPT — elige método:[/bold]\n"
        "  [yellow]1[/yellow]  codex login  (GPT Plus — abre navegador, sin API key)\n"
        "  [yellow]2[/yellow]  API key      (pegar clave desde platform.openai.com)\n"
    )
    choice = pt_prompt("Opción [1/2]: ").strip()
    if choice == "1":
        console.print("[dim]Ejecutando codex login (abre navegador)...[/dim]")
        try:
            result = subprocess.run(["codex", "login"])
        except FileNotFoundError:
            console.print("[yellow]codex no esta instalado.[/yellow]")
            ans = pt_prompt("Install codex CLI now? [y/n]: ").strip().lower()
            if ans in ("y", "yes", "s", "si"):
                console.print("[dim]Installing @openai/codex via npm...[/dim]")
                try:
                    r = subprocess.run(["npm", "install", "-g", "@openai/codex"])
                    if r.returncode != 0:
                        return "[red]npm install failed. Install manually: npm install -g @openai/codex[/red]"
                    result = subprocess.run(["codex", "login"])
                except FileNotFoundError:
                    return "[red]npm not found. Install Node.js then: npm install -g @openai/codex[/red]"
            else:
                return "Cancelled. Use option 2 (API key) or install codex manually."
        if result.returncode == 0:
            mgr._creds["openai_via"] = "codex_login"
            mgr._save()
            return "[green]✓ Codex CLI autenticado (GPT Plus activo)[/green]"
        return "[red]codex login fallido. Prueba la opción 2 con API key.[/red]"
    else:
        console.print("[dim]Obtén tu clave en: https://platform.openai.com/api-keys[/dim]")
        key = pt_prompt("OpenAI API Key: ", is_password=True).strip()
        if not key:
            return "Cancelado."
        mgr.set("openai", key)
        existing = mgr._accounts.accounts_for("openai")
        if existing:
            mgr._accounts.update(existing[0]["id"], credential=key)
        else:
            mgr._accounts.add("openai", "OpenAI Principal", key, "api_key")
        mgr._accounts.apply_active_credentials()
        return "[green]✓ OpenAI API key guardada.[/green]"
