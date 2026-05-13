#!/usr/bin/env python3
"""
gen_ui2.py — Segunda pasada: elimina TODA decoración CSS con sprites.

Genera en static/ui/:
  bar_wallet.png       430×50   top wallet bar
  led_r/y/g/b.png      14×14   LEDs individuales (rojo/dorado/verde/azul)
  payline.png          388×8    línea de pago dorada
  reel_bg.png          114×114  fondo+borde de ventana de rodillo
  reel_fade_top.png    114×40   fundido negro superior (opaco → transp)
  reel_fade_bot.png    114×40   fundido negro inferior (transp → opaco)
  btn_minus.png         42×42   botón −
  btn_plus.png          42×42   botón +
  btn_collect.png      220×58   botón COBRAR jackpot
  bar_jackpot.png      392×46   barra jackpot pool
  jackpot_title.png    380×110  título "🎉 JACKPOT 🎉"
"""
from __future__ import annotations
import io, math, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).parent / "static" / "ui"
OUT.mkdir(parents=True, exist_ok=True)

# ── Paleta ────────────────────────────────────────────────────────────────────
C_BG    = (5, 5, 13)
C_DARK  = (8, 8, 20)
C_GOLD  = (255, 215, 0)
C_GOLD2 = (200, 155, 0)
C_RED   = (255, 34, 68)
C_GREEN = (0, 255, 136)
C_BLUE  = (0, 170, 255)
C_CHR_H = (230, 230, 255)
C_CHR_M = (150, 150, 170)
C_CHR_S = (50, 50, 70)

def clamp(v): return max(0, min(255, int(v)))
def lerp(a, b, t):
    if isinstance(a, tuple):
        return tuple(clamp(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))
    return a + (b - a) * t

def render_text_macos(text, font_name, size, color=(255,255,255)):
    r, g, b = color[:3]
    script = f'''
import Cocoa, sys
text = {repr(text)}
font = Cocoa.NSFont.fontWithName_size_({repr(font_name)}, {size})
if font is None: font = Cocoa.NSFont.boldSystemFontOfSize_({size})
color = Cocoa.NSColor.colorWithRed_green_blue_alpha_({r/255:.3f},{g/255:.3f},{b/255:.3f},1.0)
attrs = {{Cocoa.NSFontAttributeName: font, Cocoa.NSForegroundColorAttributeName: color}}
astr = Cocoa.NSAttributedString.alloc().initWithString_attributes_(text, attrs)
sz = astr.size()
w, h = max(1,int(sz.width+8)), max(1,int(sz.height+8))
rep = Cocoa.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
    None, w, h, 8, 4, True, False, Cocoa.NSCalibratedRGBColorSpace, 0, 0)
Cocoa.NSGraphicsContext.setCurrentContext_(Cocoa.NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))
Cocoa.NSColor.clearColor().set()
Cocoa.NSRectFill(Cocoa.NSMakeRect(0,0,w,h))
astr.drawAtPoint_(Cocoa.NSMakePoint(4,4))
Cocoa.NSGraphicsContext.currentContext().flushGraphics()
data = rep.representationUsingType_properties_(Cocoa.NSBitmapImageFileTypePNG,{{}})
sys.stdout.buffer.write(bytes(data))
'''
    try:
        r = subprocess.run(["python3", "-c", script], capture_output=True, timeout=10)
        if r.returncode == 0 and r.stdout:
            return Image.open(io.BytesIO(r.stdout)).convert("RGBA")
    except Exception:
        pass
    return None

def chrome_rect(draw, x1, y1, x2, y2, radius=12, tiers=None):
    if tiers is None:
        tiers = [C_CHR_S, C_CHR_M, C_CHR_H, C_CHR_M, C_CHR_S]
    for i, c in enumerate(tiers):
        r = i
        draw.rounded_rectangle([x1+r, y1+r, x2-r, y2-r],
                                radius=max(2, radius-r*2),
                                outline=(*c, 255), width=1)

def save(img, name):
    p = OUT / name
    img.save(p, "PNG", optimize=True)
    print(f"  ✅ {name:<28s} {p.stat().st_size:,}b")

