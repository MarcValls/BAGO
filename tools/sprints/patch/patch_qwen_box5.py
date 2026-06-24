"""Add a ' \u2500' (space + dash) suffix to title_text so the junction is visible.

Before: ' Status' + '─' + '─' + ...   -> visually  'Status──────...'
After:  ' Status \u2500' + '─' + ... -> visually  'Status ───────...'
"""
from pathlib import Path

P = Path(r"C:\Program Files\BAGO\.bago\chat\renderer.py")
text = P.read_text(encoding="utf-8")

# Replace the title_text construction to include the trailing " \u2500".
old = '    glyph_str = f" {glyph} " if glyph else ""\n    title_text = f" {title}{glyph_str}"\n    title_w = _visible_width(title_text)'
new = '    glyph_str = f" {glyph} " if glyph else ""\n    # " \u2500" suffix makes the title-bar junction visible in dim terminals.\n    title_text = f" {title}{glyph_str} \u2500"\n    title_w = _visible_width(title_text)'

if old not in text:
    print("NOT FOUND")
    raise SystemExit(1)

text = text.replace(old, new, 1)

# Also remove the previous "bridge" hack so we don't overshoot the bar budget.
old2 = '    bar_len = max(0, top_inner_w - title_w - 1)\n    # we will inject one extra "\u2500" into the title as a bridge; reserve it.\n    _bridge = 1'
new2 = '    bar_len = max(0, top_inner_w - title_w - 1)'
if old2 in text:
    text = text.replace(old2, new2, 1)

# And simplify the inner branch since the bridge is now baked into title_text.
old3 = (
    '        top_pre = "\u256d\u2500"\n'
    '        # Append a trailing " \u2500" to the title slice so the junction\n'
    '        # "Status \u2500\u2500\u2500\u2500" is visually distinct (the last\n'
    '        # dash of the title is rendered in title_color, then the fill\n'
    '        # continues in border_color).\n'
    '        title_suffix = "\u2500"  # the "bridge" dash, in title_color\n'
    '        title_with_suffix = title_text + title_suffix\n'
    '        title_suffix_w = _visible_width(title_suffix)\n'
    '        fill_dashes = "\u2500" * max(0, bar_len - title_suffix_w)\n'
    '        top_post = fill_dashes + "\u256e"\n'
    '        top = (\n'
    '            f"{border_color}{top_pre}{Color.RESET}"\n'
    '            f"{title_color}{title_with_suffix}{Color.RESET}"\n'
    '            f"{border_color}{fill_dashes}{Color.RESET}"\n'
    '            f"{border_color}\u256e{Color.RESET}"\n'
    '        )'
)
new3 = (
    '        top_pre = "\u256d\u2500"\n'
    '        fill_dashes = "\u2500" * max(0, bar_len)\n'
    '        top_post = fill_dashes + "\u256e"\n'
    '        top = (\n'
    '            f"{border_color}{top_pre}{Color.RESET}"\n'
    '            f"{title_color}{title_text}{Color.RESET}"\n'
    '            f"{border_color}{fill_dashes}{Color.RESET}"\n'
    '            f"{border_color}\u256e{Color.RESET}"\n'
    '        )'
)
if old3 in text:
    text = text.replace(old3, new3, 1)
else:
    # also handle the case where the previous patch used gap_dash + fill_dashes.
    old4 = (
        '        top_pre = "\u256d\u2500"\n'
        '        # One gap dash between title and fill so "Status \u2500\u2500\u2500\u2500" reads cleanly.\n'
        '        gap_dash = "\u2500"\n'
        '        fill_dashes = "\u2500" * max(0, bar_len - 1)\n'
        '        top_post = fill_dashes + gap_dash + "\u256e"\n'
        '        top = (\n'
        '            f"{border_color}{top_pre}{Color.RESET}"\n'
        '            f"{title_color}{title_text}{Color.RESET}"\n'
        '            f"{border_color}{gap_dash}{Color.RESET}"\n'
        '            f"{border_color}{fill_dashes}{Color.RESET}"\n'
        '            f"{border_color}\u256e{Color.RESET}"\n'
        '        )'
    )
    if old4 in text:
        text = text.replace(old4, new3, 1)

P.write_text(text, encoding="utf-8")
print("patched")