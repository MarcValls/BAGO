"""Final split: extract palette + wizard router from repl_menu.py."""
import re
from pathlib import Path

P = Path(r"C:\Program Files\BAGO\.bago\chat\repl_menu.py")
text = P.read_text(encoding="utf-8")


def extract_method(text: str, name: str) -> tuple:
    pat = re.compile(r"    def " + re.escape(name) + r"\b.*?\n", re.DOTALL)
    m = pat.search(text)
    if not m:
        return None, None
    start = m.start()
    rest = text[start + 4:]
    end_m = re.search(r"\n    (def |class )", rest)
    if end_m:
        end = start + 4 + end_m.start() + 1
    else:
        end = len(text)
    return start, text[start:end].rstrip()


# Collect spans for palette + router + tty_ok.
palette_methods = [
    "_command_catalog",
    "_show_command_palette",
    "_show_flat_command_palette",
    "_show_menu",
    "_show_menu_section",
    "_run_menu_item",
]
router_methods = [
    "_run_wizard",
    "_wizard_tty_ok",
]

spans = []
for m in palette_methods + router_methods:
    s, body = extract_method(text, m)
    if s is None:
        print(f"  warn: {m} not found")
        continue
    spans.append((s, s + len(body), m, body))

# Sort spans descending.
spans.sort(key=lambda t: -t[0])

new_palette = []
new_router = []
for s, e, m, body in spans:
    if m in palette_methods:
        new_palette.append(body)
    else:
        new_router.append(body)
    text = text[:s] + text[e:]

# Insert delegators before the class _SafeFileHistory line.
class_marker = "class _SafeFileHistory"
class_pos = text.find(class_marker)
if class_pos < 0:
    class_pos = len(text)

delegators = []
for m in palette_methods + router_methods:
    delegators.append(
        f"    def {m}(self, *args, **kwargs):\n"
        f"        from repl_{'menu_palette' if m in palette_methods else 'menu_router'} "
        f"import {m.lstrip('_')} as _impl\n"
        f"        return _impl(self, *args, **kwargs)\n"
    )

text = text[:class_pos] + "\n".join(delegators) + "\n" + text[class_pos:]
P.write_text(text, encoding="utf-8")
print(f"trimmed: {P.name}")

# Write the two extracted modules.
def format_module(title: str, desc: str, methods: list, bodies: dict) -> str:
    lines = [
        f'"""\nModule: {title}\n{desc}\n\nPublic methods extracted from BagoReplMenuMixin:\n'
    ]
    for m in methods:
        lines.append(f"  - {m}")
    lines.append('"""\n\nfrom __future__ import annotations\nfrom typing import TYPE_CHECKING\n\nimport renderer as R\n\nif TYPE_CHECKING:\n    from repl import BagoREPL\n\n\n')
    for m in methods:
        lines.append(bodies.get(m, "").rstrip() + "\n\n")
    return "\n".join(lines)

bodies_dict = {m: b for _, _, m, b in spans}

palette_module = format_module(
    "repl_menu_palette.py",
    "Free functions for the slash-command palette and menu navigation.",
    palette_methods,
    bodies_dict,
)
router_module = format_module(
    "repl_menu_router.py",
    "Free function that resolves /wizard calls to their module implementations.",
    router_methods,
    bodies_dict,
)

(CHAT := P.parent).joinpath("repl_menu_palette.py").write_text(palette_module, encoding="utf-8")
(CHAT).joinpath("repl_menu_router.py").write_text(router_module, encoding="utf-8")
print("wrote: repl_menu_palette.py, repl_menu_router.py")