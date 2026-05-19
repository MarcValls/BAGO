"""
BAGO — Menú de catálogo de modelos locales.

Muestra modelos disponibles para Ollama (instalados / por instalar),
destaca las "joyas ocultas" y permite instalar con una tecla.
"""

from __future__ import annotations

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..model_catalog import CATALOG, SPECIALTIES, ModelEntry, enrich_with_installed, get_gems
from ..providers import ollama_probe, ollama_pull
from ..ui import _menu_pick

console = Console()

# ─── Constantes de visualización ─────────────────────────────────────────────

_FILTER_CHOICES = [
    ("all",          "Todos los modelos"),
    ("gems",         "✨ Joyas ocultas"),
    ("coding",       "💻 Código"),
    ("reasoning",    "🧠 Razonamiento"),
    ("general",      "🌐 General"),
    ("multilingual", "🗺  Multilingüe"),
    ("small",        "🪶 Ultra-ligeros (<3GB)"),
    ("vision",       "👁  Visión"),
    ("rag",          "🔍 RAG / Embeddings"),
    ("uncensored",   "🔓 Sin censura"),
    ("installed",    "✅ Solo instalados"),
]


def _installed_tags() -> list[str]:
    probe = ollama_probe()
    return probe.get("models", []) if probe.get("running") else []


def _build_table(entries: list[ModelEntry]) -> Table:
    t = Table(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style="bold cyan",
        expand=False,
    )
    t.add_column("",        width=2, no_wrap=True)          # instalado
    t.add_column("Gem",     width=3, no_wrap=True)          # joya
    t.add_column("Modelo",  min_width=22, no_wrap=True)
    t.add_column("Maker",   min_width=14, no_wrap=True)
    t.add_column("GB",      width=5, justify="right")
    t.add_column("Ctx",     width=6, justify="right")
    t.add_column("Especialidad", min_width=18)
    t.add_column("Descripción breve", min_width=30)

    for m in entries:
        inst_icon = "[green]✓[/green]" if m.installed else "[dim]·[/dim]"
        gem_icon  = "[yellow]✨[/yellow]" if m.gem else ""
        specs = "  ".join(SPECIALTIES.get(s, s) for s in m.specialty[:2])
        # descripción: primeras 60 chars
        desc = m.description[:70].rstrip()
        if len(m.description) > 70:
            desc += "…"
        style = "bold" if m.gem else ""
        t.add_row(
            inst_icon,
            gem_icon,
            f"[{style}]{m.label}[/{style}]" if style else m.label,
            f"[dim]{m.maker[:16]}[/dim]",
            f"{m.size_gb:.1f}",
            f"{m.context_k}K",
            specs,
            f"[dim]{desc}[/dim]",
        )
    return t


def _show_detail(entry: ModelEntry) -> None:
    status_line = (
        "[green bold]INSTALADO[/green bold]"
        if entry.installed else
        "[yellow]No instalado[/yellow]"
    )
    lines = [
        f"[bold cyan]{entry.label}[/bold cyan]  —  {entry.maker}",
        f"Tag Ollama : [yellow]{entry.ollama_tag}[/yellow]",
        f"Tamaño    : {entry.size_gb:.1f} GB  ·  Contexto: {entry.context_k}K tokens",
        f"Estado    : {status_line}",
        "",
        f"[bold]Descripción:[/bold]",
        entry.description,
    ]
    if entry.benchmark:
        lines += ["", f"[bold]Benchmarks:[/bold]  {entry.benchmark}"]
    if entry.gem:
        lines += [
            "",
            f"[yellow bold]✨ POR QUÉ ES UNA JOYA:[/yellow bold]",
            f"[yellow]{entry.gem_reason}[/yellow]",
        ]
    if entry.url:
        lines += ["", f"[dim]Más info: {entry.url}[/dim]"]

    console.print(Panel("\n".join(lines), title="Ficha de modelo", box=box.ROUNDED))


def _filter_entries(filter_key: str, entries: list[ModelEntry]) -> list[ModelEntry]:
    if filter_key == "all":
        return entries
    if filter_key == "gems":
        return [m for m in entries if m.gem]
    if filter_key == "installed":
        return [m for m in entries if m.installed]
    if filter_key == "small":
        return [m for m in entries if m.size_gb < 3.0]
    return [m for m in entries if filter_key in m.specialty]


