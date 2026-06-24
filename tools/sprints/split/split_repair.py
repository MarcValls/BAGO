"""Extract dataclasses and private helpers from repair_loop.py into _models/_helpers."""
import re
from pathlib import Path

P = Path(r"C:\Program Files\BAGO\bago_core\codegen\repair_loop.py")
text = P.read_text(encoding="utf-8")


def extract_block(text: str, name: str) -> tuple:
    """Extract a top-level def/class block."""
    pat = re.compile(
        r"^(?:def|class) " + re.escape(name) + r"\b.*?\n(?=^(?:def|class) |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pat.search(text)
    if not m:
        return None, None
    return m.start(), m.group(0).rstrip()


# What to extract where.
to_models = ["RepairFeedback", "RepairAttempt", "RepairVerdict"]
to_helpers = [
    "_safe_staged_files", "_apply_patch_to_memory", "_build_files_to_validate",
    "_build_initial_prompt", "_build_repair_prompt", "_coerce_to_patches",
    "_extract_failing_lines", "_build_feedback",
]

spans = []
for n in to_models:
    s, b = extract_block(text, n)
    if s is not None:
        spans.append((s, s + len(b), "_models", n, b))

for n in to_helpers:
    s, b = extract_block(text, n)
    if s is not None:
        spans.append((s, s + len(b), "_helpers", n, b))

# Sort descending so we can splice without messing up earlier indices.
spans.sort(key=lambda t: -t[0])

models_body = []
helpers_body = []
for s, e, dest, name, body in spans:
    text = text[:s] + text[e:]
    if dest == "_models":
        models_body.append((name, body))
    else:
        helpers_body.append((name, body))

# Write the extracted modules.
base = '''"""Auto-extracted by split_codegen.py during 4.8.0 modularization."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

'''

models_text = base
for name, body in models_body:
    models_text += body + "\n\n"
(CHAT := P.parent).joinpath("repair_loop_models.py").write_text(models_text, encoding="utf-8")
print(f"wrote: repair_loop_models.py")

helpers_text = base
for name, body in helpers_body:
    helpers_text += body + "\n\n"
(CHAT).joinpath("repair_loop_helpers.py").write_text(helpers_text, encoding="utf-8")
print(f"wrote: repair_loop_helpers.py")

# Inject re-exports at the top of repair_loop.py.
header = '''"""repair_loop.py - thin facade.

Dataclasses live in repair_loop_models.py.
Helpers live in repair_loop_helpers.py.
Public entry point `run_repair_loop` stays here.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from repair_loop_models import (  # noqa: F401
    RepairFeedback, RepairAttempt, RepairVerdict,
)
from repair_loop_helpers import (  # noqa: F401
    _safe_staged_files, _apply_patch_to_memory,
    _build_files_to_validate, _build_initial_prompt,
    _build_repair_prompt, _coerce_to_patches,
    _extract_failing_lines, _build_feedback,
)

'''

# Find the first non-blank line of the original file (after the shebang/docstring).
# Just prepend the header.
text = header + text.lstrip()
# Strip any leading shebang or docstring from the original to avoid duplication.
# The original started with "#!/usr/bin/env python3" usually; remove it.
text = re.sub(r"^#!.*\n", "", text)
text = re.sub(r'^""".*?"""\n', "", text, count=1, flags=re.DOTALL)
text = header + text.lstrip()

P.write_text(text, encoding="utf-8")
print(f"trimmed: {P.name}")