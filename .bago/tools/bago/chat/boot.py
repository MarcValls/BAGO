"""bago.chat.boot — resolución de provider al arranque y tareas paralelas de inicio."""

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

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
        # buscar en providers.json
        for pn, pd in providers.items():
            if args.model in pd.get("models", {}):
                name = args.model
                wire = pd["models"][args.model].get("wire_name", args.model)
                prov = pn
                break
        # si no esta en providers.json pero es un modelo local instalado
        if not name:
            from bago.model_availability import installed_ollama_models
            if args.model in installed_ollama_models():
                name = args.model
                wire = args.model
                prov = "ollama-local"
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
            "local": "ollama-local", "github-models": "github-models",
        }
        chosen = pm.get(args.provider, "") or auto_detect_provider(creds, providers)
        if not args.provider:
            pi(f"Provider detectado: {chosen}")

        # ── Validar que el provider elegido realmente funciona ───────────────
        # Usamos health check rápido; si falla, intentamos fallback ordenado
        from ..provider_health import scan_provider_health
        active = creds.active_bago_providers()
        health = {}
        if chosen and chosen != "none":
            try:
                health = scan_provider_health(creds, providers, timeout=3)
            except Exception:
                pass
            chosen_health = health.get(chosen, {})
            if not chosen_health.get("ok") and not getattr(args, 'single_model', False):
                # Intentar siguiente provider activo válido
                for fallback in ("ollama-local", "copilot", "github-models", "codex", "anthropic", "ollama-cloud"):
                    if fallback == chosen:
                        continue
                    if fallback in active and health.get(fallback, {}).get("ok"):
                        chosen = fallback
                        pi(f"Fallback provider: {chosen}")
                        break
                else:
                    chosen = "none"
                    pi("Ningún provider válido encontrado")

        name, wire, prov = get_default_model(chosen, providers)
        if not name:
            session = BagoSession("none", "sin-modelo", "sin-modelo", creds, single_model=getattr(args, 'single_model', False))
            from bago.menus.auth import _cmd_login
            _cmd_login(session)
            providers = load_providers()
            chosen = auto_detect_provider(creds, providers)
            if chosen and chosen != "none":
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
            session.provider = prov
            session.model_name = name
            session.wire_name = wire
            session.providers = providers
            source = session._update_model_origin(prov, name, wire)
            session.last_route = {
                "mode": "auto",
                "provider": prov,
                "model": name,
                "reason": "login requerido",
                "service": source.get("service", ""),
                "route": source.get("route", ""),
                "backend": source.get("backend", ""),
            }
            return session

    return BagoSession(prov, name, wire, creds, single_model=getattr(args, 'single_model', False))


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
    _executor = None
    try:
        _executor = _cf.ThreadPoolExecutor(max_workers=2, thread_name_prefix="bago_startup")
        _health_future = _executor.submit(
            scan_provider_health, session.creds, session.providers, 2
        )
        _hw_future = _executor.submit(probe_hardware)
    except Exception:
        pass

    # -- Resultado health scan --------------------------------------------------
    _health = None
    if _health_future:
        try:
            _health = _health_future.result(timeout=5)
        except KeyboardInterrupt:
            _health = None
            if _executor:
                _executor.shutdown(wait=False, cancel_futures=True)
            raise
        except Exception:
            _health = None

    if _health is not None:
        _active_creds = session.creds.active_bago_providers()
        for _pname, _phdata in _health.items():
            if _phdata.get("ok"):
                session.skip_providers.discard(_pname)
            elif _pname in _active_creds or _pname in ("ollama-local", "ollama-cloud"):
                session.skip_providers.add(_pname)
        banner(session, health=_health)
        session._last_health = _health
        if all(not v.get("ok") for v in _health.values()):
            console.print(
                "\n  [bold yellow]⚠  Ningún provider disponible.[/bold yellow]\n"
                "  Usa [cyan]/login[/cyan] para configurar un provider "
                "o ejecuta [cyan]ollama serve[/cyan] si tienes Ollama instalado."
            )
    else:
        banner(session)
        session._last_health = None


    # ── Resultado HW probe ────────────────────────────────────────────────────
    if _hw_future:
        try:
            hw = _hw_future.result(timeout=5)
            session.hw = hw
        except KeyboardInterrupt:
            if _executor:
                _executor.shutdown(wait=False, cancel_futures=True)
            raise
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
