"""
Comando /scan — Vista completa de providers y modelos.

Tres secciones:
  DISPONIBLES            → providers ok ahora (verde)
  POTENCIALMENTE DISPONIBLES → en el catálogo pero no configurados (amarillo)
  MISSING                → estuvieron ok, ahora no responden (rojo)
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
from rich.panel import Panel

from ..providers import KNOWN_PROVIDERS_CATALOG, scan_provider_health, update_scan_history
from ..ui import console


def _auth_quota_line(info: dict) -> str:
    auth = info.get("auth_detail")
    quota = info.get("quota_detail")
    if not auth and not quota:
        return ""
    auth = auth or "no comprobado"
    quota = quota or "no comprobada"
    return f"    [dim]└ auth: {auth}  |  cuota/gasto: {quota}[/dim]"


def _cmd_scan(session) -> None:
    """Ejecuta el scan completo y muestra el estado de providers y modelos."""
    console.print("[dim]  Escaneando providers (puede tardar 3-4 s)...[/dim]")

    health = scan_provider_health(session.creds, session.providers, timeout=4)
    # Guardar en historial y obtener MISSING
    missing = update_scan_history(health)

    # ── Clasificar providers ───────────────────────────────────────────────────
    available:    list[tuple[str, dict]] = []
    potentially:  list[tuple[str, dict]] = []

    for pname, catalog in KNOWN_PROVIDERS_CATALOG.items():
        h = health.get(pname, {})
        if h.get("ok"):
            available.append((pname, {**catalog, **h}))
        elif pname in missing:
            pass  # se mostrará en MISSING
        else:
            potentially.append((pname, {**catalog, **h}))

    # ── Sección 1: DISPONIBLES ────────────────────────────────────────────────
    avail_lines: list[str] = []
    for pname, info in available:
        detail = info.get("detail", "OK")
        label  = info.get("label", pname)
        models = info.get("models", [])
        reg_models = list(session.providers.get(pname, {}).get("models", {}).keys())

        avail_lines.append(
            f"  [bold green]●[/bold green] [bold]{label:<26}[/bold]  "
            f"[green]{detail}[/green]"
        )
        # Modelos Ollama instalados (reales)
        if models:
            shown = models[:5]
            extra = f"  +{len(models)-5} más" if len(models) > 5 else ""
            avail_lines.append(
                f"    [dim green]└ instalados: {', '.join(shown)}{extra}[/dim green]"
            )
        # Modelos registrados en el registry BAGO
        if reg_models:
            avail_lines.append(
                f"    [dim]└ registry BAGO: {', '.join(reg_models[:4])}"
                + (f" +{len(reg_models)-4} más" if len(reg_models) > 4 else "")
                + "[/dim]"
            )
        aq = _auth_quota_line(info)
        if aq:
            avail_lines.append(aq)

    avail_section = (
        "\n".join(avail_lines)
        if avail_lines
        else "  [dim](ninguno disponible ahora mismo)[/dim]"
    )

    # ── Sección 2: POTENCIALMENTE DISPONIBLES ─────────────────────────────────
    pot_lines: list[str] = []
    for pname, info in potentially:
        label    = info.get("label", pname)
        setup    = info.get("setup", "")
        requires = info.get("requires", "")
        detail   = info.get("detail", "")

        # Distinguir: "no configurado" vs "configurado pero falla"
        if detail:
            reason = f"[yellow]{detail}[/yellow]"
        else:
            reason = "[dim]no configurado[/dim]"

        pot_lines.append(
            f"  [yellow]◌[/yellow] [bold]{label:<26}[/bold]  {reason}"
        )
        if requires:
            pot_lines.append(f"    [dim]└ requiere: {requires}[/dim]")
        if setup:
            pot_lines.append(f"    [dim]└ setup:    {setup}[/dim]")
        aq = _auth_quota_line(info)
        if aq:
            pot_lines.append(aq)

    pot_section = (
        "\n".join(pot_lines)
        if pot_lines
        else "  [dim](todos los providers conocidos están configurados)[/dim]"
    )

    # ── Sección 3: MISSING ────────────────────────────────────────────────────
    miss_lines: list[str] = []
    for pname, minfo in missing.items():
        catalog   = KNOWN_PROVIDERS_CATALOG.get(pname, {})
        label     = catalog.get("label", pname)
        last_ok   = minfo.get("last_ok", "?")
        # Formatear timestamp
        try:
            import datetime
            dt  = datetime.datetime.fromisoformat(last_ok)
            ago = datetime.datetime.now() - dt
            days = ago.days
            fmt  = dt.strftime("%Y-%m-%d %H:%M")
            since = f"{fmt}  ({days}d atrás)" if days > 0 else fmt
        except Exception:
            since = last_ok[:16] if last_ok else "?"

        lmodels = minfo.get("last_models", [])
        miss_lines.append(
            f"  [bold red]✗[/bold red] [bold]{label:<26}[/bold]  "
            f"[red]último OK: {since}[/red]"
        )
        if lmodels:
            miss_lines.append(
                f"    [dim red]└ modelos que tenía: {', '.join(lmodels[:4])}"
                + (f" +{len(lmodels)-4} más" if len(lmodels) > 4 else "")
                + "[/dim red]"
            )
        # Añadir consejo de setup
        setup = catalog.get("setup", "")
        if setup:
            miss_lines.append(f"    [dim]└ para recuperar: {setup}[/dim]")

    miss_section = (
        "\n".join(miss_lines)
        if miss_lines
        else "  [dim](ningún provider que haya desaparecido)[/dim]"
    )

    # ── Render ────────────────────────────────────────────────────────────────
    total_ok = len(available)
    total_all = len(KNOWN_PROVIDERS_CATALOG)

    # ── Sección 4: CUENTAS REGISTRADAS ───────────────────────────────────────
    am = getattr(getattr(session, "creds", None), "account_manager", None)
    if am and am.accounts:
        acct_lines = am.summary_lines()
        acct_section = "\n".join(acct_lines)
    else:
        acct_section = "  [dim]Sin cuentas multi — usa [yellow]/login add <provider>[/yellow] para agregar[/dim]"

    body = (
        f"[bold green]── DISPONIBLES ({total_ok}/{total_all})[/bold green]\n"
        f"{avail_section}\n\n"
        f"[bold yellow]── POTENCIALMENTE DISPONIBLES[/bold yellow]\n"
        f"{pot_section}\n\n"
        f"[bold red]── MISSING (estuvieron activos)[/bold red]\n"
        f"{miss_section}\n\n"
        f"[bold cyan]── CUENTAS REGISTRADAS[/bold cyan]\n"
        f"{acct_section}"
    )

    console.print(Panel(
        body,
        title="[bold]BAGO / Scan de Providers y Modelos[/bold]",
        box=box.ROUNDED,
        expand=False,
    ))

    # Guardar health en session para reutilizar en /status sin re-escanear
    session._last_health = health



def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(__file__ + " --test: PASS (imports OK)")
    return 0


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
