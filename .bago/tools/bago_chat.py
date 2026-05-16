
#!/usr/bin/env python3
"""BAGO Orchestrator HUB — Entry point"""
import argparse, sys
from pathlib import Path

from rich import box
from rich.panel import Panel

sys.path.insert(0, str(Path(__file__).parent))

from bago import (CredentialManager, load_providers, load_routing,
                  BagoSession, cmd, chat, console, pi, pe, banner)
from bago.constants import BAGO_SYSTEM, USER_BAGO
from bago.providers import auto_detect_provider, get_default_model, route_by_task
from bago.ui import show_response

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.styles import Style
except ImportError as e:
    print(f"ERROR: {e}"); sys.exit(1)

def main():
    p = argparse.ArgumentParser(description="BAGO Orchestrator HUB")
    p.add_argument("--provider", default="")
    p.add_argument("--model", default="")
    p.add_argument("--task",  default="")
    args = p.parse_args()

    creds     = CredentialManager()
    providers = load_providers()
    routing   = load_routing()

    if args.model:
        # Modelo explicito
        name, wire, prov = None, None, args.provider or "codex"
        for pn, pd in providers.items():
            if args.model in pd.get("models", {}):
                name, wire, prov = args.model, pd["models"][args.model].get("wire_name", args.model), pn
                break
        if not name:
            console.print(f"[red]Modelo '{args.model}' no encontrado.[/red]"); sys.exit(1)
    elif args.task:
        name, wire, prov, _ = route_by_task(args.task, routing, providers)
        pi(f"Router BAGO → {name} ({prov}) para: {args.task}")
    else:
        pm = {"copilot":"copilot","codex":"codex","ollama":"ollama-local",
              "ollama-local":"ollama-local","ollama-cloud":"ollama-cloud","anthropic":"anthropic"}
        chosen = pm.get(args.provider, "") or auto_detect_provider(creds, providers)
        if not args.provider:
            pi(f"Provider detectado: {chosen}")
        name, wire, prov = get_default_model(chosen, providers)
        if not name:
            # Ningun provider activo — pedir login
            console.print(Panel(
                "[bold yellow]No hay providers activos.[/bold yellow]\n"
                "Usa [yellow]/login github[/yellow] para Copilot, "
                "[yellow]/login openai[/yellow] para GPT, "
                "[yellow]/login anthropic[/yellow] para Claude, "
                "[yellow]/login ollama[/yellow] para local.",
                title="BAGO — Login requerido", box=box.ROUNDED, border_style="yellow"))
            # Abrir el chat igualmente para que puedan hacer /login
            name, wire, prov = "sin-modelo", "sin-modelo", "none"

    session = BagoSession(prov, name, wire, creds)
    banner(session)

    hist_file = USER_BAGO / "state" / "chat_input_history.txt"
    hist_file.parent.mkdir(parents=True, exist_ok=True)
    pt = PromptSession(history=FileHistory(str(hist_file)),
                       auto_suggest=AutoSuggestFromHistory(),
                       style=Style.from_dict({"prompt":"bold cyan"}))

    while True:
        try:
            line = pt.prompt(f"[{session.model_name}] > ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]BAGO terminado.[/dim]"); break
        if not line: continue
        if line.startswith("/"):
            if not cmd(line, session): break
            continue
        try:
            result = chat(session, line)
            if result:   # None = ya mostrado por chain/ensemble
                show_response(result, session.model_name, session.provider)
        except RuntimeError as e:
            pe(str(e))
            console.print("[dim]  Prueba /login para registrar providers o /switch para cambiar modelo.[/dim]")

if __name__ == "__main__":
    main()
