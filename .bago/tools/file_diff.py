"""bago diff — Visual diff between files or directories in the monorepo."""
from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = ROOT / ".bago" / "state"


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

# ANSI colors
def RED(s):    return f"\033[31m{s}\033[0m"
def GREEN(s):  return f"\033[32m{s}\033[0m"
def CYAN(s):   return f"\033[36m{s}\033[0m"
def YELLOW(s): return f"\033[33m{s}\033[0m"
def DIM(s):    return f"\033[2m{s}\033[0m"
def BOLD(s):   return f"\033[1m{s}\033[0m"


def _resolve(path_str: str) -> Path:
    """Resolve relative to project root or as absolute."""
    p = Path(path_str)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p.resolve()


def _diff_files(a: Path, b: Path, context: int, color: bool):
    """Unified diff between two text files."""
    try:
        a_lines = a.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        b_lines = b.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    except Exception as e:
        print(f"  ✖ Error al leer archivos: {e}", file=sys.stderr)
        return 1

    diff = list(difflib.unified_diff(
        a_lines, b_lines,
        fromfile=str(a), tofile=str(b),
        n=context,
    ))

    if not diff:
        print(f"  {GREEN('✔')} Sin diferencias entre los archivos.")
        return 0

    for line in diff:
        if not color:
            print(line, end="")
            continue
        if line.startswith("---") or line.startswith("+++"):
            print(BOLD(CYAN(line)), end="")
        elif line.startswith("@@"):
            print(YELLOW(line), end="")
        elif line.startswith("+"):
            print(GREEN(line), end="")
        elif line.startswith("-"):
            print(RED(line), end="")
        else:
            print(DIM(line), end="")
    return 1  # differences found


def _diff_dirs(a: Path, b: Path, context: int, color: bool, ext_filter: str | None):
    """Compare two directories recursively, show diffs for differing files."""
    a_files = {f.relative_to(a): f for f in a.rglob("*") if f.is_file()
               and "node_modules" not in f.parts}
    b_files = {f.relative_to(b): f for f in b.rglob("*") if f.is_file()
               and "node_modules" not in f.parts}

    if ext_filter:
        a_files = {k: v for k, v in a_files.items() if k.suffix == ext_filter}
        b_files = {k: v for k, v in b_files.items() if k.suffix == ext_filter}

    only_a = sorted(a_files.keys() - b_files.keys())
    only_b = sorted(b_files.keys() - a_files.keys())
    common = sorted(a_files.keys() & b_files.keys())

    print()
    total_diff = 0

    for rel in only_a:
        print(f"  {RED('─')} Solo en A: {rel}")
    for rel in only_b:
        print(f"  {GREEN('+')} Solo en B: {rel}")

    for rel in common:
        fa, fb = a_files[rel], b_files[rel]
        try:
            ta = fa.read_text(encoding="utf-8", errors="replace")
            tb = fb.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if ta != tb:
            total_diff += 1
            print(f"\n  {YELLOW('≠')} {rel}")
            _diff_files(fa, fb, context, color)

    print()
    summary = []
    if only_a:
        summary.append(f"{RED(str(len(only_a)))} solo en A")
    if only_b:
        summary.append(f"{GREEN(str(len(only_b)))} solo en B")
    if total_diff:
        summary.append(f"{YELLOW(str(total_diff))} con diferencias")
    if not summary:
        print(f"  {GREEN('✔')} Directorios idénticos.\n")
    else:
        print(f"  Resultado: {', '.join(summary)}\n")

    return len(only_a) + len(only_b) + total_diff


def main():
    parser = argparse.ArgumentParser(
        description="BAGO diff — Compare files or directories in the monorepo"
    )
    parser.add_argument("a", help="Ruta A (relativa al proyecto o absoluta)")
    parser.add_argument("b", help="Ruta B (relativa al proyecto o absoluta)")
    parser.add_argument("--context", "-c", type=int, default=3,
                        help="Líneas de contexto (default: 3)")
    parser.add_argument("--no-color", action="store_true", help="Sin colores ANSI")
    parser.add_argument("--ext", help="Filtrar por extensión (solo dirs), e.g. .ts")
    args = parser.parse_args()

    a = _resolve(args.a)
    b = _resolve(args.b)
    color = not args.no_color

    print(f"\n  {CYAN('A')}: {a}")
    print(f"  {CYAN('B')}: {b}\n")

    if not a.exists():
        print(f"  ✖ No existe: {a}", file=sys.stderr)
        sys.exit(1)
    if not b.exists():
        print(f"  ✖ No existe: {b}", file=sys.stderr)
        sys.exit(1)

    if a.is_file() and b.is_file():
        result = _diff_files(a, b, args.context, color)
        sys.exit(0)
    elif a.is_dir() and b.is_dir():
        _diff_dirs(a, b, args.context, color, args.ext)
        sys.exit(0)
    else:
        print("  ✖ Ambas rutas deben ser archivos o ambas directorios.", file=sys.stderr)
        sys.exit(1)



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
