"""Print line counts of all key BAGO files."""
import pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent
files = [
    "bago_core/launcher.py",
    "bago_core/node_control.py",
    "bago_core/node_control_cli.py",
    "bago_core/node_control_render.py",
    "bago_core/node_control_ssot.py",
    "bago_core/node_control_store.py",
    "bago_core/node_control_policy.py",
    "bago_core/node_control_tui.py",
    "bago_core/node_control_translator.py",
    "bago_core/parsers.py",
    "bago_core/parsers_sections.py",
    "bago_core/evidence_bundle.py",
    "bago_core/cli_installs.py",
    "tools/check_modular.py",
    "tools/inspect_encoding.py",
    "tools/normalize_encoding.py",
]
for rel in files:
    p = REPO / rel
    if p.exists():
        n = len(p.read_text(encoding="utf-8").splitlines())
        print(f"{p.name:42s} {n:5d} lines")
    else:
        print(f"{p.name:42s}  MISSING")
