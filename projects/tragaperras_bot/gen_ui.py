#!/usr/bin/env python3
"""
gen_ui.py — Pre-renderer completo de interfaz para Casino BAGO.
Estilo: "Neo-Vegas Cyber" — noche, neón, metal cromado, holográfico.

Activos generados en static/ui/:
  bg_main.png          430×932  fondo completo (skyline + star field + grid)
  panel_machine.png    390×270  cuerpo de la máquina (sin reels — fondo)
  logo_casino.png      390×90   logo "🎰 CASINO BAGO" cromado + neón
  frame_balance.png    320×68   marco display de saldo (LED ámbar)
  btn_spin.png         390×70   botón GIRAR normal (3D rojo metálico)
  btn_spin_pressed.png 390×70   botón GIRAR pulsado
  btn_daily.png        390×52   botón BONUS DIARIO (verde cyber)
  panel_paytable.png   380×220  fondo tabla de pagos (cristal oscuro)
  panel_jackpot.png    430×932  overlay jackpot (negro+neón dorado)
"""
from __future__ import annotations
import sys
sys.stdout.reconfigure(encoding="utf-8")
import math, os, random, subprocess, sys, io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).parent / "static" / "ui"
OUT.mkdir(parents=True, exist_ok=True)

RNG = random.Random(42)   # reproducible

# ── Paleta ────────────────────────────────────────────────────────────────────
C_BG       = (5,   5,  13)
C_DARK     = (10,  10, 24)
C_PANEL    = (13,  13, 30)
C_PANEL2   = (18,  18, 42)
C_GOLD     = (255, 215, 0)
C_GOLD2    = (200, 155, 0)
C_NEON_R   = (255,  34, 68)
C_NEON_B   = (0,  170, 255)
C_NEON_G   = (0,  255, 136)
C_CHROME_H = (240, 240, 255)   # chrome highlight
C_CHROME_M = (160, 160, 180)   # chrome mid
C_CHROME_S = (60,  60,  80)    # chrome shadow
C_AMBER    = (255, 160, 20)    # LED display color
C_CITY     = (15,  18,  35)    # city silhouette

# ── Helpers ───────────────────────────────────────────────────────────────────

def lerp(a, b, t):
    if isinstance(a, tuple):
        return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))
    return a + (b - a) * t

def clamp(v, lo=0, hi=255):
    return max(lo, min(hi, v))

def add_noise(img: Image.Image, amount: int = 6) -> Image.Image:
    """Añade grano sutil (ruido) a la imagen."""
    import array
    pix = list(img.getdata())
    noisy = []
    for p in pix:
        d = RNG.randint(-amount, amount)
        if len(p) == 4:
            noisy.append((clamp(p[0]+d), clamp(p[1]+d), clamp(p[2]+d), p[3]))
        else:
            noisy.append(tuple(clamp(c+d) for c in p))
    img2 = img.copy()
    img2.putdata(noisy)
    return img2

def rounded_rect_mask(size, radius) -> Image.Image:
    """Máscara RGBA con esquinas redondeadas."""
    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size[0]-1, size[1]-1], radius=radius, fill=255)
    return mask

def paste_centered(base: Image.Image, overlay: Image.Image, y_offset: int = 0):
    ox = (base.width  - overlay.width)  // 2
    oy = (base.height - overlay.height) // 2 + y_offset
    if overlay.mode == "RGBA":
        base.paste(overlay, (ox, oy), overlay)
    else:
        base.paste(overlay, (ox, oy))

def vgradient(w, h, top, bot, alpha=255):
    """Imagen con gradiente vertical."""
    img = Image.new("RGBA", (w, h))
    pix = []
    for y in range(h):
        t = y / max(h-1, 1)
        c = lerp(top, bot, t)
        pix.extend([(*c, alpha)] * w)
    img.putdata(pix)
    return img

