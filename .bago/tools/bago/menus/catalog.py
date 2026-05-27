"""
BAGO — Menú de catálogo de modelos locales.

Muestra modelos disponibles para Ollama (instalados / por instalar),
destaca las "joyas ocultas" y clasifica por compatibilidad de hardware.
"""

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
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..hw_probe import hw_summary_lines, probe_hardware, invalidate_hw_cache
from ..model_catalog import (
    CATALOG, SPECIALTIES, ModelEntry,
    enrich_with_installed, enrich_with_compat, get_gems,
)
from ..providers import ollama_probe, ollama_pull
from ..ui import _menu_pick, _stdin_prompt

console = Console()

# ─── Constantes de visualización ─────────────────────────────────────────────

_FILTER_CHOICES = [
    ("all",          "Todos los modelos"),
    ("hw_ok",        "✅ Recomendados para este equipo"),
    ("hw_warn",      "⚠  Puede funcionar en este equipo"),
    ("hw_no",        "❌ No funcionarán en este equipo"),
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

_COMPAT_ICON = {
    "ok":   "[green]✓[/green]",
    "warn": "[yellow]⚠[/yellow]",
    "no":   "[red]✗[/red]",
    "":     "[dim]?[/dim]",
}

_COMPAT_COLOR = {
    "ok":   "green",
    "warn": "yellow",
    "no":   "red dim",
    "":     "dim",
}


def _installed_tags() -> list[str]:
    probe = ollama_probe()
    return probe.get("models", []) if probe.get("running") else []


def _compat_icon(level: str) -> str:
    return _COMPAT_ICON.get(level, "[dim]?[/dim]")


def _build_table(entries: list[ModelEntry]) -> Table:
    t = Table(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style="bold cyan",
        expand=False,
    )
    t.add_column("HW",      width=3, no_wrap=True)          # compatibilidad
    t.add_column("Inst",    width=2, no_wrap=True)           # instalado
    t.add_column("✨",      width=2, no_wrap=True)           # joya
    t.add_column("Modelo",  min_width=22, no_wrap=True)
    t.add_column("Maker",   min_width=14, no_wrap=True)
    t.add_column("GB",      width=5, justify="right")
    t.add_column("Ctx",     width=6, justify="right")
    t.add_column("Especialidad", min_width=16)
    t.add_column("HW — nota", min_width=28)

    for m in entries:
        compat_icon = _compat_icon(m.compat_level)
        inst_icon   = "[green]✓[/green]" if m.installed else "[dim]·[/dim]"
        gem_icon    = "[yellow]✨[/yellow]" if m.gem else ""
        specs       = "  ".join(SPECIALTIES.get(s, s) for s in m.specialty[:2])
        hw_note     = m.compat_reason[:45] if m.compat_reason else "[dim]sin datos HW[/dim]"
        col         = _COMPAT_COLOR.get(m.compat_level, "")
        label       = f"[bold]{m.label}[/bold]" if m.gem else m.label
        if col:
            label = f"[{col}]{label}[/{col}]"

        t.add_row(
            compat_icon,
            inst_icon,
            gem_icon,
            label,
            f"[dim]{m.maker[:16]}[/dim]",
            f"{m.size_gb:.1f}",
            f"{m.context_k}K",
            specs,
            f"[dim]{hw_note}[/dim]",
        )
    return t


def _show_detail(entry: ModelEntry) -> None:
    status_line = (
        "[green bold]INSTALADO[/green bold]"
        if entry.installed else
        "[yellow]No instalado[/yellow]"
    )
    compat_line = ""
    if entry.compat_level == "ok":
        compat_line = f"[green bold]✓ Compatible[/green bold]  {entry.compat_reason}"
    elif entry.compat_level == "warn":
        compat_line = f"[yellow bold]⚠ Puede funcionar[/yellow bold]  {entry.compat_reason}"
    elif entry.compat_level == "no":
        compat_line = f"[red bold]✗ No recomendado[/red bold]  {entry.compat_reason}"

    lines = [
        f"[bold cyan]{entry.label}[/bold cyan]  —  {entry.maker}",
        f"Tag Ollama : [yellow]{entry.ollama_tag}[/yellow]",
        f"Tamaño    : {entry.size_gb:.1f} GB  ·  Contexto: {entry.context_k}K tokens",
        f"Estado    : {status_line}",
    ]
    if compat_line:
        lines.append(f"Hardware  : {compat_line}")
    lines += [
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
    if filter_key == "hw_ok":
        return [m for m in entries if m.compat_level == "ok"]
    if filter_key == "hw_warn":
        return [m for m in entries if m.compat_level == "warn"]
    if filter_key == "hw_no":
        return [m for m in entries if m.compat_level == "no"]
    return [m for m in entries if filter_key in m.specialty]


def _show_hw_panel() -> None:
    hw = probe_hardware()
    lines = ["[bold cyan]Análisis de hardware[/bold cyan]", ""] + hw_summary_lines(hw)
    # Estadísticas del catálogo
    ok_count   = sum(1 for m in CATALOG if m.compat_level == "ok")
    warn_count = sum(1 for m in CATALOG if m.compat_level == "warn")
    no_count   = sum(1 for m in CATALOG if m.compat_level == "no")
    lines += [
        "",
        f"  [bold]En el catálogo:[/bold]  "
        f"[green]{ok_count} recomendados[/green]  "
        f"[yellow]{warn_count} posibles[/yellow]  "
        f"[red]{no_count} no viables[/red]",
    ]
    console.print(Panel("\n".join(lines), box=box.ROUNDED))


def cmd_catalog(session=None) -> None:
    """Menú principal del catálogo de modelos."""
    console.print("  [dim]Analizando hardware…[/dim]", end="\r")
    hw = probe_hardware()
    enrich_with_compat(hw)
    enrich_with_installed(_installed_tags())

    current_filter = "hw_ok"   # Por defecto: mostrar los que funcionan en este equipo

    while True:
        entries = _filter_entries(current_filter, CATALOG)

        gems_count = sum(1 for m in CATALOG if m.gem)
        inst_count = sum(1 for m in CATALOG if m.installed)
        ok_count   = sum(1 for m in CATALOG if m.compat_level == "ok")
        filter_label = dict(_FILTER_CHOICES).get(current_filter, current_filter)

        console.print(
            Panel(
                f"  [bold cyan]BAGO Model Catalog[/bold cyan]   "
                f"[dim]{len(CATALOG)} modelos  ·  "
                f"[green]{ok_count} compatibles ✓[/green]  ·  "
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
            ("hwinfo",   "🖥  Análisis detallado de hardware"),
            ("filter",   "🔎 Cambiar filtro"),
            ("install",  "⬇  Instalar un modelo"),
            ("detail",   "📄 Ver ficha detallada"),
            ("use",      "▶  Usar modelo ahora"),
            ("refresh",  "🔄 Refrescar (hardware + instalados)"),
            (None,       "── Salir ──"),
        ]
        action = _menu_pick("Catálogo", "¿Qué quieres hacer?", rows)

        if action == "hwinfo":
            _show_hw_panel()

        elif action == "filter":
            filt = _menu_pick("Filtro", "Selecciona categoría:", _FILTER_CHOICES)
            if filt:
                current_filter = filt

        elif action == "install":
            choices = [
                (
                    m.ollama_tag,
                    f"{_compat_icon(m.compat_level)} {m.label}  [{m.size_gb:.1f}GB]"
                    f"{'  ✨' if m.gem else ''}",
                )
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
                    if entry.compat_level == "no":
                        console.print(
                            f"  [red]⚠  Este modelo NO es compatible con tu hardware "
                            f"({entry.compat_reason})[/red]"
                        )
                        try:
                            from prompt_toolkit import prompt as pt_prompt
                        except ModuleNotFoundError:
                            pt_prompt = _stdin_prompt
                        ans = pt_prompt("  ¿Continuar de todas formas? [s/N]: ").strip().lower()
                        if ans not in ("s", "si", "sí", "y", "yes"):
                            continue
                console.print(f"\n  Descargando [yellow]{tag}[/yellow]…  (puede tardar varios minutos)\n")
                ok = ollama_pull(tag)
                if ok:
                    console.print(f"  [green]✓ {tag} instalado correctamente.[/green]")
                    enrich_with_installed(_installed_tags())
                else:
                    console.print(f"  [red]✗ No se pudo instalar {tag}. Comprueba que Ollama está activo.[/red]")

        elif action == "detail":
            choices = [
                (
                    m.ollama_tag,
                    f"{_compat_icon(m.compat_level)} {'✅ ' if m.installed else '   '}"
                    f"{m.label}{'  ✨' if m.gem else ''}",
                )
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
                (
                    m.ollama_tag,
                    f"{_compat_icon(m.compat_level)} {'✅ ' if m.installed else '   '}"
                    f"{m.label}  [{m.size_gb:.1f}GB]",
                )
                for m in entries
            ]
            tag = _menu_pick("Usar modelo", "Elige modelo:", choices)
            if tag:
                entry = next((m for m in CATALOG if m.ollama_tag == tag), None)
                if entry and not entry.installed:
                    try:
                        from prompt_toolkit import prompt as pt_prompt
                    except ModuleNotFoundError:
                        pt_prompt = _stdin_prompt
                    ans = pt_prompt(f"  {tag} no está instalado. ¿Instalar ahora? [s/N]: ").strip().lower()
                    if ans in ("s", "si", "sí", "y", "yes"):
                        ollama_pull(tag)
                        enrich_with_installed(_installed_tags())
                msg = session.switch_model(f"ollama-local/{tag}")
                console.print(f"  {msg}")

        elif action == "refresh":
            invalidate_hw_cache()
            hw = probe_hardware()
            enrich_with_compat(hw)
            enrich_with_installed(_installed_tags())
            console.print("  [green]Hardware y modelos actualizados.[/green]")

        else:
            break




def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(__file__ + " --test: PASS (imports OK)")
    return 0


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
