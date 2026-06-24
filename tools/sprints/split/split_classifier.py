"""Extract CodeTaskClassification + helpers from task_classifier.py."""
import re
from pathlib import Path

P = Path(r"C:\Program Files\BAGO\bago_core\codegen\task_classifier.py")
text = P.read_text(encoding="utf-8")


def extract_block(text: str, name: str) -> tuple:
    pat = re.compile(
        r"^(?:def|class) " + re.escape(name) + r"\b.*?\n(?=^(?:def|class) |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pat.search(text)
    if not m:
        return None, None
    return m.start(), m.group(0).rstrip()


to_extract = [
    "CodeTaskClassification", "_has_any", "_extract_paths",
    "_resolve_paths", "_confidence",
]
keep = ["classify_code_request"]

spans = []
for n in to_extract:
    s, b = extract_block(text, n)
    if s is not None:
        spans.append((s, s + len(b), n, b))

spans.sort(key=lambda t: -t[0])
extracted = []
for s, e, n, b in spans:
    text = text[:s] + text[e:]
    extracted.append((n, b))

ext_body = '''"""Auto-extracted by split_codegen.py during 4.8.0 modularization."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Iterable

'''
for n, b in extracted:
    ext_body += b + "\n\n"
(P.parent / "task_classifier_models.py").write_text(ext_body, encoding="utf-8")
print(f"wrote: task_classifier_models.py")

# Inject re-exports at the top of task_classifier.py.
header = '''"""task_classifier.py - thin facade.

CodeTaskClassification + private helpers live in task_classifier_models.py.
Public entry point `classify_code_request` stays here.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Iterable

from task_classifier_models import (  # noqa: F401
    CodeTaskClassification,
    _has_any, _extract_paths, _resolve_paths, _confidence,
)

'''
# Remove leading shebang + first docstring if present.
text = re.sub(r"^#!.*\n", "", text)
text = re.sub(r'^""".*?"""\n', "", text, count=1, flags=re.DOTALL)
text = header + text.lstrip()
P.write_text(text, encoding="utf-8")
print(f"trimmed: {P.name}")