"""bago.credentials.flows.ollama — Flujos de login para Ollama local/cloud y OpenCode."""

import os
import shutil
import subprocess

from ...ui import console, _stdin_prompt


def pt_prompt(text: str, is_password: bool = False) -> str:
    return _stdin_prompt(text, is_password=is_password)


def _resolve(cmd: str) -> str | None:
    """Resuelve un binario respetando shims de Windows (npm.cmd, opencode.cmd…)."""
    path = shutil.which(cmd)
    if path:
        return path
    if os.name == "nt":
        for ext in (".cmd", ".bat", ".exe"):
            path = shutil.which(cmd + ext)
            if path:
                return path
    return None


def flow_ollama_cloud(mgr) -> str:
    """Ollama Cloud: ollama signin o API key desde ollama.com."""
    console.print(
        "[bold]Ollama Cloud — elige método:[/bold]\n"
        "  [yellow]1[/yellow]  ollama signin  (login con tu cuenta ollama.com)\n"
        "  [yellow]2[/yellow]  API key        (desde ollama.com/settings/api)\n"
    )
    choice = pt_prompt("Opción [1/2]: ").strip()
    if choice == "1":
        console.print("[dim]Ejecutando ollama signin...[/dim]")
        try:
            result = subprocess.run(["ollama", "signin"])
        except FileNotFoundError:
            return "[red]ollama no encontrado. Instalalo desde https://ollama.com y reintenta.[/red]"
        if result.returncode == 0:
            mgr._creds["ollama_cloud_via"] = "ollama_signin"
            mgr._save()
            return "[green]✓ Ollama Cloud autenticado con ollama signin.[/green]"
        return "[red]ollama signin fallido. Prueba la opción 2 con API key.[/red]"
    else:
        console.print("[dim]Obtén tu clave en: https://ollama.com/settings/api[/dim]")
        key = pt_prompt("Ollama Cloud API Key: ", is_password=True).strip()
        if not key:
            return "Cancelado."
        mgr.set("ollama_cloud", key)
        existing = mgr._accounts.accounts_for("ollama_cloud")
        if existing:
            mgr._accounts.update(existing[0]["id"], credential=key)
        else:
            mgr._accounts.add("ollama_cloud", "Ollama Cloud", key, "api_key")
        mgr._accounts.apply_active_credentials()
        return "[green]✓ Ollama Cloud API key guardada.[/green]"


def flow_ollama_service(mgr) -> str:
    """Ollama local: verifica que esté corriendo y lista modelos disponibles."""
    if mgr._ollama_ok():
        try:
            out = subprocess.check_output(
                ["ollama", "list"], text=True, stderr=subprocess.DEVNULL
            )
            console.print(out)
            return "[green]✓ Ollama activo y disponible.[/green]"
        except Exception:
            pass
    return "[red]Ollama no disponible. Instala desde https://ollama.com[/red]"


def flow_opencode(mgr) -> str:
    """OpenCode AI: instala si no está, luego opencode auth login."""
    opencode_bin = _resolve("opencode")
    opencode_ok = False
    if opencode_bin:
        try:
            subprocess.check_output(
                [opencode_bin, "--version"], stderr=subprocess.DEVNULL, timeout=5
            )
            opencode_ok = True
        except Exception:
            opencode_ok = False

    if not opencode_ok:
        console.print(
            "[bold yellow]OpenCode no está instalado.[/bold yellow]\n"
            "[dim]Instala con:[/dim]  npm install -g opencode-ai\n"
            "[dim]Más info:[/dim]    https://opencode.ai\n"
        )
        if pt_prompt("¿Instalar ahora? [s/n]: ").strip().lower() == "s":
            npm_bin = _resolve("npm")
            if not npm_bin:
                return (
                    "[red]npm no encontrado en PATH. Instala Node.js "
                    "(https://nodejs.org) y vuelve a intentarlo.[/red]"
                )
            console.print("[dim]Ejecutando npm install -g opencode-ai...[/dim]")
            try:
                r = subprocess.run([npm_bin, "install", "-g", "opencode-ai"])
            except FileNotFoundError:
                return "[red]No se pudo ejecutar npm. Instala manualmente: npm install -g opencode-ai[/red]"
            if r.returncode != 0:
                return "[red]Instalación fallida. Instala manualmente: npm install -g opencode-ai[/red]"
            console.print("[green]✓ opencode instalado.[/green]")
            opencode_bin = _resolve("opencode")
            if not opencode_bin:
                return "[yellow]opencode instalado pero no encontrado en PATH. Reabre la terminal e intenta de nuevo.[/yellow]"
        else:
            return "Cancelado. Instala opencode manualmente."

    console.print("[dim]Ejecutando opencode auth login...[/dim]")
    try:
        result = subprocess.run([opencode_bin, "auth", "login"])
    except FileNotFoundError:
        return "[red]No se pudo ejecutar opencode. Reabre la terminal e intenta de nuevo.[/red]"
    if result.returncode == 0:
        mgr._creds["opencode_via"] = "opencode_login"
        mgr._save()
        return "[green]✓ OpenCode autenticado.[/green]"
    mgr._creds["opencode_via"] = "opencode_installed"
    mgr._save()
    return "[green]✓ OpenCode instalado y marcado como activo.[/green]"
