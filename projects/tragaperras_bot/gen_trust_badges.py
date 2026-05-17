#!/usr/bin/env python3
"""
gen_trust_badges.py — Genera sprites de confianza para Casino BAGO.
Trust badges con estilo Neo-Vegas Cyber (consistente con gen_ui.py).
No requiere macOS — solo Pillow.
"""
from __future__ import annotations
import sys
sys.stdout.reconfigure(encoding="utf-8")
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).parent / "static" / "ui"
OUT.mkdir(parents=True, exist_ok=True)

# ── Paleta (misma que gen_ui.py) ─────────────────────────────────────────────
C_BG      = (5,   5,  13)
C_DARK    = (10,  10, 24)
C_GOLD    = (255, 215,  0)
C_GOLD2   = (200, 155,  0)
C_NEON_G  = (0,  255, 136)
C_NEON_B  = (0,  170, 255)
C_NEON_R  = (255,  34,  68)
C_AMBER   = (255, 160,  20)
C_CHROME  = (220, 220, 240)
C_GREEN   = (30, 200, 80)

def lerp(a, b, t):
    if isinstance(a, tuple):
        return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))
    return a + (b - a) * t

def rounded_rect(draw, xy, radius, fill, outline=None, outline_width=2):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill,
                           outline=outline, width=outline_width)

def neon_glow(img: Image.Image, color, radius=8, strength=0.6) -> Image.Image:
    """Añade halo de neón a imagen RGBA."""
    r, g, b = color[:3]
    glow_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    alpha = img.split()[3] if img.mode == 'RGBA' else Image.new('L', img.size, 255)
    colored = Image.new('RGBA', img.size, (r, g, b, 0))
    colored.putalpha(alpha)
    blurred = colored.filter(ImageFilter.GaussianBlur(radius))
    # Increase opacity of glow
    glow_data = blurred.getdata()
    glow_enhanced = [(px[0], px[1], px[2], min(255, int(px[3] * strength * 3))) for px in glow_data]
    blurred.putdata(glow_enhanced)
    glow_layer = Image.alpha_composite(glow_layer, blurred)
    glow_layer = Image.alpha_composite(glow_layer, blurred)
    return Image.alpha_composite(glow_layer, img)

