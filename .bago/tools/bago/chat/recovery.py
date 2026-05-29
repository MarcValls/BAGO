"""bago.chat.recovery — flujos de recuperación ante fallos de modelo o provider."""

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from bago.providers import ollama_probe, ollama_pull, get_default_model
from bago.llm import _is_cloud_auth_error, _is_cloud_connection_error
from bago.ui import console, pi, pe, _menu_select, _menu_input
from bago.ollama_runtime import default_ollama_base_url


# ─── Ollama ───────────────────────────────────────────────────────────────────

def _ollama_recovery_flow(session, model_name: str) -> bool:
    """Recuperación interactiva cuando Ollama no tiene el modelo o no está activo.

    Retorna True si la sesión queda lista para reintentar la llamada LLM.
    """
    from bago.menus.auth import _cmd_login

    base_url = default_ollama_base_url()
    probe = ollama_probe(base_url)

    if not probe["running"]:
        console.print(
            f"\n  [yellow]⚠  Ollama no responde en [bold]{base_url}[/bold][/yellow]"
        )
        choices = [
            ("custom_url", "Sí — introduzco la URL donde está corriendo"),
            ("install",    "No — quiero arrancar / instalar Ollama"),
            ("other",      "Usar otro provider"),
        ]
        sel = _menu_select(
            "Ollama inaccesible",
            "¿Sabes si Ollama está instalado en una URL diferente?",
            choices,
        )

        if sel == "custom_url":
            url = _menu_input(
                "URL de Ollama",
                "Introduce la URL base de Ollama:",
                default=default_ollama_base_url().replace("127.0.0.1", "localhost"),
            )
            if url:
                probe2 = ollama_probe(url.strip())
                if probe2["running"]:
                    base_url = url.strip()
                    probe = probe2
                    console.print(f"  [green]✔ Ollama encontrado en {base_url}[/green]")
                    session.skip_providers.discard("ollama-local")
                    session.skip_providers.discard("ollama-cloud")
                else:
                    pe(f"No se pudo conectar a Ollama en {url}")
                    sel = "other"
            else:
                sel = "other"

        if sel == "install":
            console.print(
                "\n  [cyan]Para instalar Ollama visita:[/cyan] https://ollama.com/download\n"
                "  Una vez instalado, ejecuta en otra terminal:\n"
                f"    [bold]ollama serve[/bold]\n"
                f"    [bold]ollama pull {model_name or 'qwen2.5-coder:7b'}[/bold]\n"
                "  Luego vuelve a BAGO y escribe tu mensaje.\n"
            )
            return False

        if sel == "other" or not probe["running"]:
            return _fallback_to_other_provider(session)

    # ── Ollama activo: ver qué modelos hay ────────────────────────────────────
    available = probe["models"]

    if not model_name:
        model_name = session.wire_name or "qwen2.5-coder:7b"

    if any(model_name in m or m.startswith(model_name.split(":")[0]) for m in available):
        console.print(f"  [green]✔ Modelo '{model_name}' encontrado. Reintentando...[/green]")
        return True

    if available:
        console.print(
            f"\n  [yellow]⚠  Modelo [bold]{model_name}[/bold] no instalado.[/yellow]\n"
            f"  Modelos disponibles en Ollama: [cyan]{', '.join(available[:8])}[/cyan]"
        )
        choices_rows = [(m, m) for m in available[:8]]
        choices_rows += [
            ("install", f"Instalar '{model_name}' ahora  (ollama pull)"),
            ("other",   "Usar otro provider"),
        ]
        sel = _menu_select(
            "Modelo no encontrado",
            f"¿Qué hacemos con '{model_name}'?",
            choices_rows,
        )
        if sel == "install":
            return _do_ollama_pull(model_name, base_url, session)
        elif sel == "other":
            return _fallback_to_other_provider(session)
        else:
            pi(f"Cambiando a {sel}...")
            session.wire_name  = sel
            session.model_name = sel.split(":")[0]
            session._update_model_origin(session.provider, session.model_name, session.wire_name)
            return True
    else:
        console.print(
            "\n  [yellow]⚠  Ollama está activo pero no tiene modelos instalados.[/yellow]"
        )
        choices = [
            ("install", f"Instalar '{model_name}'  (ollama pull)"),
            ("other",   "Usar otro provider"),
        ]
        sel = _menu_select("Sin modelos en Ollama", "¿Qué deseas hacer?", choices)
        if sel == "install":
            return _do_ollama_pull(model_name, base_url, session)
        return _fallback_to_other_provider(session)