def render_text_macos(text: str, font_name: str, size: int,
                       color: tuple = (255,255,255)) -> Image.Image | None:
    """Renderiza texto via AppKit macOS."""
    r, g, b = color
    script = f'''
import Cocoa
import sys

text = {repr(text)}
font = Cocoa.NSFont.fontWithName_size_({repr(font_name)}, {size})
if font is None:
    font = Cocoa.NSFont.systemFontOfSize_({size})
color = Cocoa.NSColor.colorWithRed_green_blue_alpha_({r/255:.3f},{g/255:.3f},{b/255:.3f},1.0)
attrs = {{Cocoa.NSFontAttributeName: font, Cocoa.NSForegroundColorAttributeName: color}}
astr = Cocoa.NSAttributedString.alloc().initWithString_attributes_(text, attrs)
sz = astr.size()
w = max(1, int(sz.width + 8))
h = max(1, int(sz.height + 8))
rep = Cocoa.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
    None, w, h, 8, 4, True, False, Cocoa.NSCalibratedRGBColorSpace, 0, 0)
Cocoa.NSGraphicsContext.setCurrentContext_(
    Cocoa.NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))
Cocoa.NSColor.clearColor().set()
Cocoa.NSRectFill(Cocoa.NSMakeRect(0, 0, w, h))
astr.drawAtPoint_(Cocoa.NSMakePoint(4, 4))
Cocoa.NSGraphicsContext.currentContext().flushGraphics()
data = rep.representationUsingType_properties_(Cocoa.NSBitmapImageFileTypePNG, {{}})
sys.stdout.buffer.write(bytes(data))
'''
    try:
        r = subprocess.run(["python3", "-c", script],
                           capture_output=True, timeout=10)
        if r.returncode == 0 and r.stdout:
            return Image.open(io.BytesIO(r.stdout)).convert("RGBA")
    except Exception:
        pass
    return None

def chrome_text(text: str, font_name: str, size: int) -> Image.Image:
    """Texto con efecto cromado (multicapa: sombra + cuerpo + highlight)."""
    layers = [
        ((30, 10, 10),   2,  2),   # sombra roja oscura
        (C_CHROME_S,     1,  1),   # sombra gris
        (C_CHROME_M,     0,  0),   # cuerpo cromado
        (C_CHROME_H,    -1, -1),   # highlight
        (C_GOLD,         0, -1),   # tinte dorado en top
    ]
    imgs = []
    max_w = max_h = 0
    for col, dx, dy in layers:
        img = render_text_macos(text, font_name, size, col)
        if img:
            imgs.append((img, dx, dy))
            max_w = max(max_w, img.width  + abs(dx) + 4)
            max_h = max(max_h, img.height + abs(dy) + 4)

    if not imgs:
        # Fallback PIL
        canvas = Image.new("RGBA", (len(text)*int(size*0.65)+8, size+12), (0,0,0,0))
        d = ImageDraw.Draw(canvas)
        try:
            fnt = ImageFont.load_default(size=size)
        except Exception:
            fnt = ImageFont.load_default()
        d.text((4, 4), text, font=fnt, fill=C_GOLD+(255,))
        return canvas

    canvas = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
    for img, dx, dy in imgs:
        tmp = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
        ox = 2 + dx
        oy = 2 + dy
        tmp.paste(img, (ox, oy), img)
        canvas = Image.alpha_composite(canvas, tmp)
    return canvas

# ═══════════════════════════════════════════════════════════════════════════════
#  1. FONDO — bg_main.png  (430×932)
# ═══════════════════════════════════════════════════════════════════════════════

