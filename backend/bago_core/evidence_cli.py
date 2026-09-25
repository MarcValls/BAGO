#!/usr/bin/env python3
"""FASE 6.3: CLI for the contract evidence bundle.

Owns:
- argparse surface (build_parser)
- run, main

R0-R10:
- R0: <100 lines
- R8: only argparse + print to stdout/stderr (no business logic)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BAGO_ROOT = Path(__file__).resolve().parents[1]
if str(BAGO_ROOT) not in sys.path:
    sys.path.insert(0, str(BAGO_ROOT))

from bago_core.resolver import add_piece_paths  # noqa: E402

# Mirror the runtime search path through the resolver so the evidence bundle
# keeps loading the same package pieces without repeating package layout rules.
add_piece_paths("core.package", "chat.package", "providers.package", "api.package", "tools.package")

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from bago_core.evidence_model import PROFILES  # noqa: E402
from bago_core.evidence_authorized import generate_bundle  # noqa: E402


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
    parser.add_argument("--provider", default="ollama-cloud", help="Provider para modo real")
    parser.add_argument("--model", default="deepseek-v3.1:671b", help="Modelo para modo real")
    parser.add_argument("--base-path", default=str(BAGO_ROOT),
                        help="Base path para config/estado en modo real")
    parser.add_argument("--overwrite", action="store_true",
                        help="Sobrescribe el directorio de salida si existe")
    return parser


def run(args: argparse.Namespace) -> int:
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
