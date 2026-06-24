"""Rewrite _qwen_box's border construction to use a single color span."""
from pathlib import Path

P = Path(r"C:\Program Files\BAGO\.bago\chat\renderer.py")
text = P.read_text(encoding="utf-8")

# Locate the exact 8-line block we want to replace.
old_block_start = '    bar_len = max(0, top_inner_w - title_w - 1)\n    top = (\n        colorize("\u256d", border_color)\n        + colorize("\u2500", border_color)\n        + colorize(title_text, title_color)\n        + colorize("\u2500" * bar_len + "\u256e", border_color)\n    )\n    bot = colorize("\u2570" + "\u2500" * top_inner_w + "\u256f", border_color)\n    border_left = colorize("\u2502", border_color)\n    border_right = colorize("\u2502", border_color)'

new_block = '    bar_len = max(0, top_inner_w - title_w - 1)\n    if _SUPPORT and border_color:\n        # Apply border_color as a single color span across the top so the\n        # dashes never get visually swallowed by terminal resets. Then\n        # re-color only the title slice with title_color.\n        top_pre = "\u256d\u2500"\n        top_post = ("\u2500" * bar_len) + "\u256e"\n        top = (\n            f"{border_color}{top_pre}{Color.RESET}"\n            f"{title_color}{title_text}{Color.RESET}"\n            f"{border_color}{top_post}{Color.RESET}"\n        )\n        bot = f"{border_color}\u2570{chr(0x2500) * top_inner_w}\u256f{Color.RESET}"\n        border_left = f"{border_color}\u2502{Color.RESET}"\n        border_right = f"{border_color}\u2502{Color.RESET}"\n    else:\n        top = "\u256d\u2500" + title_text + ("\u2500" * bar_len) + "\u256e"\n        bot = "\u2570" + (chr(0x2500) * top_inner_w) + "\u256f"\n        border_left = "\u2502"\n        border_right = "\u2502"'

if old_block_start not in text:
    print("OLD BLOCK NOT FOUND — printing first 500 chars after 'bar_len = max'")
    idx = text.find("bar_len = max")
    print(repr(text[idx:idx + 600]))
    raise SystemExit(1)

text = text.replace(old_block_start, new_block, 1)
P.write_text(text, encoding="utf-8")
print(f"patched {P}")