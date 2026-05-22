# 🎨 BAGO Sprite Studio

Generate game sprites, animation sheets, banners, charts, QR codes and more — **no API key required**.

Built on the BAGO framework. Backends: Hugging Face Spaces (Gradio) or GitHub Copilot Codex CLI.

## Tools included

| Script | Purpose |
|--------|---------|
| `generators/sprite_studio.py` | Game sprite generator — characters, animation sheets, icons |
| `generators/image_gen.py` | Local image generator — banners, charts, QR codes (matplotlib + Pillow) |
| `generators/image_studio.py` | Entry point for the full image studio CLI |

## Quick start

```bash
pip install Pillow matplotlib qrcode requests

# Generate BIANCA character sprite (anime style, transparent bg)
python generators/sprite_studio.py --char bianca

# List available character presets
python generators/sprite_studio.py --list-chars

# Generate animation sheet 256×1024
python generators/sprite_studio.py --char bianca --size sheet

# Generate from free prompt
python generators/sprite_studio.py --prompt "pixel art knight, 64x64, transparent bg"

# Open sprite gallery in browser
python generators/sprite_studio.py --gallery

# Local image generation (no network)
python generators/image_gen.py banner          # BAGO banner PNG
python generators/image_gen.py qr "hello"      # QR code
python generators/image_gen.py chart           # metrics chart
python generators/image_gen.py tools           # visual tool map
```

## Sprite sizes

| Key | Dimensions | Use case |
|-----|-----------|---------|
| `standard` | 256×512 | Standing character |
| `sheet` | 256×1024 | 8-frame animation sheet |
| `icon` | 64×64 | Game icon / avatar |
| `banner` | 512×256 | UI banner |
| `WxH` | custom | Any dimension |

## Character presets

| Key | Description |
|-----|-------------|
| `bianca` | BIANCA — protagonist (white hair, dark green hoodie, anime style) |
| `char_girl` | Secondary character — anime female |

Add custom presets in `CHARACTER_PRESETS` inside `sprite_studio.py`.

## Backends

| Backend | Key | Notes |
|---------|-----|-------|
| Hugging Face Gradio Space | `hf` | Free, no account needed |
| GitHub Copilot Codex CLI | `codex` | Requires GitHub Copilot access |

```bash
python generators/sprite_studio.py --backend hf    # force HF
python generators/sprite_studio.py --backend codex # force Codex
```

## Output

Sprites are saved to `sprites_out/` by default. Override with `--out FOLDER`.

A `gallery.html` is generated automatically and can be opened in any browser.

## Requirements

| Package | Version |
|---------|---------|
| Pillow | ≥ 9.0 |
| matplotlib | ≥ 3.6 |
| qrcode | ≥ 7.3 |
| requests | ≥ 2.28 |

## Related repos

- [BAGO](https://github.com/MarcValls/BAGO) — main framework
- [ISO_GAME](https://github.com/MarcValls/ISO_GAME) — isometric engine that uses these sprites
- [BIANCA_THE_GAME](https://github.com/MarcValls/BIANCA_THE_GAME) — game built with these tools
