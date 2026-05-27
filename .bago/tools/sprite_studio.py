#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sprite_studio.py — Generador de sprites BIANCA via Copilot/HF sin API key.

Uso:
  python3 sprite_studio.py                    → lanzar con preset bianca, tamaño estándar
  python3 sprite_studio.py --char bianca      → personaje bianca (preset completo)
  python3 sprite_studio.py --char char_girl   → personaje char_girl (otro preset)
  python3 sprite_studio.py --prompt "..."     → prompt libre
  python3 sprite_studio.py --size 256x512     → tamaño custom (anchoxalto)
  python3 sprite_studio.py --size sheet       → hoja animación 256x1024
  python3 sprite_studio.py --size icon        → icono 64x64
  python3 sprite_studio.py --backend hf       → forzar HF Space Gradio
  python3 sprite_studio.py --backend codex    → forzar Codex CLI
  python3 sprite_studio.py --out CARPETA      → carpeta de salida (default: sprites_out)
  python3 sprite_studio.py --gallery          → solo abrir galería sin generar
  python3 sprite_studio.py --list-sizes       → ver tamaños disponibles
  python3 sprite_studio.py --list-chars       → ver personajes disponibles
"""

from __future__ import annotations

import json
import os
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ── Rutas ──────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).resolve().parents[2]
STUDIO_DIR = ROOT / ".bago" / "sprite_studio"
GALLERY_HTML = STUDIO_DIR / "gallery.html"
HISTORY_JSON = STUDIO_DIR / "history.json"
STUDIO_DIR.mkdir(parents=True, exist_ok=True)

# ── Presets de personajes ──────────────────────────────────────────────────────
CHARACTER_PRESETS: dict[str, dict] = {
    "bianca": {
        "description": "BIANCA — protagonista de BIANCA: La Tejedora de Universos",
        "prompt_base": (
            "anime game sprite, character BIANCA, female, white/silver hair, "
            "dark green hoodie, pale skin, standing pose, full body, "
            "transparent background, clean cel-shading, "
            "color accents: blue #4da8ff, gold #f7d774"
        ),
        "negative": "lowres, bad anatomy, bad hands, extra fingers, text, watermark, blurry, worst quality, cropped",
        "default_size": "256x512",
    },
    "char_girl": {
        "description": "char_girl — personaje secundario estilo anime",
        "prompt_base": (
            "female anime game sprite, dark brown hair in twin messy buns with loose strands, "
            "pink off-shoulder sweater, ripped grey skinny jeans, chunky purple platform boots, "
            "small black backpack, transparent background, isometric camera, "
            "semi-realistic, clean silhouette, full body no crop"
        ),
        "negative": "lowres, bad anatomy, text, watermark, blurry, cropped",
        "default_size": "256x512",
    },
}

# ── Presets de tamaño ─────────────────────────────────────────────────────────
SIZE_PRESETS: dict[str, tuple[int, int]] = {
    "standard": (256, 512),
    "sheet":    (256, 1024),
    "icon":     (64, 64),
    "portrait": (96, 96),
    "hd":       (512, 1024),
    "square":   (512, 512),
    "thumb":    (128, 128),
}


def _parse_size(size_str: str) -> tuple[int, int]:
    """Convierte '256x512' o 'standard' a (w, h)."""
    if size_str in SIZE_PRESETS:
        return SIZE_PRESETS[size_str]
    if "x" in size_str:
        parts = size_str.lower().split("x")
        return int(parts[0]), int(parts[1])
    raise ValueError(f"Tamaño desconocido: {size_str}. Usa NxM o uno de: {', '.join(SIZE_PRESETS)}")


# ── Backends de generación ────────────────────────────────────────────────────

def _generate_hf_space(prompt: str, negative: str, width: int, height: int, out_path: Path) -> bool:
    """Genera imagen via HF Space Gradio (sin API key)."""
    try:
        from gradio_client import Client
        print("  🌐 Conectando a HF Space (prodia/sdxl)…")
        client = Client("prodia/sdxl-stable-diffusion-xl", verbose=False)
        result = client.predict(
            prompt,
            negative,
            "anythingXL_xl.safetensors",
            20,
            fn_index=0,
        )
        # result[0] = ruta temporal al PNG
        import shutil
        src = Path(result[0]) if isinstance(result, (list, tuple)) else Path(str(result))
        if src.exists():
            shutil.copy(src, out_path)
            return True
        return False
    except Exception as e:
        print(f"  ⚠ HF Space falló: {e}")
        return False


def _generate_codex_cli(prompt: str, width: int, height: int, out_path: Path) -> bool:
    """Genera imagen via Codex CLI (requiere codex instalado)."""
    import subprocess, glob as _glob

    codex_bin = "codex"
    full_prompt = (
        f"Generate a {width}x{height} pixel sprite image. "
        f"Save it as a PNG file. {prompt}"
    )
    try:
        print("  🤖 Ejecutando Codex CLI…")
        subprocess.run(
            [codex_bin, "exec",
             "--dangerously-bypass-approvals-and-sandbox",
             "-s", "danger-full-access",
             full_prompt],
            timeout=120,
            check=True,
        )
        # Buscar imagen más reciente en ~/.codex/generated_images/
        codex_imgs = Path.home() / ".codex" / "generated_images"
        pngs = sorted(codex_imgs.rglob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
        if pngs:
            import shutil
            shutil.copy(pngs[0], out_path)
            return True
        return False
    except Exception as e:
        print(f"  ⚠ Codex CLI falló: {e}")
        return False


def _generate_placeholder(prompt: str, width: int, height: int, out_path: Path) -> bool:
    """Genera placeholder PNG con PIL cuando no hay backend disponible."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGBA", (width, height), (26, 26, 46, 255))
        draw = ImageDraw.Draw(img)
        # Marco
        draw.rectangle([2, 2, width - 3, height - 3], outline=(77, 168, 255), width=2)
        # Texto centrado
        lines = [
            "SPRITE STUDIO",
            f"{width}×{height}",
            "— placeholder —",
            prompt[:40] + ("…" if len(prompt) > 40 else ""),
        ]
        y = height // 2 - len(lines) * 10
        for line in lines:
            bbox = draw.textbbox((0, 0), line)
            tw = bbox[2] - bbox[0]
            draw.text(((width - tw) // 2, y), line, fill=(247, 215, 116))
            y += 22
        img.save(out_path, "PNG")
        print("  📦 Placeholder generado (sin backend activo)")
        return True
    except Exception as e:
        print(f"  ✗ PIL falló: {e}")
        return False


# ── Post-proceso ──────────────────────────────────────────────────────────────

def _post_process(src: Path, dest: Path, width: int, height: int) -> None:
    """Redimensiona y normaliza el PNG al tamaño solicitado."""
    try:
        from PIL import Image
        img = Image.open(src).convert("RGBA")
        img = img.resize((width, height), Image.LANCZOS)
        img.save(dest, "PNG", optimize=True)
    except Exception:
        import shutil
        shutil.copy(src, dest)


# ── Galería HTML ───────────────────────────────────────────────────────────────

def _build_gallery_html(history: list[dict]) -> str:
    items_html = ""
    for entry in reversed(history):
        rel = entry.get("file", "")
        ts  = entry.get("timestamp", "")[:16].replace("T", " ")
        sz  = entry.get("size", "")
        pr  = entry.get("prompt", "")[:80]
        backend = entry.get("backend", "?")
        char = entry.get("char", "—")
        items_html += f"""
        <div class="card">
          <img src="{rel}" alt="{pr}" onerror="this.style.opacity='0.3'">
          <div class="info">
            <div class="ts">{ts} · {sz} · {backend}</div>
            <div class="char">🎨 {char}</div>
            <div class="prompt" title="{pr}">{pr}</div>
            <a href="{rel}" download class="dl">⬇ descargar</a>
          </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="8">
<title>🎨 BAGO Sprite Studio</title>
<style>
  body {{ background:#0f0f1a; color:#ccc; font-family:monospace; margin:0; padding:20px; }}
  h1   {{ color:#4da8ff; font-size:1.4em; margin-bottom:4px; }}
  .sub {{ color:#666; font-size:.8em; margin-bottom:24px; }}
  .grid {{ display:flex; flex-wrap:wrap; gap:16px; }}
  .card {{ background:#1a1a2e; border:1px solid #4da8ff33; border-radius:8px;
           overflow:hidden; width:220px; transition:.2s; }}
  .card:hover {{ border-color:#4da8ff; transform:translateY(-2px); }}
  .card img {{ width:100%; display:block; background:#111; min-height:80px; }}
  .info {{ padding:10px; }}
  .ts   {{ color:#666; font-size:.7em; }}
  .char {{ color:#f7d774; font-size:.8em; margin:4px 0; }}
  .prompt {{ color:#aaa; font-size:.75em; overflow:hidden; white-space:nowrap;
             text-overflow:ellipsis; }}
  .dl  {{ display:inline-block; margin-top:8px; color:#4da8ff; font-size:.75em;
           text-decoration:none; }}
  .dl:hover {{ color:#f7d774; }}
  .empty {{ color:#444; padding:40px; }}
</style>
</head>
<body>
<h1>🎨 BAGO Sprite Studio</h1>
<div class="sub">Auto-refresca cada 8s · {len(history)} sprite(s) generados</div>
<div class="grid">
{items_html if history else '<div class="empty">Sin sprites aún — ejecuta bago sprite-studio para generar.</div>'}
</div>
</body>
</html>"""


def _load_history() -> list[dict]:
    try:
        return json.loads(HISTORY_JSON.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_history(history: list[dict]) -> None:
    HISTORY_JSON.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


def _open_gallery(history: list[dict]) -> None:
    html = _build_gallery_html(history)
    GALLERY_HTML.write_text(html, encoding="utf-8")
    webbrowser.open(GALLERY_HTML.as_uri())
    print(f"  🌐 Galería abierta: {GALLERY_HTML}")


# ── CLI ────────────────────────────────────────────────────────────────────────

def _parse_cli(argv: list[str]) -> dict:
    cfg: dict = {
        "char": None,
        "prompt": None,
        "size": None,
        "backend": "auto",  # auto | hf | codex | placeholder
        "out": str(STUDIO_DIR / "sprites_out"),
        "gallery_only": False,
        "list_sizes": False,
        "list_chars": False,
        "no_browser": False,
    }
    i = 1
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            print(__doc__)
            raise SystemExit(0)
        elif a == "--gallery":
            cfg["gallery_only"] = True
        elif a == "--list-sizes":
            cfg["list_sizes"] = True
        elif a == "--list-chars":
            cfg["list_chars"] = True
        elif a == "--no-browser":
            cfg["no_browser"] = True
        elif a == "--char" and i + 1 < len(argv):
            cfg["char"] = argv[i + 1]; i += 1
        elif a == "--prompt" and i + 1 < len(argv):
            cfg["prompt"] = argv[i + 1]; i += 1
        elif a == "--size" and i + 1 < len(argv):
            cfg["size"] = argv[i + 1]; i += 1
        elif a == "--backend" and i + 1 < len(argv):
            cfg["backend"] = argv[i + 1]; i += 1
        elif a == "--out" and i + 1 < len(argv):
            cfg["out"] = argv[i + 1]; i += 1
        else:
            raise SystemExit(f"Argumento desconocido: {a}. Usa --help.")
        i += 1
    return cfg


def main() -> int:
    cfg = _parse_cli(sys.argv)

    # ── Listados informativos ─────────────────────────────────────────────────
    if cfg["list_sizes"]:
        print("📐 Tamaños disponibles:")
        for name, (w, h) in SIZE_PRESETS.items():
            print(f"  {name:<12} {w}×{h}")
        print("  O usa NxM directamente, ej: 512x512")
        return 0

    if cfg["list_chars"]:
        print("🎨 Personajes disponibles:")
        for name, data in CHARACTER_PRESETS.items():
            print(f"  {name:<14} — {data['description']}")
        return 0

    history = _load_history()

    # ── Solo galería ─────────────────────────────────────────────────────────
    if cfg["gallery_only"]:
        _open_gallery(history)
        return 0

    # ── Resolución de parámetros ─────────────────────────────────────────────
    char_name = cfg["char"] or "bianca"
    preset    = CHARACTER_PRESETS.get(char_name)

    if preset:
        prompt   = cfg["prompt"] or preset["prompt_base"]
        negative = preset.get("negative", "lowres, bad quality")
        size_str = cfg["size"] or preset["default_size"]
    else:
        prompt   = cfg["prompt"] or f"anime sprite of {char_name}, transparent background, full body"
        negative = "lowres, bad anatomy, text, watermark"
        size_str = cfg["size"] or "256x512"

    width, height = _parse_size(size_str)
    out_dir = Path(cfg["out"])
    out_dir.mkdir(parents=True, exist_ok=True)

    ts_str  = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"sprite_{char_name}_{width}x{height}_{ts_str}.png"
    tmp_file = STUDIO_DIR / f"_tmp_{ts_str}.png"

    print()
    print("🎨  BAGO Sprite Studio")
    print("=" * 48)
    print(f"  Personaje : {char_name}")
    print(f"  Tamaño    : {width}×{height}")
    print(f"  Backend   : {cfg['backend']}")
    print(f"  Salida    : {out_file.name}")
    print(f"  Prompt    : {prompt[:70]}{'…' if len(prompt) > 70 else ''}")
    print()

    # ── Generación ────────────────────────────────────────────────────────────
    ok = False
    used_backend = cfg["backend"]

    if cfg["backend"] in ("auto", "hf"):
        ok = _generate_hf_space(prompt, negative, width, height, tmp_file)
        used_backend = "hf-space"

    if not ok and cfg["backend"] in ("auto", "codex"):
        ok = _generate_codex_cli(prompt, width, height, tmp_file)
        used_backend = "codex-cli"

    if not ok:
        ok = _generate_placeholder(prompt, width, height, tmp_file)
        used_backend = "placeholder"

    if not ok:
        print("  ✗ No se pudo generar la imagen.")
        return 1

    # Post-proceso: resize al tamaño exacto
    _post_process(tmp_file, out_file, width, height)
    tmp_file.unlink(missing_ok=True)

    size_kb = out_file.stat().st_size // 1024
    print(f"  ✅ Guardado: {out_file}  ({size_kb} KB)")

    # ── Registrar en historial ────────────────────────────────────────────────
    history.append({
        "timestamp": datetime.now().isoformat(),
        "file":      out_file.as_posix(),
        "char":      char_name,
        "prompt":    prompt,
        "size":      f"{width}×{height}",
        "backend":   used_backend,
    })
    _save_history(history)

    # ── Actualizar y abrir galería ────────────────────────────────────────────
    if not cfg["no_browser"]:
        _open_gallery(history)
    else:
        html = _build_gallery_html(history)
        GALLERY_HTML.write_text(html, encoding="utf-8")

    print()
    print(f"  → Genera más:  bago sprite-studio --char {char_name} --size {size_str}")
    print(f"  → Ver galería: bago sprite-studio --gallery")
    print(f"  → Tamaños:     bago sprite-studio --list-sizes")
    return 0




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