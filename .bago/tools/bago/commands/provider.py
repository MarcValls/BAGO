"""Comando /provider: listar, activar y desactivar providers."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich import box
from rich.panel import Panel

from ..providers import auto_detect_provider, get_default_model, load_providers
from ..ui import console, pe, pi


def cmd_provider(session, args: str) -> None:
    parts = args.split()
    if not parts or parts[0].lower() in ("list", "ls", "status"):
        disabled = sorted(session.creds.disabled_providers())
        active = session.creds.active_bago_providers()
        console.print(Panel(
            f"Activos:      {', '.join(active) or 'ninguno'}\n"
            f"Desactivados: {', '.join(disabled) or 'ninguno'}\n\n"
            "[dim]/provider off <provider>  oculta y excluye un servicio[/dim]\n"
            "[dim]/provider on <provider>   lo vuelve a considerar[/dim]",
            title="[bold]Providers BAGO[/bold]", box=box.SIMPLE,
        ))
        return

    action = parts[0].lower()
    if len(parts) >= 2 and action in ("off", "disable", "desactivar"):
        target = parts[1]
        state = session.creds.set_provider_enabled(target, False)
        session.providers = load_providers()
        if not session.creds.is_provider_enabled(session.provider):
            new_prov = auto_detect_provider(session.creds, session.providers)
            name, wire, prov = get_default_model(new_prov, session.providers)
            if name:
                session.provider, session.model_name, session.wire_name = prov, name, wire
                session.last_route = {
                    "mode": "manual",
                    "provider": prov,
                    "model": name,
                    "reason": f"{target} desactivado",
                }
        pi(f"Provider {target}: {state}.")
        return

    if len(parts) >= 2 and action in ("on", "enable", "activar"):
        target = parts[1]
        state = session.creds.set_provider_enabled(target, True)
        session.providers = load_providers()
        pi(f"Provider {target}: {state}.")
        return

    pe("Uso: /provider list | /provider off <provider> | /provider on <provider>")
