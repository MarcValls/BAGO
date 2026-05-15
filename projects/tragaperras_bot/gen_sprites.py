#!/usr/bin/env python3
"""
gen_sprites.py — Generador de sprites pre-renderizados para Casino BAGO.

Usa AppKit (macOS) para renderizar emojis a alta calidad,
luego PIL para añadir fondos con gradiente, bordes metálicos y glow.
Resultado: 7 PNGs de 110x110 en static/symbols/ + sprite sheet.
"""
from __future__ import annotations
import sys
sys.stdout.reconfigure(encoding="utf-8")
import math
import os
import struct
import subprocess
import sys
from pathlib import Path

OUT_DIR = Path(__file__).parent / "static" / "symbols"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Definición de símbolos ────────────────────────────────────────────────────
SYMBOLS = [
    {
        "id":    "cherry",
        "emoji": "🍒",
        "label": "CEREZA",
        "grad":  [(180, 10, 30), (255, 60, 80)],   # rojo
        "glow":  (255, 80, 100),
        "tier":  1,
    },
    {
        "id":    "lemon",
        "emoji": "🍋",
        "label": "LIMÓN",
        "grad":  [(160, 140, 0), (255, 230, 0)],   # amarillo
        "glow":  (255, 240, 60),
        "tier":  1,
    },
    {
        "id":    "orange",
        "emoji": "🍊",
        "label": "NARANJA",
        "grad":  [(170, 80, 0), (255, 150, 20)],   # naranja
        "glow":  (255, 160, 40),
        "tier":  2,
    },
    {
        "id":    "grape",
        "emoji": "🍇",
        "label": "UVAS",
        "grad":  [(60, 0, 120), (150, 40, 220)],   # morado
        "glow":  (180, 80, 255),
        "tier":  2,
    },
    {
        "id":    "star",
        "emoji": "⭐",
        "label": "ESTRELLA",
        "grad":  [(120, 90, 0), (255, 210, 40)],   # dorado
        "glow":  (255, 220, 60),
        "tier":  3,
    },
    {
        "id":    "diamond",
        "emoji": "💎",
        "label": "DIAMANTE",
        "grad":  [(0, 80, 160), (40, 200, 255)],   # cian
        "glow":  (60, 220, 255),
        "tier":  3,
    },
    {
        "id":    "seven",
        "emoji": "7️⃣",
        "label": "JACKPOT",
        "grad":  [(140, 0, 0), (255, 30, 30)],     # rojo intenso + dorado
        "glow":  (255, 215, 0),
        "tier":  4,
    },
]

CELL = 110  # tamaño del sprite en px