def cmd_catalog(session=None) -> None:
    """Menú principal del catálogo de modelos."""
    # 1. Enriquecer con estado instalado
    installed = _installed_tags()
    enrich_with_installed(installed)

    current_filter = "all"

    while True:
        entries = _filter_entries(current_filter, CATALOG)

        # Cabecera
        gems_count = sum(1 for m in CATALOG if m.gem)
        inst_count = sum(1 for m in CATALOG if m.installed)
        filter_label = dict(_FILTER_CHOICES).get(current_filter, current_filter)

        console.print(
            Panel(
                f"  [bold cyan]BAGO Model Catalog[/bold cyan]   "
                f"[dim]{len(CATALOG)} modelos  ·  "
                f"[yellow]{gems_count} joyas ✨[/yellow]  ·  "
                f"[green]{inst_count} instalados[/green][/dim]\n"
                f"  Filtro activo: [bold]{filter_label}[/bold]   "
                f"({len(entries)} modelos visibles)",
                box=box.ROUNDED,
            )
        )

        # Tabla
        if entries:
            console.print(_build_table(entries))
        else:
            console.print("  [dim]Sin modelos con ese filtro.[/dim]")

        # Menú de acciones
        rows: list[tuple] = [
            ("filter",   "🔎 Cambiar filtro"),
            ("install",  "⬇  Instalar un modelo"),
            ("detail",   "📄 Ver ficha detallada"),
            ("use",      "▶  Usar modelo ahora"),
            ("refresh",  "🔄 Refrescar estado instalados"),
            (None,       "── Salir ──"),
        ]
        action = _menu_pick("Catálogo", "¿Qué quieres hacer?", rows)

        if action == "filter":
            filt = _menu_pick("Filtro", "Selecciona categoría:", _FILTER_CHOICES)
            if filt:
                current_filter = filt

        elif action == "install":
            choices = [
                (m.ollama_tag, f"{m.label}  [{m.size_gb:.1f}GB]  {'✨' if m.gem else ''}")
                for m in entries if not m.installed
            ]
            if not choices:
                console.print("  [green]Todos los modelos del filtro actual ya están instalados.[/green]")
                continue
            tag = _menu_pick("Instalar", "Elige modelo a instalar:", choices)
            if tag:
                entry = next((m for m in CATALOG if m.ollama_tag == tag), None)
                if entry:
                    _show_detail(entry)
                console.print(f"\n  Descargando [yellow]{tag}[/yellow]…  (puede tardar varios minutos)\n")
                ok = ollama_pull(tag)
                if ok:
                    console.print(f"  [green]✓ {tag} instalado correctamente.[/green]")
                    # Actualizar estado en catálogo
                    enrich_with_installed(_installed_tags())
                else:
                    console.print(f"  [red]✗ No se pudo instalar {tag}. Comprueba que Ollama está activo.[/red]")

        elif action == "detail":
            choices = [
                (m.ollama_tag, f"{'✅ ' if m.installed else '   '}{m.label}  {'✨' if m.gem else ''}")
                for m in entries
            ]
            tag = _menu_pick("Ficha", "Elige modelo:", choices)
            if tag:
                entry = next((m for m in CATALOG if m.ollama_tag == tag), None)
                if entry:
                    _show_detail(entry)

        elif action == "use":
            if session is None:
                console.print("  [yellow]No hay sesión activa para cambiar modelo.[/yellow]")
                continue
            choices = [
                (m.ollama_tag, f"{'✅ ' if m.installed else '⚠  '}{m.label}  [{m.size_gb:.1f}GB]")
                for m in entries
            ]
            tag = _menu_pick("Usar modelo", "Elige modelo:", choices)
            if tag:
                entry = next((m for m in CATALOG if m.ollama_tag == tag), None)
                if entry and not entry.installed:
                    from prompt_toolkit import prompt as pt_prompt
                    ans = pt_prompt(f"  {tag} no está instalado. ¿Instalar ahora? [s/N]: ").strip().lower()
                    if ans in ("s", "si", "sí", "y", "yes"):
                        ollama_pull(tag)
                        enrich_with_installed(_installed_tags())
                msg = session.switch_model(f"ollama-local/{tag}")
                console.print(f"  {msg}")

        elif action == "refresh":
            enrich_with_installed(_installed_tags())
            console.print("  [green]Estado actualizado.[/green]")

        else:
            break
