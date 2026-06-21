#!/usr/bin/env python3
"""FASE 6.3: CLI for the contract evidence bundle.

Owns:
- argparse surface (build_parser)
- _run_tests, run, main

R0-R10:
- R0: <100 lines
- R8: only argparse + print to stdout/stderr (no business logic)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

BAGO_ROOT = Path(__file__).resolve().parents[1]
if str(BAGO_ROOT) not in sys.path:
    sys.path.insert(0, str(BAGO_ROOT))

# Mirror the sys.path layout that legacy evidence_bundle.py used:
# `.bago/chat/commands.py` provides the `execute` function consumed by the
# generator. Without injecting it, `from commands import execute` resolves
# to bago_core/commands/__init__.py (a different module) and ImportError
# fires.
for _path in (BAGO_ROOT / ".bago" / "core", BAGO_ROOT / ".bago" / "chat",
              BAGO_ROOT / ".bago" / "providers", BAGO_ROOT / ".bago" / "api",
              BAGO_ROOT / ".bago" / "tools"):
    s = str(_path)
    if s not in sys.path:
        sys.path.insert(0, s)

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from bago_core.evidence_model import PROFILES, ContractMockAdapter  # noqa: E402
from bago_core.evidence_generator import generate_bundle  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bago evidence",
        description="Genera bundles de evidencia verificables para los contratos de BAGO v4.",
    )
    parser.add_argument("--mode", choices=("simulated", "real"), default="simulated",
                        help="Tipo de evidencia a generar")
    parser.add_argument("--objective", choices=sorted(PROFILES), default="community-knowledge",
                        help="Objetivo demostrable")
    parser.add_argument("--output", help="Directorio de salida del bundle")
    parser.add_argument("--provider", default="ollama-local", help="Provider para modo real")
    parser.add_argument("--model", default="llama3.2:3b", help="Modelo para modo real")
    parser.add_argument("--base-path", default=str(BAGO_ROOT),
                        help="Base path para config/estado en modo real")
    parser.add_argument("--overwrite", action="store_true",
                        help="Sobrescribe el directorio de salida si existe")
    parser.add_argument("--test", action="store_true",
                        help="Ejecuta la prueba interna del generador")
    return parser


def _run_tests() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "bundle"
        manifest_path = generate_bundle(
            mode="simulated",
            objective="community-knowledge",
            output_dir=output_dir,
            provider="mock-contract",
            model=ContractMockAdapter.MODEL_ID,
            base_path=BAGO_ROOT,
            overwrite=False,
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["status"] == "pass"
        assert any(item["id"] == "plan-generation" for item in manifest["checks"])
        assert (output_dir / "session" / "context.jsonl").exists()
        assert (output_dir / "commands" / "results.json").exists()
        assert (output_dir / "knowledge" / "recent_memories.json").exists()
        print("evidence_bundle.py --test: ALL PASS")
    return 0


def run(args: argparse.Namespace) -> int:
    if getattr(args, "test", False):
        return _run_tests()

    if not getattr(args, "output", None):
        print("Uso: bago evidence --output <directorio> [--mode simulated|real] [--objective ...]")
        return 1

    try:
        manifest_path = generate_bundle(
            mode=args.mode,
            objective=args.objective,
            output_dir=Path(args.output).resolve(),
            provider=args.provider,
            model=args.model,
            base_path=Path(args.base_path).resolve(),
            overwrite=bool(args.overwrite),
        )
    except Exception as exc:
        print(f"❌ No se pudo generar el bundle: {exc}")
        return 1

    print(f"✓ Bundle generado: {manifest_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
