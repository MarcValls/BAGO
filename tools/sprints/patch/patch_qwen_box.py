"""Replace the Qwen box renderer in renderer.py with state-aware version."""
import io
import re
import sys
from pathlib import Path

P = Path(r"C:\Program Files\BAGO\.bago\chat\renderer.py")
text = P.read_text(encoding="utf-8")

# Locate the bounds of _qwen_box. It starts with `def _qwen_box(` and ends
# just before the next top-level `def ` (at column 0) or `print_message_qwen`.
start = text.find("def _qwen_box(")
assert start >= 0, "_qwen_box not found"

# Find the end: the next top-level `def ` after start.
m = re.compile(r"\ndef ", re.MULTILINE)
m_iter = list(m.finditer(text, start + 1))
end = m_iter[0].start() if m_iter else len(text)

print(f"replacing bytes {start}..{end} (len={end - start})")

new_block = '''def _qwen_box(
    title: str,
    body: str,
    role: str = "system",
    state: str = "static",
    min_width: int = 30,
    max_width: int = 140,
) -> str:
    """Render a Qwen-style framed box with optional state indicator.

    state values:
      - "draft"    : user typing, glyph U+270E, border/title DIM.
      - "sent"     : user message sent, glyph U+2713, border/title BRIGHT_WHITE.
      - "received" : assistant replied, glyph U+25CF, border/title BRIGHT_CYAN.
      - "static"   : system / status, no glyph, border/title DIM.
    """
    import shutil as _sh
    cols = _sh.get_terminal_size((100, 20)).columns
    width = max(min_width, min(max_width, cols - 2))

    if role == "assistant":
        title_color = Color.BRIGHT_CYAN
        border_color = Color.BRIGHT_CYAN
        glyph = "\\u25cf"
    elif role == "user":
        if state == "draft":
            title_color = Color.DIM
            border_color = Color.DIM
            glyph = "\\u270e"
        elif state == "sent":
            title_color = Color.BRIGHT_WHITE
            border_color = Color.BRIGHT_WHITE if hasattr(Color, "BRIGHT_WHITE") else Color.DIM
            glyph = "\\u2713"
        else:
            title_color = Color.BRIGHT_WHITE
            border_color = Color.DIM
            glyph = None
    else:
        title_color = Color.DIM
        border_color = Color.DIM
        glyph = None

    glyph_str = f" {glyph} " if glyph else ""
    title_text = f" {title}{glyph_str}"
    title_w = _visible_width(title_text)
    top_inner_w = width - 2
    if title_w + 1 > top_inner_w:
        title_text = title_text[: top_inner_w - 2] + "\\u2026 "
        title_w = _visible_width(title_text)
    bar_len = max(0, top_inner_w - title_w - 1)
    top = (
        colorize("\\u256d", border_color)
        + colorize("\\u2500", border_color)
        + colorize(title_text, title_color)
        + colorize("\\u2500" * bar_len + "\\u256e", border_color)
    )
    bot = colorize("\\u2570" + "\\u2500" * top_inner_w + "\\u256f", border_color)
    border_left = colorize("\\u2502", border_color)
    border_right = colorize("\\u2502", border_color)

    inner_w = width - 4
    raw = body if body else ""
    lines_out = []
    for src_line in raw.splitlines() or [""]:
        for chunk in _wrap_line(src_line, inner_w):
            pad = " " * max(0, inner_w - _visible_width(chunk))
            lines_out.append(border_left + " " + chunk + pad + " " + border_right)
    if not lines_out:
        pad = " " * inner_w
        lines_out.append(border_left + " " + pad + " " + border_right)

    def _normalize(line, target_visible):
        cur = _visible_width(line)
        if cur == target_visible:
            return line
        if cur < target_visible:
            return line + colorize("\\u2500" * (target_visible - cur), border_color)
        return line

    top = _normalize(top, width)
    bot = _normalize(bot, width)
    return "\\n".join([top] + lines_out + [bot])


def print_qwen_input(prompt: str, content: str, cursor: str = "\\u2588") -> None:
    """Render a single-line Qwen-style input box in draft state.

    Shows the prompt glyph on the left (defaults to U+276F) and the current
    text content plus a blinking cursor block. Border is dim, title has
    the pencil glyph (U+270E).
    """
    import shutil as _sh
    cols = _sh.get_terminal_size((100, 20)).columns
    width = max(30, min(140, cols - 2))
    inner_w = width - 4
    title_text = " Tu \\u270e "
    title_w = _visible_width(title_text)
    top_inner_w = width - 2
    bar_len = max(0, top_inner_w - title_w - 1)
    top = (
        colorize("\\u256d\\u2500", Color.DIM)
        + colorize(title_text, Color.DIM)
        + colorize("\\u2500" * bar_len + "\\u256e", Color.DIM)
    )
    bot = colorize("\\u2570" + "\\u2500" * top_inner_w + "\\u256f", Color.DIM)
    border_left = colorize("\\u2502", Color.DIM)
    border_right = colorize("\\u2502", Color.DIM)

    body = f"{prompt} {content}" if prompt else content
    if not body:
        body = " "
    if _visible_width(body) + _visible_width(cursor) > inner_w:
        body = body[: max(0, inner_w - _visible_width(cursor) - 1)] + "\\u2026"
    body_with_cursor = body + cursor
    pad = " " * max(0, inner_w - _visible_width(body_with_cursor))
    line = border_left + " " + body_with_cursor + pad + " " + border_right
    print(top + "\\n" + line + "\\n" + bot, flush=True)


'''

# Replace in original text. Decode the escapes in new_block from literal \uXXXX.
new_block_decoded = new_block.encode().decode("unicode_escape")

new_text = text[:start] + new_block_decoded + text[end:]
P.write_text(new_text, encoding="utf-8")
print(f"wrote {P} ({len(new_text)} bytes)")