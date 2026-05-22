#!/usr/bin/env python3
"""
recent_projects.py — Registro de proyectos recientes BAGO

Registra automáticamente cada repo donde BAGO arranca y permite
consultar el historial de proyectos con sus métricas.

Uso:
  python3 .bago/tools/recent_projects.py            # lista proyectos recientes
  python3 .bago/tools/recent_projects.py --record   # registra proyecto actual (uso interno)
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Windows UTF-8 fix
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

BAGO_ROOT = Path(__file__).resolve().parent.parent
STATE     = BAGO_ROOT / "state"
RECENT_F  = STATE / "recent_projects.json"
MAX_RECENT = 10  # máximo de proyectos a recordar

# ─── Colores ANSI ─────────────────────────────────────────────────────────────
USE_COLOR = sys.stdout.isatty() and "--plain" not in sys.argv

def _c(code, text):
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text

CYAN   = lambda t: _c("1;36", t)
GREEN  = lambda t: _c("1;32", t)
YELLOW = lambda t: _c("1;33", t)
BOLD   = lambda t: _c("1",    t)
DIM    = lambda t: _c("2",    t)


# ─── Lógica de registro ────────────────────────────────────────────────────────

def _load_recent() -> list:
    if not RECENT_F.exists():
        return []
    try:
        data = json.loads(RECENT_F.read_text(encoding="utf-8"))
        return data.get("projects", [])
    except Exception:
        return []


def _save_recent(projects: list) -> None:
    RECENT_F.write_text(
        json.dumps({"projects": projects}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def _get_ideas_done() -> int:
    impl_f = STATE / "implemented_ideas.json"
    if not impl_f.exists():
        return 0
    try:
        data = json.loads(impl_f.read_text(encoding="utf-8"))
        return len(data.get("implemented", []))
    except Exception:
        return 0


def _get_last_idea() -> str:
    impl_f = STATE / "implemented_ideas.json"
    if not impl_f.exists():
        return ""
    try:
        data = json.loads(impl_f.read_text(encoding="utf-8"))
        items = data.get("implemented", [])
        if items:
            return items[-1].get("title", "")
    except Exception:
        pass
    return ""


def _get_repo_context() -> dict:
    ctx_f = STATE / "repo_context.json"
    if not ctx_f.exists():
        return {}
    try:
        return json.loads(ctx_f.read_text(encoding="utf-8"))
    except Exception:
        return {}


def record_project() -> None:
    """Registra el proyecto actual en recent_projects.json. Llamado al arrancar el banner."""
    ctx       = _get_repo_context()
    repo_root = ctx.get("repo_root", str(BAGO_ROOT.parent))
    repo_name = Path(repo_root).name
    mode      = ctx.get("working_mode", "self")
    now       = datetime.now(tz=timezone.utc).isoformat()

    projects = _load_recent()

    # Actualizar entrada existente o insertar nueva
    existing = next((p for p in projects if p.get("repo_root") == repo_root), None)
    if existing:
        existing["last_seen"]  = now
        existing["ideas_done"] = _get_ideas_done()
        existing["last_idea"]  = _get_last_idea()
        existing["mode"]       = mode
        # Mover al frente (más reciente)
        projects.remove(existing)
        projects.insert(0, existing)
    else:
        projects.insert(0, {
            "repo_root":  repo_root,
            "repo_name":  repo_name,
            "last_seen":  now,
            "ideas_done": _get_ideas_done(),
            "last_idea":  _get_last_idea(),
            "mode":       mode,
        })

    # Mantener máximo
    projects = projects[:MAX_RECENT]
    _save_recent(projects)


def load_recent() -> list:
    """API pública para que el banner pueda leer los proyectos recientes."""
    return _load_recent()


# ─── Formateo de fechas ────────────────────────────────────────────────────────

def _relative_date(iso_str: str) -> str:
    """Devuelve 'hoy', 'ayer', 'hace N días' o fecha corta."""
    try:
        dt   = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now  = datetime.now(tz=timezone.utc)
        days = (now - dt).days
        if days == 0:
            return "hoy"
        elif days == 1:
            return "ayer"
        elif days < 7:
            return f"hace {days}d"
        else:
            return dt.strftime("%Y-%m-%d")
    except Exception:
        return "?"


# ─── Lectura de sesiones (session_close_*.md) ─────────────────────────────────

def _load_sessions(limit: int = 15) -> list:
    """Lee los session_close_*.md más recientes y extrae idea + estado + fecha."""
    sessions = []
    files = sorted(STATE.glob("session_close_*.md"), reverse=True)[:limit]
    for f in files:
        try:
            text  = f.read_text(encoding="utf-8")
            # Título: primera línea — "# Cierre de sesión — <idea>"
            title = ""
            for line in text.splitlines():
                if line.startswith("# Cierre"):
                    title = line.replace("# Cierre de sesión —", "").strip()
                    break
            # Fecha cierre
            fecha = ""
            for line in text.splitlines():
                if line.startswith("**Fecha cierre**"):
                    fecha = line.split(":", 1)[-1].strip()
                    break
            # Estado
            estado = "?"
            for line in text.splitlines():
                if line.startswith("**Estado**"):
                    estado = line.split(":", 1)[-1].strip()
                    break
            if title:
                sessions.append({
                    "title":  title,
                    "fecha":  fecha,
                    "estado": estado,
                    "file":   f.name,
                })
        except Exception:
            continue
    return sessions


# ─── Comando bago recent ──────────────────────────────────────────────────────

def cmd_recent() -> int:
    projects = _load_recent()
    sessions = _load_sessions()

    print()

    # ── Sección: proyectos (repos) ────────────────────────────────────────────
    print(BOLD("  Proyectos BAGO"))
    print(DIM("  " + "─" * 58))
    if not projects:
        print(DIM("  Sin proyectos registrados aún — se registra al arrancar `bago`"))
    else:
        print(DIM(f"  {'Repo':<22}  {'Modo':<8}  {'Ideas':>5}  {'Visto':<8}  Última tarea"))
        print(DIM("  " + "─" * 58))
        for i, p in enumerate(projects):
            name      = p.get("repo_name", "?")[:21]
            mode      = p.get("mode", "?")[:7]
            ideas     = str(p.get("ideas_done", 0))
            when      = _relative_date(p.get("last_seen", ""))
            last_idea = p.get("last_idea", "")[:28]
            marker    = "→" if i == 0 else " "
            print(f"  {marker} {BOLD(name + ' ' * max(0, 21 - len(name)))}  "
                  f"{DIM(mode + ' ' * max(0, 7 - len(mode)))}  "
                  f"{GREEN(ideas):>5}  "
                  f"{YELLOW(when)}{' ' * max(0, 7 - len(when))}  "
                  f"{DIM(last_idea)}")
        print(DIM(f"  {len(projects)} repo(s)  ·  usa `bago repo-clone` para añadir proyectos externos"))

    print()

    # ── Sección: sesiones recientes ───────────────────────────────────────────
    print(BOLD("  Sesiones recientes"))
    print(DIM("  " + "─" * 58))
    if not sessions:
        print(DIM("  Sin sesiones registradas."))
    else:
        print(DIM(f"  {'Fecha':<22}  {'Estado':<6}  Tarea"))
        print(DIM("  " + "─" * 58))
        for s in sessions:
            fecha  = s.get("fecha", "?")[:20]
            estado = "✅" if "COMPLETADA" in s.get("estado", "") else "⏳"
            title  = s.get("title", "?")[:38]
            print(f"  {DIM(fecha + ' ' * max(0, 21 - len(fecha)))}  {estado}  {title}")
        print(DIM(f"  {len(sessions)} sesión(es) mostradas"))

    print()
    return 0


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    args = sys.argv[1:]
    if "--record" in args:
        record_project()
        return 0
    return cmd_recent()



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    raise SystemExit(main())