def gen_background():
    W, H = 430, 932
    img = Image.new("RGBA", (W, H))
    d   = ImageDraw.Draw(img)

    # ── Gradiente base (espacio profundo) ─────────────────────────────────────
    for y in range(H):
        t = y / H
        # top: azul oscuro → mid: morado oscuro → bot: negro con tinte rojo
        if t < 0.5:
            c = lerp((8, 5, 25), (12, 8, 30), t*2)
        else:
            c = lerp((12, 8, 30), (5, 3, 10), (t-0.5)*2)
        d.line([(0, y), (W, y)], fill=(*c, 255))

    # ── Aurora neon en la cima ─────────────────────────────────────────────────
    for layer_y in range(80):
        t = layer_y / 80
        alpha = int(60 * math.sin(math.pi * t))
        hue_shift = math.sin(layer_y * 0.15) * 0.5 + 0.5
        r = int(lerp(80, 160, hue_shift))
        g = int(lerp(20, 60, 1-hue_shift))
        b = int(lerp(180, 100, hue_shift))
        # línea ondulada
        for x in range(W):
            wave = int(20 * math.sin(x * 0.04 + layer_y * 0.1))
            py = layer_y + wave
            if 0 <= py < H:
                existing = img.getpixel((x, py))
                blended = (
                    clamp(existing[0] + r * alpha // 255),
                    clamp(existing[1] + g * alpha // 255),
                    clamp(existing[2] + b * alpha // 255),
                    255,
                )
                img.putpixel((x, py), blended)

    # ── Campo de estrellas ─────────────────────────────────────────────────────
    for _ in range(320):
        sx = RNG.randint(0, W-1)
        sy = RNG.randint(0, int(H*0.65))
        sz = RNG.choice([1, 1, 1, 2, 2, 3])
        brightness = RNG.randint(140, 255)
        tint = RNG.choice([
            (brightness, brightness, brightness),      # blanco
            (brightness, brightness//2, brightness//2),# rojo
            (brightness//2, brightness//2, brightness),# azul
            (brightness, brightness, brightness//2),   # dorado
        ])
        d.ellipse([sx-sz, sy-sz, sx+sz, sy+sz], fill=(*tint, 220))

    # ── Grid hexagonal en el suelo ────────────────────────────────────────────
    floor_y = int(H * 0.58)
    HEX_R   = 28
    for row in range(12):
        for col in range(-1, 18):
            cx = col * HEX_R * 1.73 + (row % 2) * HEX_R * 0.866
            cy = floor_y + row * HEX_R * 1.5
            alpha_fade = max(0, int(80 * (1 - (cy - floor_y) / (H - floor_y))))
            if alpha_fade < 4:
                continue
            pts = []
            for i in range(6):
                angle = math.radians(60*i - 30)
                pts.append((cx + HEX_R * math.cos(angle), cy + HEX_R * math.sin(angle)))
            # líneas del hexágono
            neon_col = (
                int(lerp(0, 255, row/12)),
                int(lerp(170, 34, row/12)),
                int(lerp(255, 68, row/12)),
            )
            for i in range(6):
                x1, y1 = pts[i]
                x2, y2 = pts[(i+1)%6]
                if 0 < cy < H:
                    d.line([(int(x1), int(y1)), (int(x2), int(y2))],
                           fill=(*neon_col, alpha_fade), width=1)

    # ── Silueta de ciudad ──────────────────────────────────────────────────────
    horizon = int(H * 0.60)
    buildings = []
    x = -10
    while x < W + 20:
        bw = RNG.randint(22, 65)
        bh = RNG.randint(40, 160)
        buildings.append((x, bw, bh))
        x += bw + RNG.randint(2, 12)

    for bx, bw, bh in buildings:
        by = horizon - bh
        # cuerpo
        d.rectangle([bx, by, bx+bw, horizon], fill=(*C_CITY, 255))
        # ventanas iluminadas
        for wy in range(by+6, horizon-8, 10):
            for wx in range(bx+4, bx+bw-4, 8):
                if RNG.random() < 0.35:
                    wc = RNG.choice([(255,200,100),(100,180,255),(255,255,200)])
                    d.rectangle([wx, wy, wx+4, wy+6], fill=(*wc, 180))
        # antena
        if RNG.random() < 0.4:
            ant_x = bx + bw//2
            d.line([(ant_x, by), (ant_x, by-RNG.randint(10,30))], fill=(100,100,120,200), width=1)

    # ── Suelo brillante (reflejo neon) ────────────────────────────────────────
    for y in range(horizon, min(horizon+60, H)):
        t = (y - horizon) / 60.0
        alpha = int(120 * (1 - t))
        for x in range(W):
            wave_r = int(40 * abs(math.sin(x * 0.05 + 0.5)))
            wave_b = int(40 * abs(math.sin(x * 0.07 + 1.5)))
            col = (clamp(C_NEON_R[0]*wave_r//40), 0, clamp(C_NEON_B[2]*wave_b//40))
            existing = img.getpixel((x, y))
            blended = tuple(clamp(existing[j] + col[j] * alpha // 120) for j in range(3)) + (255,)
            img.putpixel((x, y), blended)

    # ── Viñeta ────────────────────────────────────────────────────────────────
    vignette = Image.new("RGBA", (W, H), (0,0,0,0))
    vd = ImageDraw.Draw(vignette)
    for i in range(60):
        t = i / 60
        a = int(160 * t)
        vd.rectangle([i, i, W-i-1, H-i-1], outline=(0,0,0,a), width=1)
    img = Image.alpha_composite(img, vignette)

    # ── Líneas de escaneo (scanlines) ─────────────────────────────────────────
    scan = Image.new("RGBA", (W, H), (0,0,0,0))
    sd = ImageDraw.Draw(scan)
    for y in range(0, H, 3):
        sd.line([(0, y), (W, y)], fill=(0,0,0,18))
    img = Image.alpha_composite(img, scan)

    img = add_noise(img.convert("RGBA"), 3)

    out = OUT / "bg_main.png"
    img.save(out, "PNG", optimize=True)
    print(f"  ✅ bg_main.png  {out.stat().st_size:,}b")
    return img

# ═══════════════════════════════════════════════════════════════════════════════
#  2. LOGO — logo_casino.png  (390×90)
# ═══════════════════════════════════════════════════════════════════════════════

def gen_logo():
    W, H = 390, 90
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Texto cromado+dorado
    text_img = chrome_text("🎰 CASINO BAGO", "Arial-BoldMT", 38)

    # Escalar si es muy ancho
    if text_img.width > W - 20:
        scale = (W - 20) / text_img.width
        text_img = text_img.resize(
            (int(text_img.width*scale), int(text_img.height*scale)),
            Image.LANCZOS,
        )

    # Glow rojo detrás del texto
    glow = text_img.filter(ImageFilter.GaussianBlur(6))
    glow_tinted = Image.new("RGBA", glow.size, (0,0,0,0))
    for px, py in [(x, y) for x in range(glow.width) for y in range(glow.height)]:
        r_, g_, b_, a_ = glow.getpixel((px, py))
        glow_tinted.putpixel((px, py), (255, 60, 80, clamp(a_*2//3)))

    # Pegar en canvas centrado
    gx = (W - glow_tinted.width) // 2 - 2
    gy = (H - glow_tinted.height) // 2
    img.paste(glow_tinted, (gx, gy), glow_tinted)
    tx = (W - text_img.width) // 2
    ty = (H - text_img.height) // 2
    img.paste(text_img, (tx, ty), text_img)

    # Línea neon abajo
    d = ImageDraw.Draw(img)
    for y_off, col, alpha in [(0, C_GOLD, 180), (1, C_NEON_R, 120), (2, (255,255,255), 60)]:
        d.line([(20, H-6+y_off), (W-20, H-6+y_off)],
               fill=(*col, alpha), width=1)

    out = OUT / "logo_casino.png"
    img.save(out, "PNG", optimize=True)
    print(f"  ✅ logo_casino.png  {out.stat().st_size:,}b")

# ═══════════════════════════════════════════════════════════════════════════════
#  3. PANEL MÁQUINA — panel_machine.png  (390×270)
# ═══════════════════════════════════════════════════════════════════════════════

def _chrome_border(draw, rect, width=3, tiers=None):
    """Dibuja borde cromado multicapa."""
    if tiers is None:
        tiers = [C_CHROME_S, C_CHROME_M, C_CHROME_H, C_CHROME_M, C_CHROME_S]
    x1, y1, x2, y2 = rect
    for i, col in enumerate(tiers):
        r = i
        draw.rounded_rectangle(
            [x1+r, y1+r, x2-r, y2-r],
            radius=max(2, 14-r*2),
            outline=(*col, 255), width=1,
        )

def gen_machine_panel():
    W, H = 390, 270
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d    = ImageDraw.Draw(img)

    # ── Fondo base (gradiente oscuro metálico) ────────────────────────────────
    for y in range(H):
        t = y / H
        # Gradiente lateral sutíl
        c = lerp(lerp((25, 20, 55), (15, 12, 38), t),
                 lerp((20, 15, 45), (10, 8, 28), t), 0)
        d.line([(0, y), (W, y)], fill=(*c, 240))

    # Esquinas redondeadas via máscara
    mask = rounded_rect_mask((W, H), 18)
    img.putalpha(mask)

    # ── Borde exterior neón rojo ───────────────────────────────────────────────
    for offset, col, a in [(-2, C_NEON_R, 80), (-1, C_NEON_R, 140), (0, (255,80,100), 200)]:
        d.rounded_rectangle(
            [1+offset, 1+offset, W-2-offset, H-2-offset],
            radius=18, outline=(*col, a), width=2,
        )

    # ── Borde cromado interior ────────────────────────────────────────────────
    _chrome_border(d, [4, 4, W-5, H-5],
                   tiers=[C_CHROME_S, C_CHROME_M, C_CHROME_H, C_CHROME_M, C_CHROME_S])

    # ── Franja superior decorativa ────────────────────────────────────────────
    header_h = 46
    for y in range(6, header_h):
        t = (y - 6) / (header_h - 6)
        c = lerp((40, 30, 80), (20, 15, 45), t)
        d.line([(8, y), (W-9, y)], fill=(*c, 230))
    # separador dorado
    d.line([(10, header_h), (W-11, header_h)], fill=(*C_GOLD, 200), width=1)
    d.line([(10, header_h+1), (W-11, header_h+1)], fill=(*C_GOLD2, 120), width=1)

    # ── LEDs en franja superior ───────────────────────────────────────────────
    led_colors = [C_NEON_R, C_GOLD, C_NEON_G, C_NEON_B] * 4
    led_y      = 24
    leds_x     = [int(16 + i * (W-32)/(len(led_colors)-1)) for i in range(len(led_colors))]
    for lx, lc in zip(leds_x, led_colors):
        for r_off in [5, 3, 1]:
            alphas = {5: 40, 3: 100, 1: 220}
            a = alphas[r_off]
            d.ellipse([lx-r_off, led_y-r_off, lx+r_off, led_y+r_off],
                      fill=(*lc, a))

    # ── Área de rodillos (ventana oscura con marcos cromados) ─────────────────
    reel_y1, reel_y2 = header_h + 12, header_h + 132
    reel_x_start = 14

    # Fondo general ventana rodillos
    d.rounded_rectangle([reel_x_start, reel_y1, W-reel_x_start-1, reel_y2],
                        radius=10, fill=(5, 4, 14, 255))
    # Borde ventana
    d.rounded_rectangle([reel_x_start, reel_y1, W-reel_x_start-1, reel_y2],
                        radius=10, outline=(*C_CHROME_M, 220), width=2)

    # 3 ventanas individuales de rodillo
    reel_w   = int((W - reel_x_start*2 - 16) / 3)
    reel_gap = 8
    for i in range(3):
        rx1 = reel_x_start + 4 + i*(reel_w + reel_gap)
        rx2 = rx1 + reel_w
        ry1, ry2 = reel_y1 + 4, reel_y2 - 4
        # Sombra interior
        d.rounded_rectangle([rx1, ry1, rx2, ry2], radius=8, fill=(4, 3, 10, 255))
        # Marco cromado individual
        _chrome_border(d, [rx1, ry1, rx2, ry2], tiers=[(40,40,60),(80,80,100),(140,140,160)])

    # ── Línea de pago (payline) ────────────────────────────────────────────────
    pay_y = (reel_y1 + reel_y2) // 2
    # Glow
    for w, a in [(5, 30), (3, 80), (1, 200)]:
        d.line([(reel_x_start+4, pay_y), (W-reel_x_start-5, pay_y)],
               fill=(*C_GOLD, a), width=w)

    # ── Estrellas decorativas en esquinas ─────────────────────────────────────
    for sx, sy in [(18, 12), (W-18, 12), (18, H-12), (W-18, H-12)]:
        for r, a in [(6, 40), (4, 80), (2, 160), (1, 240)]:
            d.ellipse([sx-r, sy-r, sx+r, sy+r], fill=(*C_GOLD, a))

    # ── Zona inferior: resultado + decoración ────────────────────────────────
    result_y = reel_y2 + 6
    for y in range(result_y, H-6):
        t = (y - result_y) / (H - 6 - result_y + 1)
        c = lerp((30, 22, 65), (18, 12, 40), t)
        d.line([(10, y), (W-11, y)], fill=(*c, 200))

    # Texto "BAGO" marca de agua tenue
    brand = render_text_macos("B A G O", "Arial-BoldMT", 11, (80, 60, 160))
    if brand:
        bx = (W - brand.width) // 2
        by = H - brand.height - 8
        img.paste(brand, (bx, by), brand)

    out = OUT / "panel_machine.png"
    img.save(out, "PNG", optimize=True)
    print(f"  ✅ panel_machine.png  {out.stat().st_size:,}b")

# ═══════════════════════════════════════════════════════════════════════════════
#  4. FRAME BALANCE — frame_balance.png  (320×68)
# ═══════════════════════════════════════════════════════════════════════════════

def gen_balance_frame():
    W, H = 320, 68
    img  = Image.new("RGBA", (W, H), (0,0,0,0))
    d    = ImageDraw.Draw(img)

    # Fondo dark glass
    d.rounded_rectangle([0, 0, W-1, H-1], radius=16, fill=(8, 6, 20, 240))

    # Borde ámbar multicapa (estilo LED)
    for offset, a in [(0, 200), (1, 120), (2, 60), (3, 30)]:
        d.rounded_rectangle([offset, offset, W-1-offset, H-1-offset],
                            radius=16-offset, outline=(*C_AMBER, a), width=1)

    # Puntos LED decorativos en los lados
    for y in range(12, H-12, 10):
        for bx, ba in [(6, 200), (7, 100)]:
            d.ellipse([bx-2, y-2, bx+2, y+2], fill=(*C_AMBER, ba))
            d.ellipse([W-bx-2, y-2, W-bx+2, y+2], fill=(*C_AMBER, ba))

    # Etiqueta "SALDO" renderizada
    label = render_text_macos("SALDO", "Courier-Bold", 11, (180, 120, 30))
    if label:
        img.paste(label, (14, 8), label)

    # Línea separadora arriba
    d.line([(12, 26), (W-13, 26)], fill=(*C_AMBER, 80), width=1)

    out = OUT / "frame_balance.png"
    img.save(out, "PNG", optimize=True)
    print(f"  ✅ frame_balance.png  {out.stat().st_size:,}b")

# ═══════════════════════════════════════════════════════════════════════════════
#  5. BOTÓN GIRAR — btn_spin.png + btn_spin_pressed.png  (390×70)
# ═══════════════════════════════════════════════════════════════════════════════

def _draw_spin_button(img: Image.Image, pressed: bool = False):
    W, H = img.size
    d    = ImageDraw.Draw(img)

    depth = 0 if pressed else 5
    ry    = depth

    # Sombra (solo normal)
    if not pressed:
        for i in range(depth + 2):
            a = int(160 * (i / (depth+2)))
            d.rounded_rectangle([2+i, 2+i+depth, W-3-i, H-2-i],
                                 radius=16, outline=(180, 10, 30, a), width=1)

    # Cuerpo botón
    for y in range(ry+2, H-3):
        t = (y - ry - 2) / (H - 5 - ry)
        if pressed:
            c = lerp((160, 10, 25), (100, 5, 15), t)
        else:
            c = lerp((220, 30, 55), (150, 10, 30), t)
        d.line([(4, y), (W-5, y)], fill=(*c, 255))

    # Esquinas redondeadas via máscara
    mask = rounded_rect_mask((W, H), 16)
    tmp  = Image.new("L", (W, H), 0)
    tmp2 = ImageDraw.Draw(tmp)
    tmp2.rounded_rectangle([2, ry+2, W-3, H-3], radius=16, fill=255)
    img.putalpha(tmp)

    # Highlight superior (efecto 3D)
    if not pressed:
        for y in range(ry+3, ry+18):
            t = (y - ry - 3) / 15
            a = int(140 * (1 - t))
            d.line([(8, y), (W-9, y)], fill=(255, 255, 255, a), width=1)

    # Borde cromado
    border_c = C_CHROME_S if pressed else C_CHROME_M
    d.rounded_rectangle([3, ry+3, W-4, H-4], radius=15, outline=(*border_c, 200), width=1)
    if not pressed:
        d.rounded_rectangle([3, ry+3, W-4, H//2], radius=15,
                            outline=(255, 255, 255, 60), width=1)

def gen_spin_buttons():
    for pressed, name in [(False, "btn_spin.png"), (True, "btn_spin_pressed.png")]:
        W, H = 390, 70
        img  = Image.new("RGBA", (W, H), (0,0,0,0))
        _draw_spin_button(img, pressed)

        # Texto "GIRAR"
        label_col = (200, 200, 200) if pressed else (255, 255, 255)
        label = render_text_macos("🎰  GIRAR", "Arial-BoldMT", 26, label_col)
        if label:
            if pressed:
                label_img = label
            else:
                # Sombra del texto
                shadow = label.filter(ImageFilter.GaussianBlur(2))
                shadow_colored = Image.new("RGBA", shadow.size)
                for px in range(shadow.width):
                    for py in range(shadow.height):
                        r,g,b,a = shadow.getpixel((px,py))
                        shadow_colored.putpixel((px,py),(100,0,0,a//2))
                label_img = Image.new("RGBA", label.size, (0,0,0,0))
                label_img.paste(shadow_colored, (1,1), shadow_colored)
                label_img.paste(label, (0,0), label)
            lx = (W - label_img.width) // 2
            ly = (H - label_img.height) // 2 + (2 if pressed else 0)
            img.paste(label_img, (lx, ly), label_img)

        out = OUT / name
        img.save(out, "PNG", optimize=True)
        print(f"  ✅ {name}  {out.stat().st_size:,}b")

# ═══════════════════════════════════════════════════════════════════════════════
#  6. BOTÓN BONUS DIARIO — btn_daily.png  (390×52)
# ═══════════════════════════════════════════════════════════════════════════════

def gen_daily_button():
    W, H = 390, 52
    img  = Image.new("RGBA", (W, H), (0,0,0,0))
    d    = ImageDraw.Draw(img)

    # Fondo gradiente verde oscuro
    for y in range(2, H-2):
        t = y / H
        c = lerp((8, 42, 22), (12, 68, 35), t)
        d.line([(4, y), (W-5, y)], fill=(*c, 255))
    mask = rounded_rect_mask((W, H), 14)
    tmp  = Image.new("L", (W, H), 0)
    tmp2 = ImageDraw.Draw(tmp)
    tmp2.rounded_rectangle([2, 2, W-3, H-3], radius=14, fill=255)
    img.putalpha(tmp)

    # Borde verde neon
    for offset, a in [(0, 220), (1, 120), (2, 60)]:
        d.rounded_rectangle([2+offset, 2+offset, W-3-offset, H-3-offset],
                            radius=14-offset, outline=(*C_NEON_G, a), width=1)
    # Highlight
    for y in range(3, 16):
        t = (y-3)/13
        d.line([(8,y),(W-9,y)], fill=(255,255,255,int(80*(1-t))), width=1)

    # Texto
    label = render_text_macos("🎁 BONUS DIARIO  +50🪙", "Arial-BoldMT", 18, C_NEON_G)
    if label:
        lx = (W - label.width) // 2
        ly = (H - label.height) // 2
        img.paste(label, (lx, ly), label)

    out = OUT / "btn_daily.png"
    img.save(out, "PNG", optimize=True)
    print(f"  ✅ btn_daily.png  {out.stat().st_size:,}b")

# ═══════════════════════════════════════════════════════════════════════════════
#  7. PANEL PAYTABLE — panel_paytable.png  (380×220)
# ═══════════════════════════════════════════════════════════════════════════════

def gen_paytable_panel():
    W, H = 380, 220
    img  = Image.new("RGBA", (W, H), (0,0,0,0))
    d    = ImageDraw.Draw(img)

    # Cristal oscuro base
    d.rounded_rectangle([0, 0, W-1, H-1], radius=12, fill=(6, 5, 18, 235))

    # Borde
    d.rounded_rectangle([0, 0, W-1, H-1], radius=12, outline=(50,50,100,200), width=1)
    d.rounded_rectangle([1, 1, W-2, H-2], radius=11, outline=(20,20,50,120), width=1)

    # Scanlines
    for y in range(0, H, 4):
        d.line([(2, y), (W-3, y)], fill=(0,0,0,25))

    # Header bar
    d.rounded_rectangle([2, 2, W-3, 30], radius=10, fill=(20,15,50,200))
    d.line([(4, 31), (W-5, 31)], fill=(*C_GOLD, 120), width=1)

    out = OUT / "panel_paytable.png"
    img.save(out, "PNG", optimize=True)
    print(f"  ✅ panel_paytable.png  {out.stat().st_size:,}b")

# ═══════════════════════════════════════════════════════════════════════════════
#  8. OVERLAY JACKPOT — panel_jackpot.png  (430×932)
# ═══════════════════════════════════════════════════════════════════════════════

def gen_jackpot_overlay():
    W, H = 430, 932
    img  = Image.new("RGBA", (W, H), (0,0,0,0))
    d    = ImageDraw.Draw(img)

    # Fondo negro semitransparente
    d.rectangle([0, 0, W-1, H-1], fill=(0, 0, 0, 220))

    # Rayos dorados desde el centro
    cx, cy = W//2, H//2
    for angle in range(0, 360, 12):
        rad     = math.radians(angle)
        length  = RNG.randint(200, 500)
        x2      = cx + int(length * math.cos(rad))
        y2      = cy + int(length * math.sin(rad))
        for w, a in [(4, 15), (2, 30), (1, 60)]:
            d.line([(cx, cy), (x2, y2)], fill=(*C_GOLD, a), width=w)

    # Círculo central glow
    for r in range(120, 0, -4):
        t = r / 120
        a = int(80 * (1 - t))
        d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(*C_GOLD, a))

    # Grid diagonal sutil
    for y in range(-W, H+W, 40):
        d.line([(0, y), (W, y+W)], fill=(*C_GOLD, 8), width=1)

    out = OUT / "panel_jackpot.png"
    img.save(out, "PNG", optimize=True)
    print(f"  ✅ panel_jackpot.png  {out.stat().st_size:,}b")

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("🎨 Casino BAGO — Generador de UI  [Neo-Vegas Cyber]")
    print(f"   Salida: {OUT}")
    print()
    steps = [
        ("Fondo principal",        gen_background),
        ("Logo casino",            gen_logo),
        ("Panel máquina",          gen_machine_panel),
        ("Frame balance",          gen_balance_frame),
        ("Botones GIRAR",          gen_spin_buttons),
        ("Botón Bonus Diario",     gen_daily_button),
        ("Panel Paytable",         gen_paytable_panel),
        ("Overlay Jackpot",        gen_jackpot_overlay),
    ]
    for label, fn in steps:
        print(f"  🖌  {label}…")
        try:
            fn()
        except Exception as e:
            import traceback
            print(f"  ❌ Error en {label}: {e}")
            traceback.print_exc()
    print(f"\n🎉 UI generada en {OUT}")

if __name__ == "__main__":
    main()
