#!/usr/bin/env python3
"""bago_core/node_control.py -- thin facade for the Node Control registry.

The runtime logic has been split into sub-facades, each owning one axis of
the registry (R7 says dispatch files are named by domain):

  - :mod:`bago_core.node_control_state`     -- load/persist, bootstrap,
    state-level helpers (find_installation, find_piece, find_connector,
    refresh_compatibility, validate, status, list_pieces, list_connectors,
    matrix, run_modular_guard)
  - :mod:`bago_core.node_control_connect`   -- connect / disconnect / set_mode
    / export_bundle (the live side-effects and per-action evidence)

The :mod:`bago_core.node_control_cli` argparse file consumes the public
API exposed here. The :mod:`bago_core.node_control_translator` module
delegates translator-specific work and is also reachable via
``bago node translator ...``.

R0-R10:
- R0: <250 lines
- R1: facade only -- this file no longer owns business logic, it only
  re-exports the sub-facades and convenience helpers
"""
from __future__ import annotations

import sys
from pathlib import Path

BAGO_ROOT = Path(__file__).resolve().parents[1]

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bago_core.node_control_ssot import ALLOWED_MODES, CLI_MODES
from bago_core.node_control_render import (
    render_connectors as _render_connectors_mod,
    render_matrix as _render_matrix_mod,
    render_pieces as _render_pieces_mod,
    render_text as _render_text_mod,
)
from bago_core.node_control_tui import interactive_tui as _interactive_tui_mod

# Re-export the store dataclass + helpers used by the CLI directly.
from bago_core.node_control_store import (
    RegistryPaths,
    derive_profile,
    discover_installations,
    fallback_installation,
    installation_id,
    json_read as _json_read,
    json_write as _json_write,
    jsonl_append as _jsonl_append,
    load_default_piece_catalog,
    materialize_piece_store,
    piece_manifest,
    piece_store_dirs as _piece_store_dirs,
    piece_store_root as _piece_store_root,
    record_evidence as _record_evidence,
    registry_paths as _registry_paths,
    slug as _slug,
    now as _now,
)

# Re-export the policy helpers (R1 says store reads policy, never the reverse).
from bago_core.node_control_policy import (
    build_compatibility as _build_compatibility,
    build_connectors as _build_connectors,
    connector_id as _connector_id,
    find_connector as _find_connector,
    find_installation as _find_installation,
    find_piece as _find_piece,
    is_valid_mode,
    normalize_mode as _normalize_mode,
    policy_for as _policy_for,
)

# Re-export the state-level orchestrator (load/persist/refresh).
from bago_core.node_control_state import (
    bootstrap,
    refresh_compatibility as _refresh_compatibility,
    status,
    list_pieces,
    list_connectors,
    matrix,
    evidence_tail,
    preview_mutation,
    validate,
)

# Re-export the connect/disconnect sub-facade.
from bago_core.node_control_connect import (
    connect,
    disconnect,
    set_mode,
    export_bundle,
)


# ----------------------------------------------------------------------------
# ``main`` lives in the CLI module; the legacy facade exposed it as a thin
# delegate. We restore the shim here so callers (and the launcher) can keep
# invoking ``bago_core.node_control.main(argv)`` exactly as before (R9).
# ----------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    from bago_core import node_control_cli as _cli
    return _cli.main(argv)


# ----------------------------------------------------------------------------
# Legacy aliases kept for backwards compatibility (R9). The old monolithic
# facade exposed these module-level helpers which the rest of the codebase
# imported as ``nc.<name>``. They now live in the state/connect sub-facades
# but are re-exported here under their old names.
# ----------------------------------------------------------------------------
def _load_state(base_path):  # pragma: no cover - alias
    from bago_core.node_control_state import _load_state as _impl
    return _impl(base_path)


def _persist_state(paths, state):  # pragma: no cover - alias
    from bago_core.node_control_state import _persist_state as _impl
    return _impl(paths, state)


def _run_modular_guard():  # pragma: no cover - alias
    from bago_core.node_control_state import run_modular_guard as _impl
    return _impl()


def _run_tests() -> int:  # pragma: no cover - smoke alias
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        status_payload = status(td)
        assert status_payload["installations"] >= 1
        pieces_payload = list_pieces(td)
        assert pieces_payload["count"] >= 1
        connectors_payload = list_connectors(td)
        assert connectors_payload["count"] >= 1
        matrix_payload = matrix(td)
        assert matrix_payload["rows"]
        ok, payload = validate(td)
        assert ok is True
        assert payload["failures"] == 0
        export_path = export_bundle(td)
        assert export_path.exists()
        assert _render_text_mod(status(td)).startswith("BAGO NODE CONTROL")
        assert "BAGO PIECES" in _render_pieces_mod(list_pieces(td))
        assert "BAGO CONNECTORS" in _render_connectors_mod(list_connectors(td))
        print("node_control.py --test: ALL PASS")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys as _sys
    if "--test" in _sys.argv:
        raise SystemExit(_run_tests())
    raise SystemExit(main())
