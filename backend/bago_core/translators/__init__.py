"""BAGO translator layer -- BAGO IR <-> provider-specific model dialects.

Translator pieces live in C:\\ProgramData\\BAGO\\pieces\\translators\\<family>\\<model>\\
and each piece exposes:

- manifest.json: piece metadata (model_family, model_id, supports, safety, evidence)
- encode.py:     BAGO IR -> provider request payload
- decode.py:     provider response -> BAGO IR
- shared/base:   the IR types (ir_types.py) and TranslatorV1 protocol (protocol.py)

This package is the thin wrapper that:
- Bootstraps shared/base onto sys.path so each piece can import it.
- Discovers all installed pieces (registry.discover_translators()).
- Exposes a smoke-test that round-trips an IR conversation through
  encode->decode for each piece, so the test suite can prove pieces
  preserve the IR without needing network access.
"""
from .bootstrap import (
    list_translators,
    get_translator,
    smoke_test_piece,
    smoke_test_all,
    bootstrap_path,
    _ensure_ir_types_path,
)

__all__ = [
    "list_translators",
    "get_translator",
    "smoke_test_piece",
    "smoke_test_all",
    "bootstrap_path",
    "_ensure_ir_types_path",
]