def make_badge(width: int, height: int, icon: str, title: str, subtitle: str,
               accent_color, filename: str):
    """Genera un badge de confianza con icono, título y subtítulo."""
    W, H = width, height
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Fondo con gradiente vertical
    for y in range(H):
        t = y / H
        c = lerp((15, 15, 35), (8, 8, 20), t)
        draw.line([(0, y), (W, y)], fill=(*c, 240))

    # Borde exterior neón (doble)
    ac = accent_color
    rounded_rect(draw, (0, 0, W-1, H-1), radius=12,
                 fill=None, outline=(*ac[:3], 180), outline_width=2)
    rounded_rect(draw, (2, 2, W-3, H-3), radius=10,
                 fill=None, outline=(*ac[:3], 60), outline_width=1)

    # Franja superior de color
    for x in range(4, W-4):
        t = x / W
        alpha = int(200 * math.sin(t * math.pi))
        draw.line([(x, 3), (x, 6)], fill=(*ac[:3], alpha))

    # Checkmark / icono círculo
    cx, cy = 36, H // 2
    r = 16
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(*ac[:3], 40),
                 outline=(*ac[:3], 200), width=2)

    # Intentar con fuente del sistema, fallback a default
    try:
        font_big = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 13)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 10)
        font_icon = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", 18)
    except OSError:
        try:
            font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
            font_icon = font_big
        except OSError:
            font_big = font_small = font_icon = ImageFont.load_default()

    # Icono en el círculo
    draw.text((cx, cy), icon, font=font_icon, fill=(*ac[:3], 255), anchor="mm")

    # Texto título
    tx = cx + r + 10
    draw.text((tx, cy - 9), title, font=font_big, fill=C_CHROME, anchor="lm")

    # Texto subtítulo
    draw.text((tx, cy + 8), subtitle, font=font_small, fill=(*ac[:3], 200), anchor="lm")

    # Punto de luz en esquina superior derecha
    for ri in range(8, 0, -2):
        alpha = int(120 / ri * 2)
        draw.ellipse([W-ri-4, 4-ri//2, W-4+ri, 4+ri], fill=(*ac[:3], alpha))

    # Guardar
    out_path = OUT / filename
    img_glow = neon_glow(img, ac, radius=6, strength=0.3)
    img_glow.save(out_path)
    print(f"  ✓ {filename} ({W}×{H})")
    return img_glow


def make_trust_strip():
    """Genera una barra horizontal con 4 badges en fila."""
    badges = [
        ("✓", "ALGORITMO JUSTO", "Provably Fair", C_NEON_G, "badge_fair.png"),
        ("📊", "RTP 94.2%", "Auditado + verificable", C_GOLD, "badge_rtp.png"),
        ("🔒", "SIN CUSTODIA", "Tu wallet, tu control", C_NEON_B, "badge_nocustody.png"),
        ("+18", "JUEGO SEGURO", "Autoexclusión activa", C_AMBER, "badge_safe.png"),
    ]

    BW, BH = 170, 60  # badge width, height
    GAP = 8
    COLS = 2
    ROWS = 2
    SW = COLS * BW + (COLS - 1) * GAP
    SH = ROWS * BH + (ROWS - 1) * GAP

    strip = Image.new('RGBA', (SW, SH), (0, 0, 0, 0))

    for i, (icon, title, sub, color, fname) in enumerate(badges):
        badge = make_badge(BW, BH, icon, title, sub, color, fname)
        col = i % COLS
        row = i // COLS
        x = col * (BW + GAP)
        y = row * (BH + GAP)
        strip.paste(badge, (x, y), badge)

    strip_path = OUT / "trust_strip.png"
    strip.save(strip_path)
    print(f"  ✓ trust_strip.png ({SW}×{SH})")


def make_welcome_header():
    """Genera un header de bienvenida profesional."""
    W, H = 390, 80
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Gradiente
    for y in range(H):
        t = y / H
        c = lerp((12, 12, 30), (5, 5, 15), t)
        alpha = int(220 * (1 - t * 0.3))
        draw.line([(0, y), (W, y)], fill=(*c, alpha))

    # Línea superior dorada
    for x in range(W):
        t = x / W
        a = int(255 * math.sin(t * math.pi))
        draw.point((x, 0), fill=(*C_GOLD, a))
        draw.point((x, 1), fill=(*C_GOLD2, a // 2))

    # Texto principal
    try:
        f_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
        f_sub   = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 11)
    except OSError:
        try:
            f_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
            f_sub   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
        except OSError:
            f_title = f_sub = ImageFont.load_default()

    draw.text((W//2, 26), "🎰 ENTRETENIMIENTO VERIFICADO", font=f_title,
              fill=(*C_GOLD, 255), anchor="mm")
    draw.text((W//2, 48), "Fichas virtuales · Algoritmo público · Sin depósitos reales",
              font=f_sub, fill=(*C_CHROME, 200), anchor="mm")
    draw.text((W//2, 64), "Casino BAGO — Juega con responsabilidad · Solo +18",
              font=f_sub, fill=(*C_AMBER, 160), anchor="mm")

    # Línea inferior
    for x in range(W):
        t = x / W
        a = int(180 * math.sin(t * math.pi))
        draw.point((x, H-1), fill=(*C_NEON_B[:3], a))

    out_path = OUT / "welcome_header.png"
    img.save(out_path)
    print(f"  ✓ welcome_header.png ({W}×{H})")


if __name__ == '__main__':
    print("🎨 Generando trust badges...")
    make_badge(170, 60, "✓", "ALGORITMO JUSTO", "Provably Fair",         C_NEON_G, "badge_fair.png")
    make_badge(170, 60, "📊", "RTP 94.2%",      "Auditado + verificable", C_GOLD,   "badge_rtp.png")
    make_badge(170, 60, "🔒", "SIN CUSTODIA",   "Tu wallet, tu control",  C_NEON_B, "badge_nocustody.png")
    make_badge(170, 60, "+18","JUEGO SEGURO",   "Autoexclusión activa",   C_AMBER,  "badge_safe.png")
    make_trust_strip()
    make_welcome_header()
    print("✅ Todos los trust badges generados en static/ui/")
