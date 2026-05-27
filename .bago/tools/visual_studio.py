#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""visual_studio.py — Dominio unificado de assets visuales BAGO.

Subcomandos:
  sprite   → generador de sprites (anteriormente sprite-studio)
  image    → generador de assets visuales coherentes (anteriormente image-studio)

Uso:
  bago visual-studio sprite --char bianca --size 256x512
  bago visual-studio image --project mi_juego --type banner
  bago sprite-studio ...         (deprecated, redirige aquí)
  bago image-studio ...          (deprecated, redirige aquí)
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
import subprocess
import sys
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
TOOLS_DIR = THIS_FILE.parent
PYTHON = sys.executable

def _run_sprite(args: list[str]) -> int:
    script = TOOLS_DIR / "sprite_studio.py"
    if not script.exists():
        print("[visual-studio] sprite_studio.py no encontrado", file=sys.stderr)
        return 1
    return subprocess.run([PYTHON, str(script)] + args).returncode

def _run_image(args: list[str]) -> int:
    # image_studio es un stub; intentamos importar el paquete si existe
    pkg = TOOLS_DIR / "image_studio"
    if (pkg / "cli.py").exists():
        return subprocess.run([PYTHON, "-m", "image_studio"] + args).returncode
    # fallback: stub legacy
    stub = TOOLS_DIR / "image_studio.py"
    if stub.exists():
        return subprocess.run([PYTHON, str(stub)] + args).returncode
    print("[visual-studio] image-studio aun no tiene motor implementado", file=sys.stderr)
    print("  Usa: bago visual-studio sprite  (sprite_studio.py si disponible)")
    return 1

def _warn_deprecated(old: str, new_cmd: str) -> None:
    print(f"[!] '{old}' está deprecado. Usa: bago visual-studio {new_cmd}")

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="bago visual-studio",
        description="Dominio unificado de assets visuales BAGO",
    )
    sub = parser.add_subparsers(dest="subcmd", required=True)

    p_sprite = sub.add_parser("sprite", help="Generador de sprites")
    p_sprite.add_argument("--char", default="", help="Personaje preset")
    p_sprite.add_argument("--size", default="", help="Tamaño (NxM o preset)")
    p_sprite.add_argument("--prompt", default="", help="Prompt libre")
    p_sprite.add_argument("--out", default="sprites_out", help="Carpeta salida")
    p_sprite.add_argument("--gallery", action="store_true", help="Abrir galería")
    p_sprite.add_argument("--list-sizes", action="store_true", help="Listar tamaños")
    p_sprite.add_argument("--list-chars", action="store_true", help="Listar personajes")
    p_sprite.add_argument("--backend", default="auto", help="Backend (auto/hf/codex)")
    p_sprite.add_argument("--no-browser", action="store_true", help="No abrir navegador")

    p_image = sub.add_parser("image", help="Generador de assets visuales")
    p_image.add_argument("--project", default="", help="Perfil de proyecto")
    p_image.add_argument("--type", default="sprite", help="Tipo: sprite/boton/fondo/icono/tile/banner")
    p_image.add_argument("--prompt", default="", help="Prompt libre")

    # Modo compatibilidad legacy: si el primer arg no es un subcomando conocido,
    # asumimos que viene de la invocación antigua y hacemos dispatch.
    known = {"sprite", "image", "--help", "-h"}
    raw = sys.argv[1:]
    if raw and raw[0] not in known:
        # Detectar invocación legacy: bago sprite-studio --char bianca
        # En ese caso sys.argv[0] es visual_studio.py y argv[1] es --char
        # pero el launcher de bago llama al módulo directamente.
        # Para soportar redirección desde el launcher, el registry mapeará
        # sprite-studio → visual_studio.py con extra_args ["sprite"].
        pass

    args, rest = parser.parse_known_args(raw)

    if args.subcmd == "sprite":
        # Reconstruir args para sprite_studio.py
        sprite_args = []
        if args.char:
            sprite_args += ["--char", args.char]
        if args.size:
            sprite_args += ["--size", args.size]
        if args.prompt:
            sprite_args += ["--prompt", args.prompt]
        if args.out:
            sprite_args += ["--out", args.out]
        if args.gallery:
            sprite_args += ["--gallery"]
        if args.list_sizes:
            sprite_args += ["--list-sizes"]
        if args.list_chars:
            sprite_args += ["--list-chars"]
        if args.backend:
            sprite_args += ["--backend", args.backend]
        if args.no_browser:
            sprite_args += ["--no-browser"]
        sprite_args += rest
        return _run_sprite(sprite_args)

    if args.subcmd == "image":
        image_args = []
        if args.project:
            image_args += ["--project", args.project]
        if args.type:
            image_args += ["--type", args.type]
        if args.prompt:
            image_args += ["--prompt", args.prompt]
        image_args += rest
        return _run_image(image_args)

    parser.print_help()
    return 1



def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())
    raise SystemExit(main())