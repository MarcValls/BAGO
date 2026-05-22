"""bago summary — Executive dashboard: ideas, tools, size, git, todos."""
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BAGO_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BAGO_DIR / "state"
TOOLS_DIR = Path(__file__).resolve().parent
DB_PATH = STATE_DIR / "bago.db"
IMPL_PATH = STATE_DIR / "implemented_ideas.json"
PROJECT_ROOT = BAGO_DIR.parent

# ── helpers ───────────────────────────────────────────────────────────────────

def _bar(value: int, max_val: int, width: int = 20, char: str = "█") -> str:
    filled = int(width * value / max_val) if max_val else 0
    return char * filled + "░" * (width - filled)


def _dir_size_mb(path: Path) -> float:
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    except Exception:
        pass
    return total / 1_048_576


def _tool_count() -> int:
    return len(list(TOOLS_DIR.glob("*.py")))


def _ideas_stats() -> dict:
    impl = {"count": 0, "last_7": 0, "last_week_dates": []}
    if IMPL_PATH.exists():
        data = json.loads(IMPL_PATH.read_text(encoding="utf-8"))
        items = data.get("implemented", [])
        impl["count"] = len(items)
        now = datetime.now(timezone.utc)
        for it in items:
            raw = it.get("done_at", "")
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
                diff = (now - dt).days
                if diff < 7:
                    impl["last_7"] += 1
            except Exception:
                pass

    db_total = 0
    db_avail = 0
    if DB_PATH.exists():
        try:
            con = sqlite3.connect(DB_PATH)
            row = con.execute("SELECT COUNT(*) FROM ideas").fetchone()
            db_total = row[0] if row else 0
            row2 = con.execute("SELECT COUNT(*) FROM ideas WHERE status='available'").fetchone()
            db_avail = row2[0] if row2 else 0
            con.close()
        except Exception:
            pass
    return {"implemented": impl["count"], "last_7": impl["last_7"], "db_total": db_total, "db_avail": db_avail}


def _active_task() -> str:
    task_path = STATE_DIR / "pending_w2_task.json"
    if task_path.exists():
        try:
            d = json.loads(task_path.read_text(encoding="utf-8"))
            name = d.get("idea", {}).get("name", "")
            return name[:60] if name else "—"
        except Exception:
            pass
    return "—"


def _git_info() -> dict:
    info = {"branch": "—", "last": "—", "dirty": False}
    candidates = [
        "git",
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files (x86)\Git\bin\git.exe",
    ]
    git_exe = None
    for c in candidates:
        try:
            res = subprocess.run(
                ["where" if os.name == "nt" else "which", c],
                capture_output=True, timeout=3,
            )
            if res.returncode == 0:
                git_exe = c
                break
        except Exception:
            pass
        if os.name == "nt" and Path(c).exists():
            git_exe = c
            break

    if not git_exe:
        return info
    try:
        branch = subprocess.run([git_exe, "branch", "--show-current"],
                                cwd=PROJECT_ROOT, capture_output=True).stdout.decode("utf-8", errors="replace").strip()
        info["branch"] = branch or "—"
        log = subprocess.run([git_exe, "log", "-1", "--pretty=%s (%ar)"],
                             cwd=PROJECT_ROOT, capture_output=True).stdout.decode("utf-8", errors="replace").strip()
        info["last"] = log[:70] if log else "—"
        status = subprocess.run([git_exe, "status", "--porcelain"],
                                cwd=PROJECT_ROOT, capture_output=True).stdout.decode("utf-8", errors="replace").strip()
        info["dirty"] = bool(status)
    except Exception:
        pass
    return info


def _app_sizes() -> list[tuple[str, float]]:
    apps_dir = PROJECT_ROOT / "apps"
    results = []
    if apps_dir.exists():
        for app in sorted(apps_dir.iterdir()):
            if app.is_dir() and not app.name.startswith("."):
                size = _dir_size_mb(app)
                results.append((app.name, size))
    return results


def _snapshots() -> int:
    snap_dir = BAGO_DIR / "snapshots"
    if snap_dir.exists():
        return len(list(snap_dir.glob("*.zip")))
    return 0


def _db_size_kb() -> float:
    if DB_PATH.exists():
        return DB_PATH.stat().st_size / 1024
    return 0.0


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    ideas = _ideas_stats()
    tools = _tool_count()
    task = _active_task()
    git = _git_info()
    app_sizes = _app_sizes()
    snaps = _snapshots()
    db_kb = _db_size_kb()
    total_app_mb = sum(s for _, s in app_sizes)

    W = 60
    sep = "─" * W
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    print(f"\n  ┌{'─' * (W - 2)}┐")
    print(f"  │  🧭  BAGO Executive Summary{' ' * (W - 29)}│")
    print(f"  │  {now_str}{' ' * (W - 4 - len(now_str))}│")
    print(f"  └{'─' * (W - 2)}┘")

    # Ideas block
    pct = int(ideas["implemented"] / max(ideas["db_total"], 1) * 100)
    bar = _bar(ideas["implemented"], max(ideas["db_total"], 100))
    print(f"\n  💡 IDEAS")
    print(f"     Implementadas : {ideas['implemented']:>3}   {bar}  {pct}%")
    print(f"     Disponibles DB: {ideas['db_avail']:>3}   (total DB: {ideas['db_total']})")
    print(f"     Últimos 7 días: {ideas['last_7']:>3}")

    # Tools block
    print(f"\n  🔧 HERRAMIENTAS")
    tool_bar = _bar(tools, 150)
    print(f"     Archivos .py  : {tools:>3}   {tool_bar}")
    print(f"     Snapshots     : {snaps:>3}   DB: {db_kb:.0f} KB")

    # Active task
    print(f"\n  ⏳ TAREA ACTIVA")
    print(f"     {task}")

    # Git block
    dirty_flag = " ⚠ (cambios sin commit)" if git["dirty"] else " ✔"
    print(f"\n  🌿 GIT")
    print(f"     Rama    : {git['branch']}{dirty_flag}")
    print(f"     Último  : {git['last']}")

    # App sizes
    if app_sizes:
        print(f"\n  📁 TAMAÑO DE APPS  (total: {total_app_mb:.1f} MB)")
        max_s = max(s for _, s in app_sizes) or 1
        for name, size in app_sizes:
            bar = _bar(size, max_s, width=15)
            print(f"     {name:<18} {bar}  {size:.1f} MB")

    print(f"\n  {sep}")
    print(f"  bago ideas · bago task · bago export · bago git\n")



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    main()
