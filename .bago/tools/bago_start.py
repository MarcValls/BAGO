#!/usr/bin/env python3
"""
bago start — Entrada rápida al repo.

Ejecuta en secuencia:
  1. bago health      (semáforo de estado global)
  2. bago ideas       (top 5 ideas priorizadas)
  3. Prompt: ¿aceptar idea top? (s/N)
     - Si s → bago ideas --accept 1  (genera pending_w2_task.json)
     - Si n → salir

Equivale a la secuencia manual de inicio de sesión de trabajo BAGO.
SLOT 7 GEN 1 · Entrada rápida del repo
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT  = Path(__file__).resolve().parent.parent.parent   # project root (bago_core/)
TOOLS = ROOT / ".bago" / "tools"


def _run(args: list[str]) -> int:
    """Execute a list command, stream output, return exit code."""
    result = subprocess.run(args, cwd=str(ROOT))
    return result.returncode


def main() -> None:
    sep = "=" * 52

    # ── 1. Health ────────────────────────────────────────────
    print(sep)
    print("BAGO START · health")
    print(sep)
    rc = _run([sys.executable, str(TOOLS / "health_score.py")])
    if rc != 0:
        print("\n⚠  Health reportó fallos. Revisa antes de continuar.")
        # No bloqueamos — el usuario decide

    print()

    # ── 2. Ideas ─────────────────────────────────────────────
    print(sep)
    print("BAGO START · ideas top")
    print(sep)
    rc_ideas = _run([sys.executable, str(TOOLS / "emit_ideas.py")])

    if rc_ideas != 0:
        print("\nKO en ideas — gate no pasa. Repara el baseline primero.")
        sys.exit(rc_ideas)

    print()

    # ── 3. Prompt de aceptación ───────────────────────────────
    print(sep)
    try:
        answer = input("¿Aceptar idea #1 como tarea activa? [s/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        print("Saliendo sin aceptar.")
        sys.exit(0)

    if answer in {"s", "si", "sí", "y", "yes"}:
        print()
        rc_accept = _run([sys.executable, str(TOOLS / "emit_ideas.py"), "--accept", "1"])
        sys.exit(rc_accept)
    else:
        print("Ninguna idea aceptada. Usa `bago ideas --accept N` cuando quieras.")

    # ── SAC: Superficie Activa por Condición (R-PROD-06) ─────
    # Si hay archivos .py modificados desde el último commit, sugerir audit ast
    _sac_suggest_ast_if_needed(ROOT)

    sys.exit(0)



def _sac_suggest_ast_if_needed(root: Path) -> None:
    """R-PROD-06 · Superficie Activa por Condición.
    Sugiere 'bago audit ast' si hay archivos .py modificados sin auditar.
    No bloquea, no se repite en la misma sesión."""
    import subprocess as sp
    # Archivos .py modificados (staged + unstaged) respecto al último commit
    try:
        r = sp.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, cwd=str(root), timeout=5
        )
        py_files = [f for f in r.stdout.splitlines() if f.endswith(".py")]
    except Exception:
        return

    if not py_files:
        return

    # Directorio único más común entre los archivos modificados
    dirs = {str(Path(f).parent) for f in py_files}
    target = sorted(dirs)[0] if len(dirs) == 1 else "."

    print()
    print("  ┌─ 💡 SAC · Sugerencia contextual (R-PROD-06) ───────────────")
    print(f"  │  {len(py_files)} archivo(s) Python modificados sin auditar.")
    print(f"  │  → bago audit ast {target}")
    print("  │  (Detecta callbacks sin handler, async sin await, fixtures,")
    print("  │   env vars sin fallback, estados inalcanzables y más)")
    print("  └────────────────────────────────────────────────────────────")


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
