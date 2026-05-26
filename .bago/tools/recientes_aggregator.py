#!/usr/bin/env python3
"""recientes_aggregator.py — Agregador de bitácora BAGO.

Lee fuentes locales (sesiones, sprints, ideas implementadas, cierres,
y opcionalmente git log) y produce una timeline normalizada de eventos
ordenados cronológicamente, lista para presentación paginada.

Uso desde CLI:
    python3 .bago/tools/recientes_aggregator.py [--limit N] [--type T] [--since DUR]
    python3 .bago/tools/recientes_aggregator.py --json
    python3 .bago/tools/recientes_aggregator.py --no-git
    python3 .bago/tools/recientes_aggregator.py --test

Imported by: bago.cli  (subcomando `bago recientes`).

Schema de evento normalizado:
    {
      "ts": ISO-8601 UTC string,
      "type": "session" | "sprint" | "idea" | "close" | "commit",
      "scope": str (id/sha/slot — qué identifica el evento),
      "title": str (1 línea, lo principal),
      "detail": str (1-3 líneas, contexto opcional)
    }
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

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

# ── rutas ────────────────────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
BAGO_DIR = HERE.parent              # .bago/
REPO_ROOT = BAGO_DIR.parent         # /Volumes/bago_core/
STATE = BAGO_DIR / "state"
SESSIONS_DIR = STATE / "sessions"
SPRINTS_DIR = STATE / "sprints"
IMPL_FILE = STATE / "implemented_ideas.json"

VALID_TYPES = {"session", "sprint", "idea", "close", "commit", "all"}


# ── helpers ──────────────────────────────────────────────────────────────
def _parse_iso(s: str) -> datetime | None:
    if not s:
        return None
    try:
        # Python 3.11+ acepta 'Z' directamente; el repo lo guarda con +00:00
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _parse_since(spec: str) -> datetime | None:
    """Parse '2w', '3d', '6h', '90m' relative durations."""
    if not spec:
        return None
    m = re.fullmatch(r"(\d+)\s*([smhdw])", spec.strip().lower())
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    delta = {
        "s": timedelta(seconds=n),
        "m": timedelta(minutes=n),
        "h": timedelta(hours=n),
        "d": timedelta(days=n),
        "w": timedelta(weeks=n),
    }[unit]
    return datetime.now(timezone.utc) - delta


def _ev(ts: datetime | str | None, type_: str, scope: str, title: str, detail: str = "") -> dict[str, Any] | None:
    if isinstance(ts, str):
        ts = _parse_iso(ts)
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return {
        "ts": ts.astimezone(timezone.utc).isoformat(),
        "type": type_,
        "scope": scope,
        "title": title,
        "detail": detail,
    }


# ── fuentes ──────────────────────────────────────────────────────────────
def collect_sessions() -> list[dict]:
    out: list[dict] = []
    if not SESSIONS_DIR.is_dir():
        return out
    for path in sorted(SESSIONS_DIR.glob("SES-*.json")):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        ts = d.get("created_at") or d.get("updated_at")
        title = d.get("user_goal") or d.get("summary") or path.stem
        title = title or path.stem
        # truncate title
        title = (title[:90] + "…") if len(title) > 90 else title
        detail_parts = []
        if d.get("selected_workflow"):
            detail_parts.append(d["selected_workflow"])
        if d.get("status"):
            detail_parts.append(f"status={d['status']}")
        if d.get("artifacts"):
            detail_parts.append(f"{len(d['artifacts'])} artefactos")
        ev = _ev(ts, "session", d.get("session_id", path.stem), title, " · ".join(detail_parts))
        if ev:
            out.append(ev)
    return out


def collect_sprints() -> list[dict]:
    out: list[dict] = []
    if not SPRINTS_DIR.is_dir():
        return out
    for path in sorted(SPRINTS_DIR.glob("SPRINT-*.json")):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        # Crea evento en created_at y, si está cerrado, otro en closed_at.
        sid = d.get("sprint_id", path.stem)
        name = d.get("name", "(sin nombre)")
        goal = d.get("goal", "")
        status = d.get("status", "?")
        n_sessions = len(d.get("sessions") or [])
        goal_safe = (goal or "")[:60]
        if d.get("created_at"):
            ev = _ev(
                d["created_at"], "sprint", f"{sid}/open", f"{sid} abierto — {name}",
                f"goal={goal_safe} · sesiones={n_sessions} · status={status}",
            )
            if ev:
                out.append(ev)
        if d.get("closed_at"):
            summary_safe = (d.get("summary") or "")[:120]
            ev = _ev(
                d["closed_at"], "sprint", f"{sid}/close", f"{sid} cerrado — {name}",
                summary_safe,
            )
            if ev:
                out.append(ev)
    return out


def collect_ideas() -> list[dict]:
    out: list[dict] = []
    if not IMPL_FILE.is_file():
        return out
    try:
        d = json.loads(IMPL_FILE.read_text(encoding="utf-8"))
    except Exception:
        return out
    for item in d.get("implemented", []):
        ev = _ev(
            item.get("done_at"), "idea",
            f"slot={item.get('slot') or '-'}",
            f"idea implementada — {item.get('title', '?')}",
            "",
        )
        if ev:
            out.append(ev)
    return out


_CLOSE_FILE_RX = re.compile(r"(?i)session_close_(\d{8})_?(\d{6})\.md")


def collect_closes() -> list[dict]:
    """Cierres de sesión generados como artefacto markdown."""
    out: list[dict] = []
    if not SESSIONS_DIR.is_dir():
        return out
    # Acepta SESSION_CLOSE_*.md y session_close_*.md (mayúsculas/minúsculas)
    for path in SESSIONS_DIR.iterdir():
        m = _CLOSE_FILE_RX.match(path.name)
        if not m or not path.is_file():
            continue
        date_part, time_part = m.group(1), m.group(2)
        try:
            ts = datetime.strptime(date_part + time_part, "%Y%m%d%H%M%S").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
        # Lee primera línea no vacía como título de detalle
        first = ""
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip().lstrip("#").strip()
                if stripped:
                    first = stripped[:100]
                    break
        except Exception:
            pass
        ev = _ev(ts, "close", path.name, "session close", first)
        if ev:
            out.append(ev)
    return out


def collect_commits(limit: int = 50) -> list[dict]:
    """Solo si estamos en repo git. Devuelve lista vacía si no hay git o falla."""
    if not shutil.which("git"):
        return []
    try:
        cp = subprocess.run(
            [
                "git",
                "-C",
                str(REPO_ROOT),
                "log",
                f"-n{limit}",
                "--no-merges",
                "--pretty=format:%H%x09%cI%x09%s",
            ],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    if cp.returncode != 0:
        return []
    out: list[dict] = []
    for line in cp.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        sha, ts, msg = parts
        ev = _ev(ts, "commit", sha[:7], msg[:90], "")
        if ev:
            out.append(ev)
    return out


# ── pipeline ─────────────────────────────────────────────────────────────
def aggregate(
    types: Iterable[str] = ("all",),
    since: datetime | None = None,
    use_git: bool = True,
    git_limit: int = 50,
) -> list[dict]:
    types_set = set(types)
    if "all" in types_set:
        types_set = {"session", "sprint", "idea", "close", "commit"}
    events: list[dict] = []
    if "session" in types_set:
        events.extend(collect_sessions())
    if "sprint" in types_set:
        events.extend(collect_sprints())
    if "idea" in types_set:
        events.extend(collect_ideas())
    if "close" in types_set:
        events.extend(collect_closes())
    if "commit" in types_set and use_git:
        events.extend(collect_commits(limit=git_limit))
    # filtra por since
    if since:
        events = [e for e in events if _parse_iso(e["ts"]) >= since]
    # ordena descendente (más reciente primero)
    events.sort(key=lambda e: e["ts"], reverse=True)
    return events


# ── render ───────────────────────────────────────────────────────────────
TYPE_GLYPH = {
    "session": "🧭",
    "sprint": "🏁",
    "idea": "💡",
    "close": "📝",
    "commit": "🔀",
}


def fmt_event(ev: dict) -> str:
    ts = _parse_iso(ev["ts"])
    when = ts.astimezone().strftime("%Y-%m-%d %H:%M") if ts else "????-??-?? ??:??"
    glyph = TYPE_GLYPH.get(ev["type"], "•")
    head = f"{when}  {glyph} {ev['type']:<7} {ev['scope'][:18]:<18} {ev['title']}"
    if ev.get("detail"):
        head += f"\n                                                {ev['detail']}"
    return head


# ── CLI ──────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="recientes_aggregator", description=__doc__.splitlines()[0])
    p.add_argument("--limit", type=int, default=200, help="máximo de eventos totales (def 200)")
    p.add_argument("--type", default="all",
                   help="comma-list: session,sprint,idea,close,commit,all (def all)")
    p.add_argument("--since", default="", help="duración relativa: 2w, 3d, 6h, 90m")
    p.add_argument("--no-git", action="store_true", help="no usar git log aunque esté disponible")
    p.add_argument("--git-limit", type=int, default=50, help="commits máximo a leer (def 50)")
    p.add_argument("--json", action="store_true", help="salida JSON (lista de eventos)")
    p.add_argument("--test", action="store_true", help="self-tests internos y salida")
    return p


def _self_test() -> int:
    """Tests deterministas mínimos sobre helpers."""
    fails: list[str] = []
    # _parse_since
    if _parse_since("2w") is None:
        fails.append("_parse_since('2w') == None")
    if _parse_since("foo") is not None:
        fails.append("_parse_since('foo') aceptado")
    # _parse_iso
    if _parse_iso("2026-05-07T07:30:42+00:00") is None:
        fails.append("_parse_iso ISO with offset")
    if _parse_iso("not-a-date") is not None:
        fails.append("_parse_iso accepted garbage")
    # _ev
    e = _ev("2026-05-07T07:30:42+00:00", "session", "X", "T")
    if not e or e["type"] != "session":
        fails.append("_ev basic")
    if _ev(None, "x", "x", "x") is not None:
        fails.append("_ev None ts")
    # aggregate sin git, devuelve lista (puede ser vacía si no hay state)
    evs = aggregate(types=("all",), use_git=False)
    if not isinstance(evs, list):
        fails.append("aggregate type")
    if fails:
        for f in fails:
            print(f"  FAIL: {f}")
        print(f"FAIL: {len(fails)}/5 tests")
        return 1
    print("OK: 5/5 self-tests")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.test:
        return _self_test()
    types = [t.strip() for t in args.type.split(",") if t.strip()]
    bad = [t for t in types if t not in VALID_TYPES]
    if bad:
        sys.exit(f"recientes: tipos inválidos: {bad}. Acepta: {sorted(VALID_TYPES)}")
    since = _parse_since(args.since) if args.since else None
    if args.since and since is None:
        sys.exit(f"recientes: --since '{args.since}' inválido (usa 2w/3d/6h/90m)")
    events = aggregate(
        types=types,
        since=since,
        use_git=not args.no_git,
        git_limit=args.git_limit,
    )
    events = events[: args.limit]
    if args.json:
        json.dump(events, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    if not events:
        print("(sin eventos)")
        return 0
    for ev in events:
        print(fmt_event(ev))
    return 0


if __name__ == "__main__":
    sys.exit(main())