def _do_ollama_pull(model_name: str, base_url: str, session) -> bool:
    """Descarga el modelo y, si tiene éxito, actualiza la sesión."""
    console.print(f"\n  [cyan]⬇  Descargando [bold]{model_name}[/bold]...[/cyan]\n")
    ok = ollama_pull(model_name, base_url)
    if ok:
        console.print(f"\n  [green]✔ Modelo '{model_name}' instalado correctamente.[/green]")
        session.wire_name = model_name
        session._update_model_origin(session.provider, session.model_name, session.wire_name)
        session.skip_providers.discard("ollama-local")
        session.skip_providers.discard("ollama-cloud")
        return True
    else:
        pe(f"No se pudo instalar '{model_name}'.")
        return _fallback_to_other_provider(session)


def _fallback_to_other_provider(session) -> bool:
    """Si hay otros providers activos los usa; si no, redirige a /login."""
    from bago.menus.auth import _cmd_login

    session.skip_providers.update({"ollama-local", "ollama-cloud"})
    active = session.creds.active_bago_providers()
    other  = [p for p in active if p not in ("ollama-local", "ollama-cloud")]

    if other:
        prov = other[0]
        name, wire, _ = get_default_model(prov, session.providers)
        if name:
            session.provider, session.model_name, session.wire_name = prov, name, wire
            source = session._update_model_origin(prov, name, wire)
            session.switches = getattr(session, "switches", 0) + 1
            session.last_route = {
                "mode": "manual",
                "provider": prov,
                "model": name,
                "reason": "recovery fallback",
                "service": source.get("service", ""),
                "route": source.get("route", ""),
                "backend": source.get("backend", ""),
            }
            pi(f"Cambiando a {name} ({prov}) — el modelo Ollama no está disponible.")
            return True

    console.print(
        "\n  [yellow]No hay providers alternativos activos.[/yellow]\n"
        "  Abriendo pantalla de registro de providers...\n"
    )
    _cmd_login(session)
    return False


# ─── Cloud ────────────────────────────────────────────────────────────────────

def _cloud_recovery_flow(session, exc) -> bool:
    """Recovery para errores de autenticación o conexión en providers cloud.

    Muestra el motivo, marca el provider como no disponible y cambia a otro.
    Retorna True si la sesión queda lista para reintentar.
    """
    from bago.menus.auth import _cmd_login

    prov = session.provider
    if _is_cloud_auth_error(exc):
        console.print(
            f"\n  [yellow]⚠  Autenticación fallida en [bold]{prov}[/bold][/yellow]\n"
            f"  Token inválido o expirado. Ejecuta [cyan]/login {prov}[/cyan] para renovar."
        )
    else:
        console.print(
            f"\n  [yellow]⚠  Sin conexión con [bold]{prov}[/bold][/yellow]\n"
            f"  Comprueba tu acceso a internet o el estado del servicio."
        )

    session.skip_providers.add(prov)
    active = session.creds.active_bago_providers()
    other  = [p for p in active if p not in session.skip_providers]

    if other:
        new_prov = other[0]
        name, wire, _ = get_default_model(new_prov, session.providers)
        if name:
            session.provider, session.model_name, session.wire_name = new_prov, name, wire
            source = session._update_model_origin(new_prov, name, wire)
            session.switches = getattr(session, "switches", 0) + 1
            session.last_route = {
                "mode": "manual",
                "provider": new_prov,
                "model": name,
                "reason": "cloud recovery fallback",
                "service": source.get("service", ""),
                "route": source.get("route", ""),
                "backend": source.get("backend", ""),
            }
            pi(f"Cambiando a {name} ({new_prov}) — {prov} no disponible.")
            return True

    console.print(
        "\n  [yellow]No hay providers alternativos disponibles.[/yellow]\n"
        "  Abriendo pantalla de registro de providers...\n"
    )
    _cmd_login(session)
    return False



def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(__file__ + " --test: PASS (imports OK)")
    return 0


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