# ══════════════════════════════════════════════════════════════════════════════
# 1. WALLET BAR  430×50
# ══════════════════════════════════════════════════════════════════════════════
def gen_bar_wallet():
    W, H = 430, 50
    img = Image.new("RGBA", (W, H))
    d   = ImageDraw.Draw(img)
    # dark glass gradiente
    for y in range(H):
        t = y / H
        c = lerp((12, 10, 30), (6, 5, 18), t)
        d.line([(0, y), (W, y)], fill=(*c, 245))
    # línea neon roja inferior
    d.line([(0, H-1), (W, H-1)], fill=(*C_RED, 200), width=1)
    d.line([(0, H-2), (W, H-2)], fill=(*C_RED, 80), width=1)
    d.line([(0, H-3), (W, H-3)], fill=(*C_RED, 30), width=1)
    # sutil scanline
    for y in range(0, H, 4):
        d.line([(0, y), (W, y)], fill=(0, 0, 0, 18))
    # texto brand pre-renderizado
    brand = render_text_macos("🎰  CASINO BAGO", "Arial-BoldMT", 16, C_GOLD)
    if brand:
        img.paste(brand, (12, (H - brand.height) // 2), brand)
    save(img, "bar_wallet.png")

# ══════════════════════════════════════════════════════════════════════════════
# 2. LEDs individuales  14×14
# ══════════════════════════════════════════════════════════════════════════════
def gen_leds():
    specs = [
        ("led_r.png",  C_RED),
        ("led_y.png",  C_GOLD),
        ("led_g.png",  C_GREEN),
        ("led_b.png",  C_BLUE),
    ]
    for name, color in specs:
        W = H = 14
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d   = ImageDraw.Draw(img)
        cx, cy = W//2, H//2
        # outer glow
        for r in range(7, 3, -1):
            t = (7 - r) / 4
            a = int(80 * t)
            d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(*color, a))
        # core
        d.ellipse([cx-4, cy-4, cx+4, cy+4], fill=(*color, 240))
        # specular highlight
        d.ellipse([cx-3, cy-3, cx-1, cy-1], fill=(255, 255, 255, 160))
        save(img, name)

# ══════════════════════════════════════════════════════════════════════════════
# 3. PAYLINE  388×8
# ══════════════════════════════════════════════════════════════════════════════
def gen_payline():
    W, H = 388, 8
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d    = ImageDraw.Draw(img)
    cx   = W // 2
    # capas: glow exterior → línea brillante → core
    for row, (y0, y1, col, alpha_fn) in enumerate([
        (0, H, C_GOLD, lambda x: int(60 * math.sin(math.pi * x / W))),     # glow wide
        (2, H-2, C_GOLD, lambda x: int(150 * math.sin(math.pi * x / W))),  # medium
        (3, H-3, (255,240,180), lambda x: int(240 * math.sin(math.pi * x / W))),  # core
    ]):
        for x in range(W):
            a = alpha_fn(x)
            if a < 2:
                continue
            for y in range(y0, y1):
                existing = img.getpixel((x, y))
                blended = tuple(clamp(existing[i] + (col[i] if i < 3 else 0) * a // 255)
                                for i in range(3)) + (min(255, existing[3] + a),)
                img.putpixel((x, y), blended)
    save(img, "payline.png")

# ══════════════════════════════════════════════════════════════════════════════
# 4. REEL BACKGROUND FRAME  114×114
# ══════════════════════════════════════════════════════════════════════════════
def gen_reel_bg():
    W = H = 114
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    # dark glass interior
    d.rounded_rectangle([0, 0, W-1, H-1], radius=12, fill=(5, 4, 14, 255))
    # inner shadow (subtle depth)
    for i in range(1, 5):
        a = int(80 * i / 5)
        d.rounded_rectangle([i, i, W-1-i, H-1-i], radius=12-i,
                             outline=(0, 0, 0, a), width=1)
    # chrome border
    chrome_tiers = [C_CHR_S, C_CHR_M, C_CHR_H, C_CHR_M, C_CHR_S]
    for i, c in enumerate(chrome_tiers):
        d.rounded_rectangle([i, i, W-1-i, H-1-i], radius=12-i,
                             outline=(*c, 220), width=1)
    # subtle blue tint glow on border
    d.rounded_rectangle([0, 0, W-1, H-1], radius=12,
                         outline=(0, 80, 160, 60), width=2)
    save(img, "reel_bg.png")

# ══════════════════════════════════════════════════════════════════════════════
# 5. REEL FADES  114×40
# ══════════════════════════════════════════════════════════════════════════════
def gen_reel_fades():
    W, H = 114, 40
    for name, top_to_bot in [("reel_fade_top.png", True), ("reel_fade_bot.png", False)]:
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for y in range(H):
            t = y / H if top_to_bot else (H - y) / H
            a = int(230 * (1 - t))
            img.paste(Image.new("RGBA", (W, 1), (5, 4, 14, a)), (0, y))
        save(img, name)

# ══════════════════════════════════════════════════════════════════════════════
# 6. BET BUTTONS  42×42
# ══════════════════════════════════════════════════════════════════════════════
def gen_bet_buttons():
    for name, symbol in [("btn_minus.png", "−"), ("btn_plus.png", "+")]:
        W = H = 42
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d   = ImageDraw.Draw(img)
        cx = cy = W // 2
        # shadow
        d.ellipse([2, 4, W-2, H-1], fill=(0, 0, 0, 100))
        # body gradient
        for r in range(18, 0, -1):
            t = 1 - r / 18
            c = lerp((30, 25, 70), (18, 15, 45), t)
            d.ellipse([cx-r, cy-r-1, cx+r, cy+r-1], fill=(*c, 255))
        # chrome ring
        for i, (col, a) in enumerate([(C_CHR_S, 200), (C_CHR_M, 180), (C_CHR_H, 140), (C_CHR_M, 100)]):
            d.ellipse([i, i, W-1-i, H-1-i], outline=(*col, a), width=1)
        # highlight arc
        d.arc([4, 4, W-5, H//2+2], start=200, end=340, fill=(255,255,255,80), width=2)
        # symbol
        label = render_text_macos(symbol, "Arial-BoldMT", 22, (220, 210, 255))
        if label:
            lx = (W - label.width) // 2
            ly = (H - label.height) // 2 - 1
            img.paste(label, (lx, ly), label)
        save(img, name)

# ══════════════════════════════════════════════════════════════════════════════
# 7. COLLECT BUTTON  220×58
# ══════════════════════════════════════════════════════════════════════════════
def gen_btn_collect():
    W, H = 220, 58
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d    = ImageDraw.Draw(img)
    # shadow
    d.rounded_rectangle([3, 5, W-3, H-1], radius=14, fill=(120, 80, 0, 120))
    # body — deep gold gradient
    for y in range(2, H-4):
        t = y / H
        c = lerp((220, 160, 0), (140, 90, 0), t)
        d.line([(4, y), (W-5, y)], fill=(*c, 255))
    mask_img = Image.new("L", (W, H), 0)
    mask_d   = ImageDraw.Draw(mask_img)
    mask_d.rounded_rectangle([2, 2, W-3, H-3], radius=14, fill=255)
    img.putalpha(mask_img)
    # top highlight
    for y in range(3, 18):
        t = (y-3)/15
        d.line([(6, y), (W-7, y)], fill=(255,255,255, int(100*(1-t))), width=1)
    # chrome border
    chrome_rect(d, 2, 2, W-3, H-3, radius=14,
                tiers=[(180,130,0),(220,170,0),(255,220,60),(220,170,0),(160,110,0)])
    # text
    label = render_text_macos("¡COBRAR!", "Arial-BoldMT", 22, (10, 5, 0))
    if label:
        lx = (W - label.width) // 2
        ly = (H - label.height) // 2 - 1
        img.paste(label, (lx, ly), label)
    save(img, "btn_collect.png")

# ══════════════════════════════════════════════════════════════════════════════
# 8. JACKPOT BAR  392×46
# ══════════════════════════════════════════════════════════════════════════════
def gen_bar_jackpot():
    W, H = 392, 46
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d    = ImageDraw.Draw(img)
    # dark gold-tinted glass
    d.rounded_rectangle([0, 0, W-1, H-1], radius=12, fill=(14, 11, 4, 240))
    # glow border
    for offset, a in [(0, 180), (1, 100), (2, 50), (3, 25)]:
        d.rounded_rectangle([offset, offset, W-1-offset, H-1-offset],
                             radius=12-offset, outline=(*C_GOLD, a), width=1)
    # inner glow fill
    for y in range(1, H-1):
        t = y / H
        a = int(15 * math.sin(math.pi * t))
        d.line([(2, y), (W-3, y)], fill=(*C_GOLD, a))
    # scanlines
    for y in range(0, H, 3):
        d.line([(2, y), (W-3, y)], fill=(0, 0, 0, 20))
    # label text
    label = render_text_macos("🎯  JACKPOT POOL", "Arial-BoldMT", 12, (180, 130, 20))
    if label:
        img.paste(label, (10, (H - label.height) // 2), label)
    save(img, "bar_jackpot.png")

# ══════════════════════════════════════════════════════════════════════════════
# 9. JACKPOT TITLE  380×110
# ══════════════════════════════════════════════════════════════════════════════
def gen_jackpot_title():
    W, H = 380, 110
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d    = ImageDraw.Draw(img)

    # Render "JACKPOT" in multiple layers for depth
    layers = [
        ("Arial-BoldMT", 56, (80, 50, 0), 3, 3),    # shadow
        ("Arial-BoldMT", 56, C_GOLD2, 1, 1),          # dark gold
        ("Arial-BoldMT", 56, C_GOLD, 0, 0),           # main gold
        ("Arial-BoldMT", 56, (255, 240, 140), -1, -1),# highlight
    ]
    base_img = None
    for font, size, color, dx, dy in layers:
        t_img = render_text_macos("JACKPOT", font, size, color)
        if t_img is None:
            continue
        if base_img is None:
            base_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        tx = (W - t_img.width) // 2 + dx
        ty = (H - t_img.height) // 2 + dy - 8
        base_img.paste(t_img, (tx, ty), t_img)

    if base_img:
        # Gold glow blur behind text
        glow = base_img.filter(ImageFilter.GaussianBlur(8))
        glow_c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for px in range(0, W, 2):
            for py in range(0, H, 2):
                r, g, b, a = glow.getpixel((px, py))
                glow_c.putpixel((px, py), (255, 200, 0, min(255, a * 2)))
                if px+1 < W:
                    glow_c.putpixel((px+1, py), (255, 200, 0, min(255, a * 2)))
                if py+1 < H:
                    glow_c.putpixel((px, py+1), (255, 200, 0, min(255, a * 2)))
                if px+1 < W and py+1 < H:
                    glow_c.putpixel((px+1, py+1), (255, 200, 0, min(255, a * 2)))
        img = Image.alpha_composite(img, glow_c)
        img = Image.alpha_composite(img, base_img)
    else:
        # Fallback
        try:
            fnt = ImageFont.load_default(size=56)
        except Exception:
            fnt = ImageFont.load_default()
        d2 = ImageDraw.Draw(img)
        d2.text((W//2, H//2), "JACKPOT", font=fnt, fill=(*C_GOLD, 255), anchor="mm")

    # Emoji decorativos renderizados
    emoji_img = None
    try:
        ei_script = '''
import Cocoa, sys
text = "🎉"
font = Cocoa.NSFont.fontWithName_size_("Apple Color Emoji", 36)
attrs = {Cocoa.NSFontAttributeName: font}
astr = Cocoa.NSAttributedString.alloc().initWithString_attributes_(text, attrs)
sz = astr.size()
w, h = max(1,int(sz.width+4)), max(1,int(sz.height+4))
rep = Cocoa.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
    None, w, h, 8, 4, True, False, Cocoa.NSCalibratedRGBColorSpace, 0, 0)
Cocoa.NSGraphicsContext.setCurrentContext_(Cocoa.NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))
Cocoa.NSColor.clearColor().set()
Cocoa.NSRectFill(Cocoa.NSMakeRect(0,0,w,h))
astr.drawAtPoint_(Cocoa.NSMakePoint(2,2))
Cocoa.NSGraphicsContext.currentContext().flushGraphics()
data = rep.representationUsingType_properties_(Cocoa.NSBitmapImageFileTypePNG,{{}})
sys.stdout.buffer.write(bytes(data))
'''
        result = subprocess.run(["python3", "-c", ei_script], capture_output=True, timeout=8)
        if result.returncode == 0 and result.stdout:
            emoji_img = Image.open(io.BytesIO(result.stdout)).convert("RGBA")
    except Exception:
        pass

    if emoji_img:
        # Left emoji
        img.paste(emoji_img, (4, (H - emoji_img.height) // 2), emoji_img)
        # Right emoji
        img.paste(emoji_img, (W - emoji_img.width - 4, (H - emoji_img.height) // 2), emoji_img)

    save(img, "jackpot_title.png")

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    print("🎨 Casino BAGO — Gen UI v2  [Sin CSS decorativo]")
    print(f"   Salida: {OUT}\n")
    steps = [
        ("Wallet bar",          gen_bar_wallet),
        ("LEDs",                gen_leds),
        ("Payline",             gen_payline),
        ("Reel background",     gen_reel_bg),
        ("Reel fades",          gen_reel_fades),
        ("Bet buttons ±",       gen_bet_buttons),
        ("Collect button",      gen_btn_collect),
        ("Jackpot bar",         gen_bar_jackpot),
        ("Jackpot title",       gen_jackpot_title),
    ]
    for label, fn in steps:
        print(f"  🖌  {label}…")
        try:
            fn()
        except Exception as e:
            import traceback
            print(f"  ❌ {label}: {e}")
            traceback.print_exc()
    print(f"\n🎉 Completado → {OUT}")

if __name__ == "__main__":
    main()
