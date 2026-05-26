#!/usr/bin/env python3
"""bago_telemetry.py — Observabilidad local para BAGO.

Equivalente a Azure Application Insights pero sin ningún servicio cloud.
Registra eventos en ~/.bago/telemetry/events.jsonl (JSONL, append-only).
Zero dependencias externas — solo stdlib.

API programática:
    tel = Telemetry()
    tel.track_command("health", args=[], duration_s=1.2, exit_code=0)
    tel.track_exception(exc, command="cosecha")
    tel.track_event("validate_pass", properties={"score": 80})
    tel.track_metric("health_score", 80.0)

CLI:
    bago telemetry              → resumen de estadísticas
    bago telemetry --stats      → estadísticas detalladas por comando
    bago telemetry --errors     → excepciones recientes
    bago telemetry --last N     → últimos N eventos
    bago telemetry --clear      → borrar telemetría (pide confirmación)
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

import json
import os
import sys
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

_xdg = os.environ.get("XDG_DATA_HOME")
TELEMETRY_DIR: Path = (
    (Path(_xdg) / "bago" / "telemetry") if _xdg
    else (Path.home() / ".bago" / "telemetry")
)
EVENTS_FILE = TELEMETRY_DIR / "events.jsonl"


# ── Writer ─────────────────────────────────────────────────────────────────────

def _append(record: dict) -> None:
    """Append one JSONL record. Thread-safe via file locking. Never raises."""
    try:
        TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        with EVENTS_FILE.open("a", encoding="utf-8") as fh:
            try:
                import fcntl  # Unix only
                fcntl.flock(fh, fcntl.LOCK_EX)
                fh.write(line)
                fcntl.flock(fh, fcntl.LOCK_UN)
            except ImportError:
                fh.write(line)  # Windows: sin locking (aceptable para CLI single-user)
    except Exception:
        pass  # telemetría nunca bloquea la ejecución principal


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── API pública ────────────────────────────────────────────────────────────────

class Telemetry:
    """Sink de telemetría local. Instanciar una vez por proceso o usar las funciones módulo."""

    def track_command(
        self,
        cmd: str,
        args: list | None = None,
        duration_s: float | None = None,
        exit_code: int | None = None,
    ) -> None:
        """Registra una ejecución de comando bago."""
        props: dict = {"args": list(args or [])}
        metrics: dict = {}
        if exit_code is not None:
            props["exit_code"] = exit_code
            props["success"] = exit_code == 0
        if duration_s is not None:
            metrics["duration_s"] = round(duration_s, 4)
        _append({"ts": _now(), "type": "command", "name": cmd,
                 "properties": props, "metrics": metrics})

    def track_exception(
        self,
        exc: BaseException,
        command: str = "",
        extra: dict | None = None,
    ) -> None:
        """Registra una excepción con stack trace completo."""
        props: dict = {
            "command": command,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        if extra:
            props.update(extra)
        _append({"ts": _now(), "type": "exception", "name": type(exc).__name__,
                 "properties": props})

    def track_event(
        self,
        name: str,
        properties: dict | None = None,
        metrics: dict | None = None,
    ) -> None:
        """Registra un evento personalizado con propiedades y métricas opcionales."""
        rec: dict = {"ts": _now(), "type": "event", "name": name}
        if properties:
            rec["properties"] = properties
        if metrics:
            rec["metrics"] = metrics
        _append(rec)

    def track_metric(
        self, name: str, value: float, properties: dict | None = None
    ) -> None:
        """Registra una métrica numérica (p.ej. health_score, duración)."""
        rec: dict = {"ts": _now(), "type": "metric", "name": name, "value": value}
        if properties:
            rec["properties"] = properties
        _append(rec)


# Instancia global para uso directo desde el launcher
_tel = Telemetry()
track_command   = _tel.track_command
track_exception = _tel.track_exception
track_event     = _tel.track_event
track_metric    = _tel.track_metric


# ── Lector ─────────────────────────────────────────────────────────────────────

def _load_events(limit: int | None = None) -> list[dict]:
    if not EVENTS_FILE.exists():
        return []
    events: list[dict] = []
    with EVENTS_FILE.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events[-limit:] if limit else events


# ── Vistas CLI ─────────────────────────────────────────────────────────────────

_USE_COLOR = sys.stdout.isatty()
def _c(code: str, t: str) -> str:
    return f"\033[{code}m{t}\033[0m" if _USE_COLOR else t
GREEN  = lambda t: _c("1;32", t)
RED    = lambda t: _c("1;31", t)
YELLOW = lambda t: _c("1;33", t)
BOLD   = lambda t: _c("1",    t)


def _view_summary(events: list[dict]) -> None:
    if not events:
        print("  Sin telemetría local. Ejecuta algunos comandos bago primero.")
        return

    cmds    = [e for e in events if e.get("type") == "command"]
    errors  = [e for e in events if e.get("type") == "exception"]
    custom  = [e for e in events if e.get("type") == "event"]
    metrics = [e for e in events if e.get("type") == "metric"]

    ok   = sum(1 for e in cmds if e.get("properties", {}).get("success") is True)
    fail = sum(1 for e in cmds if e.get("properties", {}).get("success") is False)

    oldest = events[0].get("ts", "?")[:10]
    newest = events[-1].get("ts", "?")[:10]

    print(f"\n  {BOLD('📊 BAGO Telemetría Local')}  ({oldest} → {newest})")
    print(f"  {'─' * 44}")
    ok_str   = GREEN(f"✅ {ok}")
    fail_str = RED(f"❌ {fail}") if fail else f"❌ {fail}"
    print(f"  Comandos ejecutados : {len(cmds):>6}  ({ok_str}  {fail_str})")
    print(f"  Excepciones         : {RED(str(len(errors))):>6}" if errors else
          f"  Excepciones         :      0")
    print(f"  Eventos custom      : {len(custom):>6}")
    print(f"  Métricas            : {len(metrics):>6}")
    print(f"  Total registros     : {len(events):>6}")

    if cmds:
        top = Counter(e.get("name") for e in cmds).most_common(5)
        print(f"\n  {BOLD('Top comandos:')}")
        max_count = top[0][1] if top else 1
        for name, count in top:
            bar_len = max(1, round(count / max_count * 20))
            bar = GREEN("█" * bar_len)
            print(f"    {name:<18} {bar} {count}")

    if errors:
        last_err = errors[-1]
        ts  = last_err.get("ts", "?")[:19].replace("T", " ")
        cmd = last_err.get("properties", {}).get("command", "?")
        print(f"\n  {RED('Último error:')} [{ts}] {last_err.get('name','?')} en cmd={cmd}")

    print()


def _view_stats(events: list[dict]) -> None:
    cmds_data: dict = defaultdict(lambda: {"ok": 0, "fail": 0, "durations": []})
    for e in events:
        if e.get("type") != "command":
            continue
        name  = e.get("name", "?")
        props = e.get("properties", {})
        dur   = e.get("metrics", {}).get("duration_s")
        if props.get("success") is True:
            cmds_data[name]["ok"] += 1
        elif props.get("success") is False:
            cmds_data[name]["fail"] += 1
        if dur is not None:
            cmds_data[name]["durations"].append(dur)

    if not cmds_data:
        print("  Sin datos de comandos aún.")
        return

    header = f"  {'COMANDO':<20} {'OK':>5} {'FAIL':>5} {'TOTAL':>6} {'AVG(s)':>8}"
    print(f"\n{BOLD(header)}")
    print("  " + "─" * 50)
    for name, d in sorted(cmds_data.items(), key=lambda x: -(x[1]["ok"] + x[1]["fail"])):
        total    = d["ok"] + d["fail"]
        avg      = sum(d["durations"]) / len(d["durations"]) if d["durations"] else None
        avg_str  = f"{avg:.2f}" if avg is not None else "  —"
        fail_col = RED(str(d["fail"])) if d["fail"] else str(d["fail"])
        print(f"  {name:<20} {GREEN(str(d['ok'])):>5} {fail_col:>5} {total:>6} {avg_str:>8}")
    print()


def _view_errors(events: list[dict]) -> None:
    errors = [e for e in events if e.get("type") == "exception"]
    if not errors:
        print(f"  {GREEN('✅ Sin excepciones registradas.')}")
        return
    print(f"\n  {RED(BOLD('Excepciones recientes'))} ({len(errors)} total)\n")
    for e in errors[-10:]:
        ts    = e.get("ts", "?")[:19].replace("T", " ")
        name  = e.get("name", "?")
        props = e.get("properties", {})
        print(f"  {RED('●')} [{ts}] {BOLD(name)} — cmd={props.get('command', '?')}")
        print(f"    {props.get('message', '')}")
        tb = props.get("traceback", "")
        if tb:
            relevant = [l.strip() for l in tb.strip().splitlines() if l.strip() and "File " in l]
            if relevant:
                print(f"    {YELLOW(relevant[-1])}")
        print()


def _view_last(events: list[dict], n: int) -> None:
    print(f"\n  {BOLD(f'Últimos {n} eventos:')}\n")
    for e in events[-n:]:
        ts      = e.get("ts", "?")[:19].replace("T", " ")
        etype   = e.get("type", "?")
        name    = e.get("name", "?")
        props   = e.get("properties", {})
        metrics = e.get("metrics", {})
        dur_str = f"  {metrics['duration_s']:.2f}s" if metrics.get("duration_s") is not None else ""
        success = props.get("success")
        icon    = GREEN("✅") if success is True else (RED("❌") if success is False else "·")
        print(f"  {icon} [{ts}] {etype:<10} {BOLD(name)}{dur_str}")
    print()


# ── Subcommand launchers ───────────────────────────────────────────────────────

def _launch_live(extra_args: list) -> None:
    """Launch the curses live TUI viewer (bago_telemetry_live.py)."""
    import subprocess
    script = Path(__file__).parent / "bago_telemetry_live.py"
    if not script.exists():
        print("  ❌ bago_telemetry_live.py no encontrado.", file=sys.stderr)
        sys.exit(1)
    result = subprocess.run([sys.executable, str(script)] + extra_args)
    sys.exit(result.returncode)


def _launch_web(extra_args: list) -> None:
    """Launch the HTTP web dashboard (bago_telemetry_web.py)."""
    import subprocess
    script = Path(__file__).parent / "bago_telemetry_web.py"
    if not script.exists():
        print("  ❌ bago_telemetry_web.py no encontrado.", file=sys.stderr)
        sys.exit(1)
    result = subprocess.run([sys.executable, str(script)] + extra_args)
    sys.exit(result.returncode)


# ── Entrypoint CLI ─────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]

    # Subcommand dispatch: live TUI or web dashboard
    if args and args[0] == "live":
        _launch_live(args[1:])
        return
    if args and args[0] == "web":
        _launch_web(args[1:])
        return

    if "--clear" in args:
        events = _load_events()
        if not sys.stdin.isatty():
            print("  Usa --clear en un TTY interactivo.")
            sys.exit(1)
        resp = input(f"  ¿Borrar {len(events)} registros en {EVENTS_FILE}? [s/N] ")
        if resp.strip().lower() in ("s", "si", "sí", "y", "yes"):
            EVENTS_FILE.unlink(missing_ok=True)
            print("  Telemetría borrada. ✅")
        else:
            print("  Cancelado.")
        return

    if "--last" in args:
        idx = args.index("--last")
        n = int(args[idx + 1]) if idx + 1 < len(args) and args[idx + 1].isdigit() else 20
        _view_last(_load_events(), n)
    elif "--stats" in args:
        _view_stats(_load_events())
    elif "--errors" in args:
        _view_errors(_load_events())
    else:
        _view_summary(_load_events())


if __name__ == "__main__":
    main()
