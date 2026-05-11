#!/usr/bin/env python3
"""doc_agent.py — Agente de documentación BAGO.

Detecta y actualiza automáticamente los documentos del framework que puedan
haberse quedado desincronizados con el código:

  • docs/COMMANDS.md  ← generado desde tool_registry.py
  • docs/LAYERS.md    ← generado desde las capas del registry
  • README.md         ← sincronizado con métricas vivas del framework

Uso:
  python3 .bago/tools/doc_agent.py              # actualiza todo (modo normal)
  python3 .bago/tools/doc_agent.py --check      # sólo verifica, no escribe
  python3 .bago/tools/doc_agent.py --dry-run    # muestra qué cambiaría
  python3 .bago/tools/doc_agent.py --json       # salida JSON legible por máquina
  python3 .bago/tools/doc_agent.py --no-stage   # no hace git add tras escribir
  python3 .bago/tools/doc_agent.py --test       # auto-test del módulo

Códigos de salida:
  0  — todos los documentos están al día (o se actualizaron sin error)
  1  — al menos un documento estaba desincronizado (modo --check) o falló
  2  — error interno del agente
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

# ── Rutas ─────────────────────────────────────────────────────────────────────
TOOLS_DIR = Path(__file__).resolve().parent
BAGO_ROOT = TOOLS_DIR.parent
REPO_ROOT = BAGO_ROOT.parent
PYTHON    = sys.executable

# ── Helpers de color ──────────────────────────────────────────────────────────

def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m"

def GREEN(s: str)  -> str: return _c("32", s)
def YELLOW(s: str) -> str: return _c("33", s)
def RED(s: str)    -> str: return _c("31", s)
def BOLD(s: str)   -> str: return _c("1",  s)
def DIM(s: str)    -> str: return _c("2",  s)
def CYAN(s: str)   -> str: return _c("36", s)


# ── Descriptor de documento ───────────────────────────────────────────────────

@dataclass
class DocResult:
    name: str           # Nombre humano del documento
    path: str           # Ruta relativa desde REPO_ROOT
    status: str         # "ok" | "updated" | "outdated" | "error" | "skipped"
    message: str = ""
    duration_s: float = 0.0

    @property
    def icon(self) -> str:
        return {
            "ok":       "✅",
            "updated":  "🔄",
            "outdated": "⚠️ ",
            "error":    "❌",
            "skipped":  "⏭️ ",
        }.get(self.status, "•")


# ── Lógica por documento ──────────────────────────────────────────────────────

def _run(args: list[str], *, timeout: int = 30) -> tuple[int, str, str]:
    """Ejecuta un subproceso y devuelve (rc, stdout, stderr)."""
    result = subprocess.run(
        args,
        capture_output=True,
        timeout=timeout,
        cwd=str(REPO_ROOT),
    )
    return (
        result.returncode,
        result.stdout.decode("utf-8", errors="replace").strip(),
        result.stderr.decode("utf-8", errors="replace").strip(),
    )


def _check_commands_md(dry_run: bool, check_only: bool, auto_stage: bool) -> DocResult:
    """Gestiona docs/COMMANDS.md."""
    name = "docs/COMMANDS.md"
    script = str(TOOLS_DIR / "generate_commands_doc.py")
    t0 = time.monotonic()

    rc, out, err = _run([PYTHON, script, "--check"])
    elapsed = time.monotonic() - t0

    if rc == 0:
        return DocResult(name, name, "ok", "Al día", elapsed)

    if check_only or dry_run:
        return DocResult(name, name, "outdated", "Desincronizado (--check)", elapsed)

    # Regenerar
    rc2, out2, err2 = _run([PYTHON, script])
    if rc2 != 0:
        msg = (err2 or out2)[:120]
        return DocResult(name, name, "error", f"Falló la regeneración: {msg}", elapsed)

    if auto_stage:
        _run(["git", "add", str(REPO_ROOT / "docs" / "COMMANDS.md")])

    return DocResult(name, name, "updated", "Regenerado correctamente", time.monotonic() - t0)


def _check_layers_md(dry_run: bool, check_only: bool, auto_stage: bool) -> DocResult:
    """Gestiona docs/LAYERS.md."""
    name = "docs/LAYERS.md"
    script = str(TOOLS_DIR / "generate_layers_doc.py")
    t0 = time.monotonic()

    rc, out, err = _run([PYTHON, script, "--check"])
    elapsed = time.monotonic() - t0

    if rc == 0:
        return DocResult(name, name, "ok", "Al día", elapsed)

    if check_only or dry_run:
        return DocResult(name, name, "outdated", "Desincronizado (--check)", elapsed)

    rc2, out2, err2 = _run([PYTHON, script])
    if rc2 != 0:
        msg = (err2 or out2)[:120]
        return DocResult(name, name, "error", f"Falló la regeneración: {msg}", elapsed)

    if auto_stage:
        _run(["git", "add", str(REPO_ROOT / "docs" / "LAYERS.md")])

    return DocResult(name, name, "updated", "Regenerado correctamente", time.monotonic() - t0)


def _check_readme(dry_run: bool, check_only: bool, auto_stage: bool) -> DocResult:
    """Gestiona README.md."""
    name = "README.md"
    script = str(TOOLS_DIR / "readme_sync.py")
    t0 = time.monotonic()

    if check_only or dry_run:
        rc, out, err = _run([PYTHON, script, "--dry-run"])
        elapsed = time.monotonic() - t0
        # readme_sync --dry-run exit 0 = al día, exit 1 = hay cambios pendientes
        if rc == 0:
            return DocResult(name, name, "ok", "Al día", elapsed)
        return DocResult(name, name, "outdated", "Necesita sincronización", elapsed)

    # Modo normal: deja que readme_sync decida si stagear
    stage_flag = [] if auto_stage else ["--no-stage"]
    rc2, out2, err2 = _run([PYTHON, script] + stage_flag)
    elapsed = time.monotonic() - t0

    if rc2 != 0:
        msg = (err2 or out2)[:120]
        return DocResult(name, name, "error", f"Falló readme_sync: {msg}", elapsed)

    if "actualizado" in out2.lower():
        return DocResult(name, name, "updated", "Sincronizado correctamente", elapsed)
    return DocResult(name, name, "ok", "Ya estaba sincronizado", elapsed)


# ── Agente principal ──────────────────────────────────────────────────────────

DOCS_PIPELINE = [
    ("commands", _check_commands_md),
    ("layers",   _check_layers_md),
    ("readme",   _check_readme),
]


def run_agent(
    *,
    check_only: bool = False,
    dry_run: bool = False,
    auto_stage: bool = True,
    only: list[str] | None = None,
    as_json: bool = False,
    verbose: bool = True,
) -> int:
    """
    Ejecuta el agente de documentación.

    Devuelve:
      0  — todos los documentos OK
      1  — algún documento desincronizado o con error
      2  — error interno
    """
    results: list[DocResult] = []

    for key, handler in DOCS_PIPELINE:
        if only and key not in only:
            results.append(DocResult(key, key, "skipped", "Omitido por --only"))
            continue
        try:
            result = handler(dry_run=dry_run, check_only=check_only, auto_stage=auto_stage)
        except Exception as exc:
            result = DocResult(key, key, "error", f"Excepción interna: {exc}")
        results.append(result)

    if as_json:
        data = {
            "results": [asdict(r) for r in results],
            "ok": all(r.status in ("ok", "updated", "skipped") for r in results),
        }
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif verbose:
        _print_report(results, check_only=check_only, dry_run=dry_run)

    any_fail = any(r.status in ("outdated", "error") for r in results)
    return 1 if any_fail else 0


def _print_report(results: list[DocResult], *, check_only: bool, dry_run: bool) -> None:
    mode = "CHECK" if check_only else ("DRY-RUN" if dry_run else "ACTUALIZAR")
    print()
    print(f"  ┌─────────────────────────────────────────────────┐")
    print(f"  │  BAGO · Agente de documentación · {mode:<13}│")
    print(f"  └─────────────────────────────────────────────────┘")
    print()

    for r in results:
        if r.status == "skipped":
            print(f"  {DIM(r.icon)}  {DIM(r.name):<28}  {DIM('omitido')}")
            continue
        color = GREEN if r.status in ("ok", "updated") else (YELLOW if r.status == "outdated" else RED)
        label = color(r.status.upper())
        msg   = DIM(r.message)
        dur   = DIM(f"({r.duration_s:.2f}s)")
        print(f"  {r.icon}  {BOLD(r.name):<28}  [{label}]  {msg}  {dur}")

    print()
    total   = sum(1 for r in results if r.status != "skipped")
    ok      = sum(1 for r in results if r.status in ("ok", "updated"))
    updated = sum(1 for r in results if r.status == "updated")
    bad     = sum(1 for r in results if r.status in ("outdated", "error"))

    if bad == 0:
        summary = GREEN(f"✅ {ok}/{total} documentos al día")
        if updated:
            summary += f"  ({CYAN(str(updated))} actualizados)"
    else:
        summary = RED(f"⚠️  {bad}/{total} documentos requieren atención")
    print(f"  {summary}")
    print()


# ── Auto-test ─────────────────────────────────────────────────────────────────

def _self_test() -> None:
    """Comprobaciones mínimas del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"

    # Comprobaciones de rutas clave
    assert (TOOLS_DIR / "generate_commands_doc.py").exists(), "generate_commands_doc.py no encontrado"
    assert (TOOLS_DIR / "generate_layers_doc.py").exists(),   "generate_layers_doc.py no encontrado"
    assert (TOOLS_DIR / "readme_sync.py").exists(),            "readme_sync.py no encontrado"

    # DocResult dataclass funciona
    r = DocResult("test", "test/path", "ok", "mensaje de prueba", 0.1)
    assert r.icon == "✅"
    r2 = DocResult("test2", "test2/path", "outdated", "desincronizado", 0.5)
    assert r2.icon == "⚠️ "

    # DOCS_PIPELINE tiene las 3 entradas esperadas
    keys = [k for k, _ in DOCS_PIPELINE]
    assert "commands" in keys, "pipeline: falta 'commands'"
    assert "layers"   in keys, "pipeline: falta 'layers'"
    assert "readme"   in keys, "pipeline: falta 'readme'"

    print("  3/3 tests pasaron")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    args = sys.argv[1:]

    if "--test" in args:
        _self_test()
        return 0

    check_only = "--check" in args
    dry_run    = "--dry-run" in args
    as_json    = "--json" in args
    no_stage   = "--no-stage" in args
    verbose    = "--quiet" not in args

    only: list[str] | None = None
    if "--only" in args:
        idx = args.index("--only")
        if idx + 1 < len(args):
            only = [x.strip() for x in args[idx + 1].split(",")]

    return run_agent(
        check_only=check_only,
        dry_run=dry_run,
        auto_stage=not no_stage,
        only=only,
        as_json=as_json,
        verbose=verbose,
    )


if __name__ == "__main__":
    sys.exit(main())
