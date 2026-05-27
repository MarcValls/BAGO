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
from bago.model_registry import print_routing_snapshot
from bago.providers import (
    auto_detect_provider, get_default_model, route_by_task, scan_provider_health,
)
from bago.ui import console, pi


# ─── Resolución de provider/modelo ────────────────────────────────────────────

def _healthy_providers(creds, providers: dict) -> tuple[dict, dict]:
    """Filtra providers por health real antes de arrancar la sesión."""
    try:
        health = scan_provider_health(creds, providers, 2)
    except Exception:
        health = {}
    healthy = {
        pname: pdata
        for pname, pdata in providers.items()
        if health.get(pname, {}).get("ok")
    }
    return healthy, health


def _available_models_from_health(providers: dict, health: dict) -> dict[str, set[str]]:
    """Construye el inventario de modelos realmente disponibles tras el health scan."""
    available: dict[str, set[str]] = {}
    for pname, pdata in providers.items():
        info = health.get(pname, {})
        if not info.get("ok"):
            continue
        models = set(info.get("models") or [])
        if not models:
            models = set((pdata or {}).get("models", {}).keys())
        available[pname] = models
    return available


def _pick_first_available(creds, providers: dict, preferred: list[str]) -> tuple[str, str, str]:
    """Escoge el primer provider/modelo disponible siguiendo una prioridad."""
    active = [p for p in creds.active_bago_providers() if p in providers]
    pool = providers
    for pname in preferred:
        if pname in active and pname in pool:
            picked = get_default_model(pname, pool)
            if picked and picked[0]:
                return picked
    for pname in active:
        picked = get_default_model(pname, pool)
        if picked and picked[0]:
            return picked
    return "", "", ""

def resolve_session(args) -> BagoSession:
    """Crea y devuelve la BagoSession a partir de los argumentos CLI."""
    creds     = CredentialManager()
    providers = load_providers()
    routing   = load_routing()
    healthy_providers, health = _healthy_providers(creds, providers)
    providers_for_boot = healthy_providers if health else providers
    preferred_order = ["ollama-local", "copilot", "codex", "anthropic", "ollama-cloud", "replicate"]

    if args.model:
        name, wire, prov = None, None, args.provider or "codex"
        # buscar en providers.json
        for pn, pd in providers_for_boot.items():
            if args.model in pd.get("models", {}):
                name = args.model
                wire = pd["models"][args.model].get("wire_name", args.model)
                prov = pn
                break
        # si no esta en providers.json pero es un modelo local instalado
        if not name:
            from bago.model_availability import installed_ollama_models
            if args.model in installed_ollama_models() and "ollama-local" in providers_for_boot:
                name = args.model
                wire = args.model
                prov = "ollama-local"
        if not name:
            fallback = _pick_first_available(creds, providers_for_boot, preferred_order)
            if fallback[0]:
                name, wire, prov = fallback
                console.print(
                    f"[yellow]Modelo '{args.model}' no disponible al arrancar; usando {name} ({prov}).[/yellow]"
                )
            else:
                console.print(f"[red]No hay modelos disponibles para arrancar.[/red]")
                sys.exit(1)

    elif args.task:
        name, wire, prov, _ = route_by_task(args.task, routing, providers_for_boot, current_provider=args.provider or None)
        pi(f"Router BAGO → {name} ({prov}) para: {args.task}")
        if not name:
            fallback = _pick_first_available(creds, providers_for_boot, preferred_order)
            if fallback[0]:
                name, wire, prov = fallback
                pi(f"Fallback de arranque → {name} ({prov})")

    else:
        pm = {
            "copilot": "copilot", "codex": "codex",
            "ollama": "ollama-local", "ollama-local": "ollama-local",
            "ollama-cloud": "ollama-cloud", "anthropic": "anthropic",
            "local": "ollama-local", "replicate": "replicate",
        }
        chosen = pm.get(args.provider, "") or auto_detect_provider(creds, providers_for_boot)
        if chosen not in providers_for_boot:
            chosen = next((p for p in preferred_order if p in providers_for_boot), chosen)
        if not args.provider:
            pi(f"Provider detectado: {chosen}")
        name, wire, prov = get_default_model(chosen, providers_for_boot)
        if not name:
            fallback = _pick_first_available(creds, providers_for_boot, preferred_order)
            if fallback[0]:
                name, wire, prov = fallback
                pi(f"Fallback de arranque → {name} ({prov})")
            else:
                name, wire, prov = "sin-modelo", "sin-modelo", "none"
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

    session = BagoSession(prov, name, wire, creds)
    session.providers = providers_for_boot
    session.available_models = _available_models_from_health(providers_for_boot, health) if health else {}
    return session


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
        filtered_providers = {
            pname: session.providers[pname]
            for pname, _phdata in _health.items()
            if _phdata.get("ok") and pname in session.providers
        }
        session.providers = filtered_providers
        session.available_models = _available_models_from_health(filtered_providers, _health)
        for _pname, _phdata in _health.items():
            if _phdata.get("ok"):
                session.skip_providers.discard(_pname)
            elif _pname in _active_creds or _pname in ("ollama-local", "ollama-cloud"):
                session.skip_providers.add(_pname)
        banner(session, health=_health)
        print_routing_snapshot(session, health=_health, available_models=session.available_models)
        session._last_health = _health
        if all(not v.get("ok") for v in _health.values()):
            console.print(
                "\n  [bold yellow]⚠  Ningún provider disponible.[/bold yellow]\n"
                "  Usa [cyan]/login[/cyan] para configurar un provider "
                "o ejecuta [cyan]ollama serve[/cyan] si tienes Ollama instalado."
            )
    else:
        banner(session)
        print_routing_snapshot(session, available_models=session.available_models)
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


def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(f"{Path(__file__).name} --test: PASS (imports OK)")
    return 0
if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
