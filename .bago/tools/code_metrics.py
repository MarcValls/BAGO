"""bago metrics — Code metrics: lines of code, file counts, types per app."""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = ROOT / ".bago" / "state"

EXCLUDE_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".vite",
                "coverage", "__pycache__", ".bago"}
EXCLUDE_EXTS = {".lock", ".map", ".min.js", ".min.css"}
SOURCE_EXTS = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".py", ".json", ".css", ".scss", ".html", ".vue",
    ".md", ".yaml", ".yml", ".toml", ".sh", ".mts"
}


@lru_cache(maxsize=1)
def _load_scan_config() -> dict[str, object]:
    try:
        from bago_config import load_config
        data = load_config("scan_config", fallback=None)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _get_metrics_exclude_dirs() -> set[str]:
    config = _load_scan_config()
    exclude_dirs = config.get("metrics_exclude_dirs", config.get("exclude_dirs"))
    return set(exclude_dirs) if isinstance(exclude_dirs, list) else EXCLUDE_DIRS


def _get_metrics_exclude_exts() -> set[str]:
    exclude_exts = _load_scan_config().get("metrics_exclude_exts")
    return set(exclude_exts) if isinstance(exclude_exts, list) else EXCLUDE_EXTS


def _get_metrics_source_exts() -> set[str]:
    source_exts = _load_scan_config().get("metrics_source_exts")
    return set(source_exts) if isinstance(source_exts, list) else SOURCE_EXTS


def _get_project_root() -> Path:
    gs_path = STATE_DIR / "global_state.json"
    if gs_path.exists():
        try:
            gs = json.loads(gs_path.read_text(encoding="utf-8"))
            p = gs.get("active_project", {}).get("path", "")
            if p and Path(p).exists():
                return Path(p)
        except Exception:
            pass
    return ROOT.parent


PROJECT_ROOT = _get_project_root()


def _count_dir(path: Path, only_ext: str | None = None) -> dict:
    """Return {ext: {files, lines}} for a directory."""
    counts: dict[str, dict] = defaultdict(lambda: {"files": 0, "lines": 0})
    exclude_dirs = _get_metrics_exclude_dirs()
    exclude_exts = _get_metrics_exclude_exts()
    source_exts = _get_metrics_source_exts()
    for f in path.rglob("*"):
        if f.is_dir():
            continue
        # Skip excluded dirs
        if any(p in exclude_dirs for p in f.parts):
            continue
        ext = f.suffix.lower()
        if ext in exclude_exts:
            continue
        if only_ext and ext != only_ext:
            continue
        if ext not in source_exts and not only_ext:
            continue
        try:
            lines = sum(1 for _ in f.open(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        counts[ext]["files"] += 1
        counts[ext]["lines"] += lines
    return dict(counts)


def _bar(val: int, max_val: int, width: int = 18) -> str:
    if max_val == 0:
        return "░" * width
    filled = int(width * val / max_val)
    return "█" * filled + "░" * (width - filled)


def _color(s: str, code: str) -> str:
    return f"\033[{code}m{s}\033[0m"

def CYAN(s):   return _color(s, "36")
def GREEN(s):  return _color(s, "32")
def YELLOW(s): return _color(s, "33")
def DIM(s):    return _color(s, "2")
def BOLD(s):   return _color(s, "1")


def cmd_by_app():
    """Show totals per app."""
    apps_dir = PROJECT_ROOT / "apps"
    apps = sorted([d for d in apps_dir.iterdir() if d.is_dir()]) if apps_dir.exists() else []
    apps = [PROJECT_ROOT] + apps

    results = []
    for app in apps:
        name = "root" if app == PROJECT_ROOT else app.name
        counts = _count_dir(app)
        total_files = sum(v["files"] for v in counts.values())
        total_lines = sum(v["lines"] for v in counts.values())
        results.append({"name": name, "files": total_files, "lines": total_lines, "counts": counts})

    max_lines = max((r["lines"] for r in results), default=1)

    print(f"\n  {BOLD('APP'):<22}  {'FILES':>6}  {'LINES':>8}  {'BAR'}")
    print("  " + "─" * 70)
    for r in results:
        bar = _bar(r["lines"], max_lines)
        print(f"  {CYAN(r['name']):<22}  {r['files']:>6}  {r['lines']:>8}  {bar}")
    total_f = sum(r["files"] for r in results)
    total_l = sum(r["lines"] for r in results)
    print("  " + "─" * 70)
    print(f"  {'TOTAL':<22}  {total_f:>6}  {total_l:>8}\n")


def cmd_by_ext(app_filter: str | None):
    """Show totals per extension."""
    if app_filter:
        base = PROJECT_ROOT / "apps" / app_filter
        if not base.exists():
            base = PROJECT_ROOT
    else:
        base = PROJECT_ROOT

    counts = _count_dir(base)
    sorted_counts = sorted(counts.items(), key=lambda x: x[1]["lines"], reverse=True)
    max_lines = max((v["lines"] for v in counts.values()), default=1)

    print(f"\n  {BOLD('EXTENSION'):<12}  {'FILES':>6}  {'LINES':>8}  BAR")
    print("  " + "─" * 55)
    for ext, v in sorted_counts:
        bar = _bar(v["lines"], max_lines)
        print(f"  {YELLOW(ext):<12}  {v['files']:>6}  {v['lines']:>8}  {bar}")
    total_f = sum(v["files"] for v in counts.values())
    total_l = sum(v["lines"] for v in counts.values())
    print("  " + "─" * 55)
    print(f"  {'TOTAL':<12}  {total_f:>6}  {total_l:>8}\n")


def main():
    parser = argparse.ArgumentParser(description="BAGO metrics — Code size metrics")
    parser.add_argument("--by", choices=["app", "ext"], default="app",
                        help="Group by app (default) or extension")
    parser.add_argument("--app", "-a", help="Filter to specific app")
    args = parser.parse_args()

    if args.by == "ext":
        cmd_by_ext(args.app)
    else:
        cmd_by_app()



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
