"""Comando /tumba: gestión interactiva de secretos."""

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
from rich.table import Table

from ..tumba import tumba_add, tumba_clear, tumba_delete, tumba_list
from ..tumba_schema import all_by_group, all_providers, get_slots, missing_slots
from ..ui import console, pi


_GROUP_LABELS = {
    "llm": "LLM / IA",
    "repo": "Repositorios",
    "cloud": "Cloud/Storage",
    "messaging": "Mensajería/Bots",
    "payments": "Pagos",
    "infra": "Infraestructura",
    "database": "Bases de datos",
    "email": "Email/SMS",
    "devops": "DevOps",
    "pm": "Gestión de proyectos",
}


def cmd_tumba(session, args: str) -> None:
    sub_parts = args.split(None, 1)
    sub = sub_parts[0].lower() if sub_parts else ""
    sub_arg = sub_parts[1].strip() if len(sub_parts) > 1 else ""

    if sub in ("list", "ls", "listar"):
        _list_keys()
    elif sub.startswith("del") or sub.startswith("rm"):
        _delete_key(sub_arg or (args.split(None, 1)[1].strip() if " " in args else ""))
    elif sub in ("clear", "limpiar", "vaciar"):
        pi(f"Tumba vaciada — {tumba_clear()} entradas eliminadas.")
    elif sub == "schema":
        _show_schema(sub_arg)
    elif sub == "fill":
        _fill_schema(sub_arg)
    elif sub == "check":
        _check_schema(sub_arg)
    else:
        _toggle_tumba(session)


def _list_keys() -> None:
    keys = tumba_list()
    if not keys:
        pi("Tumba vacía.")
        return
    pi("[bold]Claves en tumba:[/bold] (los valores nunca se muestran)")
    for idx, key in enumerate(keys, 1):
        console.print(f"  {idx:>2}. [bold cyan]{key}[/bold cyan]  →  {{{{{key}}}}}")


def _delete_key(name: str) -> None:
    if not name:
        pi("[red]Uso: /tumba del <nombre>[/red]")
        return
    console.print(tumba_delete(name))


def _show_schema(provider: str) -> None:
    if provider:
        slots = get_slots(provider.lower())
        if not slots:
            providers_str = ", ".join(all_providers())
            pi(f"[red]Provider '{provider}' no tiene schema predefinido.[/red]\n  Disponibles: {providers_str}")
            return
        _print_provider_schema(provider.lower(), slots)
        return

    pi("[bold]Providers con schema tumba predefinido:[/bold]")
    for group, members in all_by_group().items():
        label = _GROUP_LABELS.get(group, group)
        prov_list = "  ".join(f"[cyan]{p}[/cyan]" for p in members)
        console.print(f"  {label}:  {prov_list}")
    console.print(
        "\n  [dim]/tumba schema <provider>  — ver slots detallados[/dim]\n"
        "  [dim]/tumba fill <provider>    — rellenar slots en modo tumba[/dim]"
    )


def _print_provider_schema(provider: str, slots: list[dict]) -> None:
    table = Table(title=f"Schema tumba — [bold]{provider}[/bold]", box=box.ROUNDED, show_lines=True)
    table.add_column("Clave tumba", style="bold cyan", no_wrap=True)
    table.add_column("Env var", style="dim")
    table.add_column("Req.", justify="center")
    table.add_column("Formato", style="yellow")
    table.add_column("Descripción")
    for slot in slots:
        req = "[green]✓[/green]" if slot["required"] else "[dim]opt[/dim]"
        env = slot["env"] or "[dim]—[/dim]"
        table.add_row(slot["name"], env, req, slot["format"], slot["desc"])
    console.print(table)

    missing = missing_slots(provider, tumba_list())
    if not missing:
        console.print(f"\n  [green]✓ Todos los slots de {provider} están en la tumba.[/green]")
        return
    required = [m for m in missing if m["required"]]
    optional = [m for m in missing if not m["required"]]
    if required:
        console.print(
            f"\n  [red]Faltan {len(required)} slots requeridos:[/red] "
            + ", ".join(f"[bold]{m['name']}[/bold]" for m in required)
        )
    if optional:
        console.print("  [dim]Opcionales sin llenar: " + ", ".join(m["name"] for m in optional) + "[/dim]")


