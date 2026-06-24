"""Split evidence_generator.py: extract helpers into evidence_generator_helpers.py."""
import re
from pathlib import Path

P = Path(r"C:\Program Files\BAGO\bago_core\evidence_generator.py")
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


# These helpers move to evidence_generator_helpers.py.
to_helpers = [
    "_sanitize_result",
    "_run_status_and_memory",
    "_run_simulated_repl",
    "_run_repl_commands",
    "_collect_evidence",
    "_build_baseline_checks",
    "_build_manifest_checks",
    "_build_manifest",
    "_write_bundle_artifacts",
    "_write_report",
    "_finalize_manifest",
    "_run_session_phase",
    "_build_checks_and_manifest",
]

# These stay in evidence_generator.py (orchestrators).
keep = [
    "_generate_bundle_with_manager",
    "_run_simulated_bundle",
    "_run_live_bundle",
    "generate_bundle",
]

spans = []
for n in to_helpers:
    s, b = extract_block(text, n)
    if s is not None:
        spans.append((s, s + len(b), "helpers", n, b))

spans.sort(key=lambda t: -t[0])
helpers_body = []
for s, e, dest, n, b in spans:
    text = text[:s] + text[e:]
    helpers_body.append((n, b))

# Write helpers module.
header = '''"""evidence_generator_helpers.py - helpers extracted during 4.8.0 split.

Auto-generated. Public entry points stay in evidence_generator.py:
    - _generate_bundle_with_manager
    - _run_simulated_bundle
    - _run_live_bundle
    - generate_bundle
"""

from __future__ import annotations
import json as _json
import os as _os
import shutil as _shutil
from datetime import datetime as _datetime, timezone as _timezone
from pathlib import Path as _Path
from typing import Any as _Any

'''
helpers_text = header
for n, b in helpers_body:
    helpers_text += b + "\n\n"
(P.parent / "evidence_generator_helpers.py").write_text(helpers_text, encoding="utf-8")
print(f"wrote: evidence_generator_helpers.py")

# Update evidence_generator.py with re-exports header.
inject = '''"""evidence_generator.py - thin facade.

Helpers live in evidence_generator_helpers.py.
Orchestrators (_generate_bundle_with_manager, _run_simulated_bundle,
_run_live_bundle, generate_bundle) stay here.
"""

from evidence_generator_helpers import (  # noqa: F401
'''
for n in to_helpers:
    fn_name = n.lstrip("_")
    inject += f"    {n},\n"
inject += ")\n\n"

# Strip shebang + first docstring.
text = re.sub(r"^#!.*\n", "", text)
text = re.sub(r'^""".*?"""\n', "", text, count=1, flags=re.DOTALL)
text = inject + text.lstrip()
P.write_text(text, encoding="utf-8")
print(f"trimmed: {P.name}")