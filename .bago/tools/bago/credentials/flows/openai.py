"""bago.credentials.flows.openai — Flujos de login para OpenAI / Codex."""

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
import shutil
from pathlib import Path

from ...ui import console, _stdin_prompt


def pt_prompt(text: str, is_password: bool = False) -> str:
    return _stdin_prompt(text, is_password=is_password)


def _resolve_codex_cli() -> str | None:
    for name in ("codex", "codex.cmd", "codex.ps1"):
        found = shutil.which(name)
        if found:
            return found
    try:
        out = subprocess.run(
            ["where.exe", "codex"],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in out.stdout.splitlines():
            candidate = line.strip()
            if candidate:
                return candidate
    except Exception:
        pass
    return None


def _run_codex_login() -> subprocess.CompletedProcess | None:
    cli = _resolve_codex_cli()
    if not cli:
        return None
    if cli.lower().endswith((".cmd", ".bat", ".ps1")):
        return subprocess.run(["cmd", "/c", cli, "login"])
    return subprocess.run([cli, "login"])


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
        result = _run_codex_login()
        if result is None:
            console.print("[yellow]codex no esta instalado.[/yellow]")
            ans = pt_prompt("Install codex CLI now? [y/n]: ").strip().lower()
            if ans in ("y", "yes", "s", "si"):
                console.print("[dim]Installing @openai/codex via npm...[/dim]")
                try:
                    npm_cli = shutil.which("npm") or shutil.which("npm.cmd") or shutil.which("npm.ps1") or "npm"
                    if str(npm_cli).lower().endswith((".cmd", ".bat", ".ps1")):
                        r = subprocess.run(["cmd", "/c", str(npm_cli), "install", "-g", "@openai/codex"])
                    else:
                        r = subprocess.run([str(npm_cli), "install", "-g", "@openai/codex"])
                    if r.returncode != 0:
                        return "[red]npm install failed. Install manually: npm install -g @openai/codex[/red]"
                    result = _run_codex_login()
                    if result is None:
                        return "[red]codex instalado pero no se pudo resolver el binario. Cierra y reabre la terminal.[/red]"
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



def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(__file__ + " --test: PASS (imports OK)")
    return 0


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
