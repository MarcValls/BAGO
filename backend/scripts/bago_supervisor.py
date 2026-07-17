#!/usr/bin/env python3
"""
bago_supervisor.py — Modo "siempre vivo" para BAGO.

Arranca un watchdog en background que mantiene la instalación con vida:
vigila procesos python colgados, WAL de SQLite inflado, sockets en TIME_WAIT
y watchers huérfanos. Cuando detecta un callejón sin salida, aplica salida
limpia (graceful shutdown) sin pérdida de evidencia y deja un evento en el
log. El proceso solo muere si vos le decís `bago sup stop`.

Uso:
    bago sup start           Arranca el supervisor en background (idempotente)
    bago sup stop            Cierra limpiamente el supervisor y todo lo que él
                              arrancó (graceful: avisa primero, espera, mata)
    bago sup status          Muestra heartbeat, último evento, PID, uptime
    bago sup status --json   Igual, en JSON
    bago sup attach          Muestra el log en vivo (tail -f)

Archivos:
    ~/.gabo/state/supervisor.json     Estado vivo (pid, started_at, last_event)
    ~/.gabo/state/supervisor.log      Eventos append-only (capped 1 MB)
    ~/.gabo/state/supervisor.lock     lockfile (flock)

Políticas de callejón sin salida (orden de severidad):
    1) Cualquier subproceso BAGO lleva >5 min sin heartbeat   -> SIGTERM
    2) Cualquier python.exe con >85% RAM por >30 s            -> SIGTERM
    3) knowledge.db-wal > 50 MB                                -> wal_checkpoint + nota
    4) >50 conexiones TIME_WAIT al puerto 11434 (ollama)      -> nota + esperar
    5) Cualquier proceso BAGO ignora SIGTERM >10 s            -> SIGKILL (último)

Si vos estás en medio de algo interactivo (otro bago en foreground), el
supervisor NO lo toca: solo vigila lo que él mismo arrancó y los python.exe
que él reconoce como hijos (los que tengan la marca "BAGO_CHILD=1" en su
entorno). Eso es la "salida limpia" que pediste: nunca te pisa la sesión.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bago_core.versioning import read_release_version
from bago_core.user_state_paths import ensure_user_roots, state_root, supervisor_state_file, supervisor_log_file, supervisor_lock_file, supervisor_stop_file, legacy_user_root

# ── Constantes ───────────────────────────────────────────────────────────────
ensure_user_roots()
STATE_DIR = state_root()
STATE_FILE   = supervisor_state_file()
LOG_FILE     = supervisor_log_file()
LOCK_FILE    = supervisor_lock_file()
STOP_FILE    = supervisor_stop_file()  # sentinel: presente = salir limpio
LOG_MAX_BYTES = 1_000_000  # 1 MB
SUPERVISOR_VERSION = read_release_version(ROOT)

# Ventanas (segundos) — todas generosas para no patear a un humano
WATCHDOG_TICK_S       = 5
HEARTBEAT_STALE_AFTER = 300   # 5 min sin HB → callejón
RAM_HIGH_PCT          = 85.0
RAM_HIGH_DWELL_S      = 30
WAL_HIGH_BYTES        = 50 * 1024 * 1024
OLLAMA_PORT           = 11434
TIME_WAIT_HIGH        = 50
GRACEFUL_TERM_WAIT_S  = 10
CHILD_MARKER_ENV      = "BAGO_CHILD"

# ── Logging append con cap ───────────────────────────────────────────────────
def _log(level: str, msg: str) -> None:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    line = f"{ts}\t{level}\t{msg}\n"
    try:
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > LOG_MAX_BYTES:
            # cap: rotar a .1
            old = LOG_FILE.with_suffix(".log.1")
            if old.exists():
                old.unlink()
            LOG_FILE.rename(old)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass
    # eco a stderr si es foreground
    if level in ("ERROR", "FATAL"):
        print(line.rstrip(), file=sys.stderr)

# ── Estado vivo ──────────────────────────────────────────────────────────────
def _read_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

def _write_state(s: dict[str, Any]) -> None:
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE_FILE)

# ── Lockfile (advisory, portabilidad Windows) ────────────────────────────────
def _acquire_lock_nonblocking() -> bool:
    """Devuelve True si pudimos tomar el lock; False si ya hay supervisor."""
    if LOCK_FILE.exists():
        try:
            existing = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        pid = existing.get("pid")
        if pid and _pid_alive(pid):
            return False
        # lockfile huérfano
        try:
            LOCK_FILE.unlink()
        except OSError:
            pass
    LOCK_FILE.write_text(json.dumps({"pid": os.getpid(), "at": _now()}), encoding="utf-8")
    return True

def _release_lock() -> None:
    try:
        LOCK_FILE.unlink()
    except OSError:
        pass

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _pid_alive(pid: int) -> bool:
    if pid <= 0 or pid == os.getpid():
        return False
    try:
        if sys.platform == "win32":
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=5,
                encoding="utf-8", errors="replace",
                **_hidden_subprocess_kwargs(),
            )
            if not out.stdout or "INFO:" in out.stdout:
                return False
            return str(pid) in out.stdout
        os.kill(pid, 0)
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False

def _hidden_subprocess_kwargs() -> dict[str, Any]:
    """Evita ventanas consola al lanzar helpers desde el supervisor en Windows."""
    if sys.platform != "win32":
        return {}
    kwargs: dict[str, Any] = {}
    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    kwargs["creationflags"] = create_no_window
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        kwargs["startupinfo"] = startupinfo
    except (AttributeError, OSError):
        pass
    return kwargs

# ── Inspección: hijos, WAL, RAM, sockets ────────────────────────────────────
def _list_bago_children() -> list[dict[str, Any]]:
    """Lista PIDs de python.exe cuyo CommandLine parece de BAGO.

    En Windows usa Get-CimInstance vía PowerShell (más estable que wmic en
    Win11 24H2+). Si todo falla, devuelve lista vacía — el supervisor sigue
    vivo, simplemente no ve hijos. Esa es la política de "salida limpia":
    un callejón en la inspección jamás mata al supervisor.
    """
    needles = ("BAGO", "bago_core", "ingest_knowledge",
               "real_fallback", "embed_mixed", "watcher_inbox",
               "auto_daily_kb", "auto_wal_vacuum", "promote-dev")
    if sys.platform != "win32":
        return []
    try:
        ps = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" "
             "| Select-Object ProcessId,CommandLine "
             "| ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="replace",
            **_hidden_subprocess_kwargs(),
        )
        if not ps.stdout.strip():
            return []
        data = json.loads(ps.stdout)
        rows = data if isinstance(data, list) else [data]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError,
            json.JSONDecodeError, ValueError) as e:
        _log("WARN", f"_list_bago_children: inspección falló: {type(e).__name__}: {e}")
        return []

    hits: list[dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        cmd = r.get("CommandLine") or ""
        if any(n in cmd for n in needles):
            try:
                pid = int(r.get("ProcessId") or 0)
            except (TypeError, ValueError):
                continue
            if pid and pid != os.getpid():
                hits.append({"pid": pid, "cmd": cmd[:200]})
    return hits

def _ram_pct(pid: int) -> float | None:
    if sys.platform != "win32":
        return None
    try:
        ps = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-Process -Id {pid} -ErrorAction SilentlyContinue)"
             f"|Select-Object -ExpandProperty WorkingSet64"],
            capture_output=True, text=True, timeout=5,
            encoding="utf-8", errors="replace",
            **_hidden_subprocess_kwargs(),
        )
        used = int(ps.stdout.strip() or 0)
        total = int(subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"],
            capture_output=True, text=True, timeout=5,
            encoding="utf-8", errors="replace",
            **_hidden_subprocess_kwargs(),
        ).stdout.strip() or 1)
        return 100.0 * used / max(total, 1)
    except (ValueError, subprocess.TimeoutExpired, OSError):
        return None

def _wal_size() -> int:
    p = STATE_DIR / "knowledge.db-wal"
    return p.stat().st_size if p.exists() else 0

def _wal_checkpoint() -> bool:
    p = STATE_DIR / "knowledge.db"
    if not p.exists():
        return False
    try:
        con = sqlite3.connect(str(p), timeout=5)
        con.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        con.close()
        return True
    except sqlite3.Error:
        return False

def _time_wait_count(port: int) -> int | None:
    if sys.platform != "win32":
        return None
    try:
        ps = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Get-NetTCPConnection -LocalPort {port} -State TimeWait -ErrorAction SilentlyContinue "
             f"| Measure-Object | Select-Object -ExpandProperty Count"],
            capture_output=True, text=True, timeout=5,
            encoding="utf-8", errors="replace",
            **_hidden_subprocess_kwargs(),
        )
        return int(ps.stdout.strip() or 0)
    except (ValueError, subprocess.TimeoutExpired, OSError):
        return None

# ── Heartbeat de hijos ──────────────────────────────────────────────────────
_heartbeats: dict[int, float] = {}

def _hb_touch(pid: int) -> None:
    _heartbeats[pid] = time.time()

def _hb_stale_pids() -> list[int]:
    now = time.time()
    return [pid for pid, t in _heartbeats.items() if now - t > HEARTBEAT_STALE_AFTER]

# ── Acciones de salida limpia ───────────────────────────────────────────────
def _graceful_kill(pid: int, why: str) -> None:
    _log("WARN", f"callejón: pid={pid} motivo={why} → SIGTERM")
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(pid), "/T"],
                           capture_output=True, timeout=5,
                           **_hidden_subprocess_kwargs())
        else:
            os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    t0 = time.time()
    while time.time() - t0 < GRACEFUL_TERM_WAIT_S and _pid_alive(pid):
        time.sleep(0.5)
    if _pid_alive(pid):
        _log("ERROR", f"pid={pid} ignoró SIGTERM {GRACEFUL_TERM_WAIT_S}s → SIGKILL")
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                               capture_output=True, timeout=5,
                               **_hidden_subprocess_kwargs())
            else:
                os.kill(pid, signal.SIGKILL)
        except OSError:
            pass

# ── Loop principal ──────────────────────────────────────────────────────────
def _cmd_start(args: argparse.Namespace) -> int:
    state = _read_state()
    if state.get("pid") and _pid_alive(state["pid"]):
        print(f"supervisor ya corre (pid={state['pid']}, "
              f"up={_fmt_uptime(state.get('started_at'))})")
        return 0
    if not _acquire_lock_nonblocking():
        print("otro supervisor está tomando el lock; reintentá en 1s", file=sys.stderr)
        return 1

    # Lanzar este script en modo --loop en background, realmente detached.
    # CREATE_NEW_PROCESS_GROUP + DETACHED_PROCESS hacen que el hijo sobreviva
    # al padre. start_new_session=False para no crear un sid en Windows.
    script = Path(__file__).resolve()
    env = os.environ.copy()
    env[CHILD_MARKER_ENV] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    if sys.platform == "win32":
        DETACHED = 0x00000008
        NEW_PG   = 0x00000200
        CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        flags = DETACHED | NEW_PG | CREATE_NO_WINDOW
        p = subprocess.Popen(
            [sys.executable, str(script), "--loop"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            creationflags=flags,
            **{k: v for k, v in _hidden_subprocess_kwargs().items() if k != "creationflags"},
            close_fds=True,
        )
    else:
        p = subprocess.Popen(
            [sys.executable, str(script), "--loop"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
            close_fds=True,
        )
    _log("INFO", f"supervisor arrancado pid={p.pid} loop detached")
    # pequeña espera para que el hijo escriba su supervisor.json
    for _ in range(20):
        time.sleep(0.1)
        st = _read_state()
        if st.get("pid") == p.pid:
            break
    print(f"supervisor arrancado pid={p.pid}")
    return 0

def _loop(args: argparse.Namespace) -> int:  # noqa: ARG001
    # Modo background: somos el hijo.
    # Política de salida limpia, en orden:
    #   1) Stop natural: STOP_FILE aparece → loop termina por el finally.
    #   2) Stop forzado:  signal SIGTERM/SIGINT/SIGBREAK → mismo finally.
    #   3) Stop nuclear:  taskkill /F /T → atexit() deja huella en el log.
    # En cualquier caso, el log registra *por qué* morimos. Eso es lo que te
    # deja ver "salida limpia" sin perder evidencia.
    _log("INFO", f"loop iniciado pid={os.getpid()}")
    # limpiar sentinel heredado de un stop previo
    try:
        STOP_FILE.unlink()
    except OSError:
        pass
    state = {
        "pid": os.getpid(),
        "started_at": _now(),
        "version": SUPERVISOR_VERSION,
        "last_event": _now(),
        "children_seen": 0,
        "events": 0,
    }
    _write_state(state)
    _release_lock()  # el padre ya no lo necesita
    LOCK_FILE.write_text(json.dumps({"pid": os.getpid(), "at": _now()}), encoding="utf-8")

    stop = False
    stop_reason = "manual"

    def _stop_handler(signum, frame):  # noqa: ARG001
        nonlocal stop, stop_reason
        stop_reason = f"signal {signum}"
        _log("INFO", f"señal {signum} → salida limpia")
        stop = True

    try:
        if sys.platform == "win32":
            signal.signal(signal.SIGINT,  _stop_handler)
            signal.signal(signal.SIGTERM, _stop_handler)
            signal.signal(signal.SIGBREAK, _stop_handler)
        else:
            signal.signal(signal.SIGTERM, _stop_handler)
            signal.signal(signal.SIGINT,  _stop_handler)
    except (ValueError, OSError):
        pass

    import atexit
    @atexit.register
    def _on_exit():
        _log("INFO", f"loop exit reason={stop_reason}")

    try:
        while not stop:
            # (1) sentinel file = parada natural
            if STOP_FILE.exists():
                stop_reason = "stop_file"
                _log("INFO", "STOP_FILE presente → salida limpia")
                stop = True
                break
            try:
                tick(state)
            except Exception as e:  # noqa: BLE001 — política de salida limpia
                _log("ERROR", f"tick falló: {type(e).__name__}: {e}")
            # espera activa pero corta para reaccionar rápido al stop
            for _ in range(WATCHDOG_TICK_S * 10):
                if stop:
                    break
                if STOP_FILE.exists():
                    stop_reason = "stop_file"
                    stop = True
                    break
                time.sleep(0.1)
    finally:
        _log("INFO", f"loop saliendo reason={stop_reason}, limpiando hijos")
        try:
            # Limpieza: matar cualquier python.exe de BAGO que *no sea* un
            # supervisor (excluimos nuestro propio PID y el del padre que
            # nos invoca, que aparece como "python bago_supervisor.py start"
            # con --loop, y el de cualquier bago.ps1 que siga vivo).
            my_pid = os.getpid()
            ppid = os.getppid() if hasattr(os, "getppid") else 0
            for ch in _list_bago_children():
                if ch["pid"] in (my_pid, ppid):
                    continue
                _graceful_kill(ch["pid"], "supervisor cerrando")
        except Exception as e:  # noqa: BLE001
            _log("WARN", f"limpieza de hijos falló: {type(e).__name__}: {e}")
        _release_lock()
        try:
            STATE_FILE.unlink()
        except OSError:
            pass
        try:
            STOP_FILE.unlink()
        except OSError:
            pass
        _log("INFO", "loop cerrado limpio")
    return 0

def tick(state: dict[str, Any]) -> None:
    """Un latido: inspecciona, decide, registra."""
    # 1) Hijos
    children = _list_bago_children()
    state["children_seen"] = max(state.get("children_seen", 0), len(children))
    for ch in children:
        _hb_touch(ch["pid"])
    # 1.a) Heartbeat vencido
    for pid in _hb_stale_pids():
        _graceful_kill(pid, f"heartbeat_stale>{HEARTBEAT_STALE_AFTER}s")
        state["events"] = state.get("events", 0) + 1
    # 1.b) RAM alta
    for ch in children:
        rp = _ram_pct(ch["pid"])
        if rp is not None and rp > RAM_HIGH_PCT:
            _log("WARN", f"pid={ch['pid']} RAM={rp:.1f}% (>={RAM_HIGH_PCT}%)")
            # No matamos al instante; damos dwell de RAM_HIGH_DWELL_S
            # (simple: si vuelve a aparecer alto dos ticks seguidos, mata)
            mark = f"ram_high:{ch['pid']}"
            last = state.get(mark)
            if last and time.time() - last > RAM_HIGH_DWELL_S:
                _graceful_kill(ch["pid"], f"ram_high {rp:.1f}% >{RAM_HIGH_DWELL_S}s")
                state["events"] = state.get("events", 0) + 1
                state.pop(mark, None)
            else:
                state[mark] = time.time()
        else:
            state.pop(f"ram_high:{ch['pid']}", None)
    # 2) WAL
    ws = _wal_size()
    if ws > WAL_HIGH_BYTES:
        if _wal_checkpoint():
            _log("INFO", f"wal_checkpoint TRUNCATE (era {ws} bytes)")
            state["events"] = state.get("events", 0) + 1
        else:
            _log("WARN", f"WAL={ws} bytes y no se pudo truncar")
    # 3) TIME_WAIT al ollama
    tw = _time_wait_count(OLLAMA_PORT)
    if tw is not None and tw > TIME_WAIT_HIGH:
        _log("WARN", f"ollama:{OLLAMA_PORT} TIME_WAIT={tw} (>={TIME_WAIT_HIGH})")
    # fin tick
    state["last_event"] = _now()
    _write_state(state)

def _cmd_stop(args: argparse.Namespace) -> int:  # noqa: ARG001
    state = _read_state()
    pid = state.get("pid")
    if not pid or not _pid_alive(pid):
        print("supervisor no está corriendo")
        _release_lock()
        try:
            STATE_FILE.unlink()
        except OSError:
            pass
        try:
            STOP_FILE.unlink()
        except OSError:
            pass
        return 0
    _log("INFO", f"stop solicitado por pid={os.getpid()} → {pid}")

    # (1) salida limpia vía sentinel: el loop lo ve y se va por el finally.
    STOP_FILE.write_text(json.dumps({"by": os.getpid(), "at": _now()}), encoding="utf-8")

    t0 = time.time()
    while time.time() - t0 < GRACEFUL_TERM_WAIT_S and _pid_alive(pid):
        time.sleep(0.3)
    if not _pid_alive(pid):
        _log("INFO", f"supervisor {pid} salió limpio en {time.time()-t0:.1f}s")
        _release_lock()
        try:
            STATE_FILE.unlink()
        except OSError:
            pass
        try:
            STOP_FILE.unlink()
        except OSError:
            pass
        print(f"supervisor {pid} detenido (limpio)")
        return 0

    # (2) forzado: SIGTERM
    _log("WARN", f"pid={pid} no honró sentinel, enviando SIGTERM")
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/T"],
                       capture_output=True, timeout=5,
                       **_hidden_subprocess_kwargs())
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    t0 = time.time()
    while time.time() - t0 < GRACEFUL_TERM_WAIT_S and _pid_alive(pid):
        time.sleep(0.5)
    if not _pid_alive(pid):
        _log("INFO", f"supervisor {pid} salió tras SIGTERM")
        _release_lock()
        try:
            STATE_FILE.unlink()
        except OSError:
            pass
        try:
            STOP_FILE.unlink()
        except OSError:
            pass
        print(f"supervisor {pid} detenido (SIGTERM)")
        return 0

    # (3) nuclear: SIGKILL/taskkill /F — solo si todo lo anterior falló
    _log("ERROR", f"pid={pid} ignoró sentinel+SIGTERM, escalando a /F")
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                       capture_output=True, timeout=5,
                       **_hidden_subprocess_kwargs())
    else:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    _release_lock()
    try:
        STATE_FILE.unlink()
    except OSError:
        pass
    try:
        STOP_FILE.unlink()
    except OSError:
        pass
    print(f"supervisor {pid} forzado (/F)")
    return 0

def _fmt_uptime(started_at: str | None) -> str:
    if not started_at:
        return "?"
    try:
        t0 = datetime.fromisoformat(started_at)
    except ValueError:
        return "?"
    dt = datetime.now(timezone.utc) - t0
    s = int(dt.total_seconds())
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def _cmd_status(args: argparse.Namespace) -> int:
    state = _read_state()
    if not state:
        print("supervisor: no instalado")
        return 0
    alive = bool(state.get("pid") and _pid_alive(state["pid"]))
    summary = {
        "version":      state.get("version"),
        "pid":          state.get("pid"),
        "alive":        alive,
        "started_at":   state.get("started_at"),
        "uptime":       _fmt_uptime(state.get("started_at")),
        "last_event":   state.get("last_event"),
        "events":       state.get("events", 0),
        "children_max": state.get("children_seen", 0),
        "log":          str(LOG_FILE),
    }
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        for k, v in summary.items():
            print(f"{k:>13}: {v}")
    return 0

def _cmd_attach(args: argparse.Namespace) -> int:  # noqa: ARG001
    if not LOG_FILE.exists():
        print("(log vacío)")
        return 0
    # tail -f minimalista, portable
    pos = max(0, LOG_FILE.stat().st_size - 4096)
    with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
        f.seek(pos)
        while True:
            line = f.readline()
            if line:
                print(line.rstrip())
            else:
                time.sleep(0.5)

# ── main ────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bago sup", description="BAGO supervisor (always-on watchdog)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s1 = sub.add_parser("start", help="arranca el supervisor en background")
    s2 = sub.add_parser("stop", help="cierra el supervisor limpiamente")
    s3 = sub.add_parser("status", help="muestra estado del supervisor")
    s3.add_argument("--json", action="store_true", help="salida en JSON")
    s4 = sub.add_parser("attach", help="tail -f del log del supervisor")
    sub.add_parser("--loop", help=argparse.SUPPRESS)  # modo background
    s1.set_defaults(func=_cmd_start)
    s2.set_defaults(func=_cmd_stop)
    s3.set_defaults(func=_cmd_status)
    s4.set_defaults(func=_cmd_attach)
    p.set_defaults(func=lambda a: p.print_help() or 0)
    return p

def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    # --loop se detecta antes de pasar por argparse (es un modo "interno")
    if argv and argv[0] == "--loop":
        return _loop(argparse.Namespace())
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
