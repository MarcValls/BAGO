"""bago.chat.boot — resolución de provider al arranque y tareas paralelas de inicio."""

import sys
from pathlib import Path

from rich import box
from rich.panel import Panel

from bago import CredentialManager, load_providers, load_routing, BagoSession, banner
from bago.providers import (
    auto_detect_provider, get_default_model, route_by_task, scan_provider_health,
)
from bago.ui import console, pi


# ─── Resolución de provider/modelo ────────────────────────────────────────────

def resolve_session(args) -> BagoSession:
    """Crea y devuelve la BagoSession a partir de los argumentos CLI."""
    creds     = CredentialManager()
    providers = load_providers()
    routing   = load_routing()

    if args.model:
        name, wire, prov = None, None, args.provider or "codex"
        for pn, pd in providers.items():
            if args.model in pd.get("models", {}):
                name = args.model
                wire = pd["models"][args.model].get("wire_name", args.model)
                prov = pn
                break
        if not name:
            console.print(f"[red]Modelo '{args.model}' no encontrado.[/red]")
            sys.exit(1)

    elif args.task:
        name, wire, prov, _ = route_by_task(args.task, routing, providers)
        pi(f"Router BAGO → {name} ({prov}) para: {args.task}")

    else:
        pm = {
            "copilot": "copilot", "codex": "codex",
            "ollama": "ollama-local", "ollama-local": "ollama-local",
            "ollama-cloud": "ollama-cloud", "anthropic": "anthropic",
        }
        chosen = pm.get(args.provider, "") or auto_detect_provider(creds, providers)
        if not args.provider:
            pi(f"Provider detectado: {chosen}")
        name, wire, prov = get_default_model(chosen, providers)
        if not name:
            console.print(Panel(
                "[bold yellow]No hay providers activos.[/bold yellow]\n"
                "Usa [yellow]/login github[/yellow] para Copilot, "
                "[yellow]/login openai[/yellow] para GPT, "
                "[yellow]/login anthropic[/yellow] para Claude, "
                "[yellow]/login ollama[/yellow] para local.",
                title="BAGO — Login requerido", box=box.ROUNDED, border_style="yellow",
            ))
            name, wire, prov = "sin-modelo", "sin-modelo", "none"

    return BagoSession(prov, name, wire, creds)


# ─── Tareas de inicio en paralelo ─────────────────────────────────────────────

def run_startup_tasks(session: BagoSession) -> None:
    """Lanza health scan + HW probe en paralelo, muestra banner y procesa resultados."""
    import concurrent.futures as _cf
    from bago.hw_probe import probe_hardware

    # ── Animación de inicio ───────────────────────────────────────────────────
    if sys.stdout.isatty():
        try:
            import importlib.util as _ilu
            _spec = _ilu.spec_from_file_location(
                "bago_intro", Path(__file__).parent.parent.parent / "bago_intro.py"
            )
            _mod = _ilu.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            _mod.play()
        except Exception:
            pass

    # ── Health scan + HW probe en paralelo ───────────────────────────────────
    _health_future = _hw_future = None
    try:
        _executor = _cf.ThreadPoolExecutor(max_workers=2, thread_name_prefix="bago_startup")
        _health_future = _executor.submit(
            scan_provider_health, session.creds, session.providers, 3
        )
        _hw_future = _executor.submit(probe_hardware)
    except Exception:
        pass

    # Mostrar banner inmediato (sin esperar el health)
    banner(session)

    # ── Resultado health scan ─────────────────────────────────────────────────
    if _health_future:
        try:
            _health = _health_future.result(timeout=4)
            _active_creds = session.creds.active_bago_providers()
            for _pname, _phdata in _health.items():
                if _phdata.get("ok"):
                    session.skip_providers.discard(_pname)
                elif _pname in _active_creds or _pname in ("ollama-local", "ollama-cloud"):
                    session.skip_providers.add(_pname)
            console.print()
            banner(session, health=_health)
            session._last_health = _health
            if all(not v.get("ok") for v in _health.values()):
                console.print(
                    "\n  [bold yellow]⚠  Ningún provider disponible.[/bold yellow]\n"
                    "  Usa [cyan]/login[/cyan] para configurar un provider "
                    "o ejecuta [cyan]ollama serve[/cyan] si tienes Ollama instalado."
                )
        except Exception:
            pass
    else:
        session._last_health = None

    # ── Resultado HW probe ────────────────────────────────────────────────────
    if _hw_future:
        try:
            hw = _hw_future.result(timeout=5)
            session.hw = hw
            try:
                from bago.model_catalog import enrich_with_compat
                enrich_with_compat(hw)
            except Exception:
                pass
            if hw.disk_free_gb < 5:
                console.print(
                    f"  [red]⚠  Disco bajo en {hw.disk_path}: "
                    f"{hw.disk_free_gb:.1f} GB libres. "
                    f"Libera espacio antes de instalar modelos.[/red]"
                )
        except Exception:
            session.hw = None
