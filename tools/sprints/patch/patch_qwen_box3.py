"""Insert a gap dash between title and fill so 'Status' is followed by ' ─'."""
from pathlib import Path

P = Path(r"C:\Program Files\BAGO\.bago\chat\renderer.py")
text = P.read_text(encoding="utf-8")

old = (
    '        top_pre = "\u256d\u2500"\n'
    '        top_post = ("\u2500" * bar_len) + "\u256e"\n'
    '        top = (\n'
    '            f"{border_color}{top_pre}{Color.RESET}"\n'
    '            f"{title_color}{title_text}{Color.RESET}"\n'
    '            f"{border_color}{top_post}{Color.RESET}"\n'
    '        )'
)
new = (
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

if old not in text:
    print("NOT FOUND. Current relevant block:")
    idx = text.find('top_pre =')
    print(repr(text[idx - 100: idx + 600]))
    raise SystemExit(1)

text = text.replace(old, new, 1)
P.write_text(text, encoding="utf-8")
print("patched")