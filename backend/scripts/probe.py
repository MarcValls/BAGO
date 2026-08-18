#!/usr/bin/env python3
"""probe.py — health check único de todos los proveedores BAGO 4.1.5.

Ejecuta todas las verificaciones en un solo proceso Python (sin lanzar el
launcher repetidas veces, evitando consolas fugaces). Imprime un resumen
JSON y sale 0 si todo OK, 1 si algún login falló.

Uso:
    python scripts\\probe.py
    python scripts\\probe.py --json
    python scripts\\probe.py --quiet
"""
from __future__ import annotations

import argparse
import ctypes
import datetime
import json
import os
import socket
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

from bago_core.user_state_paths import legacy_user_root, state_root


def _http_json(url: str, body: dict | None = None, timeout: float = 5.0) -> tuple[bool, dict | str, float]:
    """Returns (ok, payload_or_error, duration_s)."""
    t0 = time.perf_counter()
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return True, payload, time.perf_counter() - t0
    except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout, OSError) as exc:
        return False, str(exc), time.perf_counter() - t0
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}", time.perf_counter() - t0


def check_ollama() -> dict:
    base = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    ok, payload, dur = _http_json(f"{base}/api/version")
    if not ok:
        return {"provider": "ollama-local", "ok": False, "error": payload, "duration_s": round(dur, 2)}
    ok_tags, tags, dur2 = _http_json(f"{base}/api/tags")
    models = [m["name"] for m in (tags.get("models") or [])] if ok_tags else []
    return {
        "provider": "ollama-local",
        "ok": ok_tags,
        "version": payload.get("version") if isinstance(payload, dict) else None,
        "models": models,
        "models_count": len(models),
        "duration_s": round(dur + dur2, 2),
    }


def check_knowledge() -> dict:
    db = state_root() / "knowledge" / "knowledge.db"
    if not db.exists():
        db = legacy_user_root() / "knowledge" / "knowledge.db"
    if not db.exists():
        return {"provider": "knowledge", "ok": False, "error": f"db not found: {db}"}
    try:
        c = sqlite3.connect(str(db))
        cur = c.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [r[0] for r in cur.fetchall()]
        by_table: dict[str, int] = {}
        for t in tables:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            by_table[t] = cur.fetchone()[0]
        return {
            "provider": "knowledge",
            "ok": True,
            "db": str(db),
            "by_table": by_table,
            "total": sum(by_table.values()),
        }
    except Exception as exc:
        return {"provider": "knowledge", "ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _pid_alive(pid: int) -> bool:
    """Best-effort: ¿el pid está vivo en este momento? Windows-first."""
    if not pid:
        return False
    try:
        import ctypes
        PROCESS_QUERY_LIMITED = 0x1000
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED, False, pid)
        if not h:
            return False
        STILL_ACTIVE = 259
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return code.value == STILL_ACTIVE
    except Exception:
        return False


def check_supervisor() -> dict:
    """Lee supervisor.json + verifica liveness del pid. No depende de un
    campo 'alive' pre-escrito (el supervisor lo recalcula en cada tick)."""
    state = state_root() / "supervisor.json"
    if not state.exists():
        state = legacy_user_root() / "state" / "supervisor.json"
    if not state.exists():
        return {"provider": "supervisor", "ok": False, "error": "no instalado"}
    try:
        payload = json.loads(state.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"provider": "supervisor", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

    pid = payload.get("pid")
    alive = bool(pid) and _pid_alive(int(pid))
    started = payload.get("started_at")
    uptime = None
    if started:
        try:
            dt = datetime.datetime.fromisoformat(started) - datetime.datetime.now(datetime.timezone.utc).astimezone().replace(tzinfo=None) if False else None  # ver abajo
        except Exception:
            uptime = None
    # cálculo uptime robusto:
    if started:
        try:
            t0 = datetime.datetime.fromisoformat(started)
            now = datetime.datetime.now(t0.tzinfo) if t0.tzinfo else datetime.datetime.now()
            uptime = int((now - t0).total_seconds())
        except Exception:
            uptime = None

    return {
        "provider": "supervisor",
        "ok": alive,
        "version": payload.get("version"),
        "pid": pid,
        "uptime_s": uptime,
        "events": payload.get("events", 0),
        "children_max": payload.get("children_seen", 0),
    }


def check_release() -> dict:
    launch = state_root() / "launch"
    if not launch.exists():
        launch = legacy_user_root() / "launch"
    sig = launch / "release.sig"
    meta = launch / "release.json"
    if not sig.exists() or not meta.exists():
        return {"provider": "release", "ok": False, "error": "artefactos no encontrados"}
    try:
        s = json.loads(sig.read_text(encoding="utf-8"))
        r = json.loads(meta.read_text(encoding="utf-8"))
        return {
            "provider": "release",
            "ok": True,
            "version": r.get("version"),
            "algorithm": s.get("algorithm"),
            "release_sha256": s.get("release_sha256", "")[:16] + "...",
            "seal_sha256": s.get("seal_sha256", "")[:16] + "...",
        }
    except Exception as exc:
        return {"provider": "release", "ok": False, "error": f"{type(exc).__name__}: {exc}"}


CHECKS = [check_ollama, check_knowledge, check_supervisor, check_release]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true", help="JSON output only")
    p.add_argument("--quiet", action="store_true", help="Solo imprime OK/FAIL summary")
    p.add_argument("--no-supervisor", action="store_true", help="Skip supervisor check")
    args = p.parse_args()

    results: list[dict] = []
    for fn in CHECKS:
        if args.no_supervisor and fn is check_supervisor:
            continue
        try:
            results.append(fn())
        except Exception as exc:
            results.append({"provider": fn.__name__, "ok": False, "error": f"{type(exc).__name__}: {exc}"})

    if args.json or args.quiet:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for r in results:
            status = "OK  " if r.get("ok") else "FAIL"
            name = r.get("provider", "?").ljust(14)
            extra = ""
            if "models_count" in r:
                extra = f" models={r['models_count']}"
            elif "total" in r:
                extra = f" rows={r['total']}"
            elif "uptime_s" in r and r["uptime_s"] is not None:
                extra = f" uptime={r['uptime_s']}s"
            err = "" if r.get("ok") else f"  ({r.get('error','')[:60]})"
            print(f"[{status}] {name}{extra}{err}")

    return 0 if all(r.get("ok") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