def _render_emoji_macos(emoji: str, size: int) -> bytes | None:
    """Renderiza emoji como PNG usando AppKit (macOS)."""
    script = f'''
import Cocoa, struct, zlib, sys

emoji = {repr(emoji)}
font_size = {size}

font = Cocoa.NSFont.fontWithName_size_("Apple Color Emoji", font_size)
attrs = {{Cocoa.NSFontAttributeName: font}}
astr = Cocoa.NSAttributedString.alloc().initWithString_attributes_(emoji, attrs)

sz = astr.size()
w = max(1, int(sz.width  + 4))
h = max(1, int(sz.height + 4))

rep = Cocoa.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
    None, w, h, 8, 4, True, False, Cocoa.NSCalibratedRGBColorSpace, 0, 0)
Cocoa.NSGraphicsContext.setCurrentContext_(
    Cocoa.NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))
Cocoa.NSColor.clearColor().set()
Cocoa.NSRectFill(Cocoa.NSMakeRect(0, 0, w, h))
astr.drawAtPoint_(Cocoa.NSMakePoint(2, 2))
Cocoa.NSGraphicsContext.currentContext().flushGraphics()

data = rep.representationUsingType_properties_(
    Cocoa.NSBitmapImageFileTypePNG, {{}})
sys.stdout.buffer.write(bytes(data))
'''
    try:
        result = subprocess.run(
            ["python3", "-c", script],
            capture_output=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
    except Exception as e:
        print(f"  ⚠ AppKit render failed: {e}")
    return None


def _lerp_color(c1: tuple, c2: tuple, t: float) -> tuple:
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _make_sprite(sym: dict) -> bool:
    """Genera un sprite PNG de CELL×CELL para el símbolo dado."""
    from PIL import Image, ImageDraw, ImageFilter

    size   = CELL
    img    = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw   = ImageDraw.Draw(img)
    c1, c2 = sym["grad"]
    glow   = sym["glow"]
    tier   = sym["tier"]

    # ── 1. Fondo con gradiente radial ─────────────────────────────────────────
    cx = cy = size // 2
    max_r   = math.hypot(cx, cy)
    for y in range(size):
        for x in range(size):
            d    = math.hypot(x - cx, y - cy)
            t    = min(1.0, d / max_r)
            # esquinas redondeadas: alpha = 0 fuera del circulo suave
            corner_r = size * 0.42
            corner_d = math.hypot(
                max(0, abs(x - cx) - (size//2 - 12)),
                max(0, abs(y - cy) - (size//2 - 12)),
            )
            if corner_d > 11:
                continue
            col = _lerp_color(c2, c1, t)
            draw.point((x, y), (*col, 240))

    # ── 2. Borde metálico ─────────────────────────────────────────────────────
    border_colors = {
        1: [(120,120,120),(200,200,200),(255,255,255),(200,200,200),(140,140,140)],
        2: [(100,80,0),(180,140,0),(255,215,0),(200,160,20),(120,90,0)],
        3: [(0,100,140),(60,180,220),(150,230,255),(80,190,230),(20,110,160)],
        4: [(140,100,0),(220,180,0),(255,230,60),(255,215,0),(160,120,0)],
    }
    metals = border_colors.get(tier, border_colors[1])
    for i, c in enumerate(metals):
        r = 6 + i
        draw.rounded_rectangle([r, r, size-1-r, size-1-r],
                                radius=14-i, outline=(*c, 255), width=1)

    # ── 3. Brillo superior (highlight) ───────────────────────────────────────
    for y in range(4, 28):
        t    = (y - 4) / 24.0
        alph = int(120 * (1 - t))
        for x in range(12, size - 12):
            corner_d = math.hypot(
                max(0, abs(x - cx) - (size//2 - 14)),
                max(0, abs(y - cy) - (size//2 - 14)),
            )
            if corner_d > 10:
                continue
            existing = img.getpixel((x, y))
            blended  = tuple(min(255, existing[j] + int((255 - existing[j]) * alph/120))
                             for j in range(3)) + (existing[3],)
            img.putpixel((x, y), blended)

    # ── 4. Renderizar emoji ───────────────────────────────────────────────────
    emoji_size = size - 22
    emoji_png  = _render_emoji_macos(sym["emoji"], emoji_size)

    if emoji_png:
        from PIL import Image as PILImage
        import io
        emoji_img = PILImage.open(io.BytesIO(emoji_png)).convert("RGBA")
        # Redimensionar manteniendo aspecto, centrar
        ew, eh    = emoji_img.size
        scale     = min((size - 20) / ew, (size - 20) / eh)
        new_w, new_h = int(ew * scale), int(eh * scale)
        emoji_img = emoji_img.resize((new_w, new_h), PILImage.LANCZOS)
        # Sombra suave detrás del emoji
        shadow = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
        for sdy in range(-2, 3):
            for sdx in range(-2, 3):
                ox = (size - new_w) // 2 + sdx + 2
                oy = (size - new_h) // 2 + sdy + 2
                shadow_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                shadow_layer.paste(emoji_img, (ox, oy), emoji_img)
                # Oscurecer para sombra
                shadow_data = [(r//4, g//4, b//4, a//3) for r,g,b,a in shadow_layer.getdata()]
                shadow_layer.putdata(shadow_data)
                img = Image.alpha_composite(img, shadow_layer)

        # Pegar emoji centrado
        ox = (size - new_w) // 2
        oy = (size - new_h) // 2 - 2
        base = img.copy()
        base.paste(emoji_img, (ox, oy), emoji_img)
        img = base
    else:
        # Fallback: texto grande si AppKit no funciona
        from PIL import ImageFont
        draw2 = ImageDraw.Draw(img)
        try:
            fnt = ImageFont.load_default(size=int(size * 0.55))
        except Exception:
            fnt = ImageFont.load_default()
        bbox  = draw2.textbbox((0, 0), sym["emoji"], font=fnt)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        draw2.text(((size-tw)//2, (size-th)//2 - 4), sym["emoji"],
                   font=fnt, fill=(255, 255, 255, 255))

    # ── 5. Glow exterior ─────────────────────────────────────────────────────
    glow_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    for r_off in range(5, 0, -1):
        alpha = int(40 * r_off / 5)
        gd.rounded_rectangle(
            [5 - r_off, 5 - r_off, size-5+r_off, size-5+r_off],
            radius=16,
            outline=(*glow, alpha),
            width=2,
        )
    img = Image.alpha_composite(img, glow_layer)

    # ── 6. Guardar ────────────────────────────────────────────────────────────
    out = OUT_DIR / f"{sym['id']}.png"
    img.save(out, "PNG", optimize=True)
    print(f"  ✅ {sym['id']:10s} → {out.name}  ({out.stat().st_size:,} bytes)")
    return True


def _make_sprite_sheet():
    """Genera hoja de sprites horizontal con todos los símbolos."""
    from PIL import Image
    cols = len(SYMBOLS)
    sheet = Image.new("RGBA", (CELL * cols, CELL), (0, 0, 0, 0))
    for i, sym in enumerate(SYMBOLS):
        p = OUT_DIR / f"{sym['id']}.png"
        if p.exists():
            tile = Image.open(p).convert("RGBA")
            sheet.paste(tile, (i * CELL, 0), tile)
    out = OUT_DIR / "sprites_sheet.png"
    sheet.save(out, "PNG", optimize=True)
    print(f"\n  📋 Sprite sheet → {out.name}  ({out.stat().st_size:,} bytes)")


def main():
    print("🎰 Casino BAGO — Generador de Sprites")
    print(f"   Salida: {OUT_DIR}")
    print()
    ok = 0
    for sym in SYMBOLS:
        print(f"  🎨 Renderizando {sym['emoji']}  {sym['label']}…")
        try:
            if _make_sprite(sym):
                ok += 1
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback; traceback.print_exc()

    print()
    _make_sprite_sheet()
    print(f"\n🎉 {ok}/{len(SYMBOLS)} sprites generados en {OUT_DIR}")


if __name__ == "__main__":
    main()