def _fill_schema(provider: str) -> None:
    if not provider:
        pi("[red]Uso: /tumba fill <provider>  (ej: /tumba fill telegram)[/red]")
        return
    provider = provider.lower()
    slots = get_slots(provider)
    if not slots:
        pi(f"[red]Provider '{provider}' no tiene schema. Usa /tumba schema para ver disponibles.[/red]")
        return
    try:
        from prompt_toolkit import prompt as pt_prompt
    except ModuleNotFoundError:
        from ..ui import _stdin_prompt as pt_prompt

    missing = missing_slots(provider, tumba_list())
    if not missing:
        pi(f"[green]✓ Todos los slots de [bold]{provider}[/bold] ya están en la tumba.[/green]")
        return

    console.print(Panel(
        f"[bold yellow]TUMBA FILL — {provider.upper()}[/bold yellow]\n\n"
        f"  Rellenando [bold]{len(missing)}[/bold] slots.\n"
        "  Los valores se copian directamente — el LLM NO los verá nunca.\n\n"
        "  [dim]Pulsa Enter sin valor para saltar un slot.[/dim]",
        title=f"[bold red]FILL: {provider}[/bold red]",
        border_style="red",
        expand=False,
    ))
    saved = 0
    for slot in missing:
        req_label = "[red]*[/red]" if slot["required"] else "[dim]opt[/dim]"
        console.print(
            f"\n  {req_label} [bold cyan]{slot['name']}[/bold cyan]\n"
            f"     [dim]{slot['desc']}[/dim]\n"
            f"     [dim]Formato: {slot['format']}[/dim]"
            + (f"\n     [dim]Obtener en: {slot['url']}[/dim]" if slot["url"] else "")
        )
        try:
            value = pt_prompt(f"  {slot['name']}: ", is_password=True).strip()
        except (KeyboardInterrupt, EOFError):
            pi("\n[dim]Fill cancelado.[/dim]")
            break
        if not value:
            console.print("  [dim]→ Saltado[/dim]")
            continue
        ok, _, msg = tumba_add(f"{slot['name']}: {value}")
        console.print(msg)
        if ok:
            saved += 1
    console.print(
        f"\n  [green]✓ {saved} slots guardados para [bold]{provider}[/bold].[/green]\n"
        "  [dim]Usa {{slot name}} en tus mensajes para insertar el valor.[/dim]"
    )


def _check_schema(provider: str) -> None:
    if not provider:
        pi("[red]Uso: /tumba check <provider>[/red]")
        return
    provider = provider.lower()
    slots = get_slots(provider)
    if not slots:
        pi(f"[red]Provider '{provider}' no tiene schema predefinido.[/red]")
        return
    keys = set(tumba_list())
    pi(f"[bold]Estado tumba — {provider}:[/bold]")
    for slot in slots:
        present = slot["name"] in keys
        status = "[green]✓ guardado[/green]" if present else (
            "[red]✗ FALTA[/red]" if slot["required"] else "[dim]— opcional[/dim]"
        )
        console.print(f"  {status}  [cyan]{slot['name']}[/cyan]")


def _toggle_tumba(session) -> None:
    session.tumba_mode = not session.tumba_mode
    if not session.tumba_mode:
        pi("Modo TUMBA [dim]DESACTIVADO[/dim] — volviendo al chat normal.")
        return
    console.print(Panel(
        "[bold yellow]MODO TUMBA ACTIVADO[/bold yellow]\n\n"
        "  Lo que escribas [bold]NO[/bold] se enviará al LLM.\n"
        "  En su lugar se copia al archivo de secretos.\n\n"
        "  [bold]Formato:[/bold]  [cyan]Nombre clave: valor secreto[/cyan]\n"
        "  [bold]Ejemplo:[/bold]  [cyan]Telegram Bot Token: 1234567:ABCxyz...[/cyan]\n\n"
        "  Para usar el valor en un mensaje normal:\n"
        "    [cyan]Configura el bot con el {{Telegram Bot Token}}[/cyan]\n\n"
        "  [dim]Subcomandos disponibles:[/dim]\n"
        "  [dim]  /tumba list              — ver claves guardadas[/dim]\n"
        "  [dim]  /tumba fill <provider>   — rellenar slots de un provider[/dim]\n"
        "  [dim]  /tumba schema [provider] — ver slots predefinidos[/dim]\n"
        "  [dim]  /tumba check <provider>  — estado de slots por provider[/dim]\n"
        "  [dim]  /tumba del <nombre>      — eliminar una clave[/dim]\n"
        "  [dim]  /tumba                   — desactivar modo tumba[/dim]",
        title="[bold red]TUMBA[/bold red]",
        border_style="red",
        expand=False,
    ))



def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(__file__ + " --test: PASS (imports OK)")
    return 0


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
