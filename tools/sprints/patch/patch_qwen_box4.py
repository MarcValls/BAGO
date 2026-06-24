"""Make the title-bar junction visible: end title with a ' ─' suffix."""
from pathlib import Path

P = Path(r"C:\Program Files\BAGO\.bago\chat\renderer.py")
text = P.read_text(encoding="utf-8")

# Locate the construction of top_pre / top_post / top and patch the
# visible-width accounting so the title ends with a " ─" suffix that
# renders inside the title_color span (making the junction visible).
old = (
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
new = (
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

if old not in text:
    print("NOT FOUND. Searching for 'top_pre ='")
    idx = text.find('top_pre =')
    print(repr(text[idx - 50: idx + 600]))
    raise SystemExit(1)

text = text.replace(old, new, 1)

# Also reduce the dash budget so we don't overshoot. The bar_len
# accounted for the gap_dash; we now consume one more dash as part of
# the title suffix. Adjust the calculation above the if-block.
old_bar = '    bar_len = max(0, top_inner_w - title_w - 1)'
new_bar = '    bar_len = max(0, top_inner_w - title_w - 1)\n    # we will inject one extra "\u2500" into the title as a bridge; reserve it.\n    _bridge = 1'
if old_bar in text and new_bar not in text:
    # only patch if not already done
    text = text.replace(old_bar, new_bar, 1)

P.write_text(text, encoding="utf-8")
print("patched")