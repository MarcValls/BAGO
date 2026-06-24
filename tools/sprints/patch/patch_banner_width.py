"""Rewrite banner() so the B-A-G-O block letters never get cropped."""
from pathlib import Path

P = Path(r"C:\Program Files\BAGO\.bago\chat\renderer.py")
text = P.read_text(encoding="utf-8")

# Locate the existing banner body and replace it.
old_marker_start = "    rendered = []\n    for line in art:\n        rendered.append(colorize(line, accent))\n    rendered.append(colorize(f\"           {version_line}\", dim))\n\n    block = globals().get(\"_QWEN_STATUS_BLOCK\")\n    if not block:\n        body_lines = [colorize(l, accent) for l in art] + [colorize(f\"           {version_line}\", dim)]\n        return _qwen_box(\"BAGO\", \"\\n\".join(body_lines), role=\"system\")\n\n    logo_lines = [colorize(l, accent) for l in art] + [colorize(f\"           {version_line}\", dim)]\n    n = max(len(logo_lines), len(block))\n    left_w = max(_visible_width(l) for l in logo_lines)\n    rows = []\n    for i in range(n):\n        l = logo_lines[i] if i < len(logo_lines) else \"\"\n        r = block[i] if i < len(block) else \"\"\n        l_pad = \" \" * max(0, left_w - _visible_width(l))\n        rows.append(l + l_pad + \"    \" + r)\n    return _qwen_box(\"BAGO\", \"\\n\".join(rows), role=\"system\")"

new_body = '''    import shutil as _sh
    cols = _sh.get_terminal_size((100, 20)).columns
    version_str = f"v{_BAGO_VERSION} \u2014 Session-First AI Chat"

    rendered_logo = [colorize(line, accent) for line in art]
    rendered_logo.append(colorize(f"            {version_str}", dim))

    block = globals().get("_QWEN_STATUS_BLOCK")
    if not block:
        # Logo only: width is content width (no terminal cap).
        content_w = max(_visible_width(l) for l in rendered_logo) + 4
        return _qwen_box("BAGO", "\\n".join(rendered_logo), role="system", min_width=content_w, max_width=max(content_w, 200))

    # Side-by-side layout. Compute widths from content (no cropping).
    left_w = max(_visible_width(l) for l in rendered_logo)
    right_w = max((_visible_width(r) for r in block), default=0)
    side_by_side_w = left_w + 4 + right_w + 4  # 4 = "│ " + " │" borders, plus inner gap

    # If the terminal can fit side-by-side, render one wide box.
    if cols >= side_by_side_w:
        n = max(len(rendered_logo), len(block))
        rows = []
        for i in range(n):
            l = rendered_logo[i] if i < len(rendered_logo) else ""
            r = block[i] if i < len(block) else ""
            l_pad = " " * max(0, left_w - _visible_width(l))
            rows.append(l + l_pad + "    " + r)
        body = "\\n".join(rows)
        return _qwen_box("BAGO", body, role="system", min_width=side_by_side_w, max_width=max(side_by_side_w, 220))

    # Terminal too narrow: stack logo and status in two boxes.
    content_w = max(left_w, right_w) + 4
    logo_body = "\\n".join(rendered_logo)
    status_body = "\\n".join(block)
    logo_box = _qwen_box("BAGO", logo_body, role="system", min_width=content_w, max_width=max(content_w, 200))
    status_box = _qwen_box("Status", status_body, role="system", min_width=content_w, max_width=max(content_w, 200))
    return logo_box + "\\n\\n" + status_box'''

if old_marker_start not in text:
    print("OLD BLOCK NOT FOUND")
    idx = text.find("    rendered = []")
    print(repr(text[idx:idx + 1500]))
    raise SystemExit(1)

text = text.replace(old_marker_start, new_body, 1)
P.write_text(text, encoding="utf-8")
print("patched")