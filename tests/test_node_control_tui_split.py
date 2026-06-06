#!/usr/bin/env python3
"""FASE 10: TUI split tests (R10).

The interactive TUI is now split into 4 modules. These tests assert:
- The IO layer is small, no business logic, no Node Control imports.
- The info-layer dispatches read-only menus (1-5).
- The write-layer dispatches mutation menus (6-9) and exposes the
  selection helpers.
- The top-level dispatcher (`interactive_tui`) is thin and delegates
  to the two menu siblings.
"""
from __future__ import annotations

import ast
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]


def _lines(path: Path) -> int:
    return len(Path(path).read_text(encoding="utf-8").splitlines())


class TestTuiIo(unittest.TestCase):
    def test_io_layer_size(self):
        """FASE 10: node_control_tui_io.py is the small IO layer."""
        p = REPO_ROOT / "bago_core" / "node_control_tui_io.py"
        self.assertLess(_lines(p), 120)

    def test_io_layer_no_business_logic(self):
        """The IO layer must not import the state or connect modules."""
        src = (REPO_ROOT / "bago_core" / "node_control_tui_io.py").read_text(
            encoding="utf-8"
        )
        for forbidden in (
            "from bago_core.node_control_state",
            "from bago_core.node_control_connect",
            "from bago_core.node_control",
        ):
            self.assertNotIn(forbidden, src)

    def test_pause_reads_eof_silently(self):
        from bago_core.node_control_tui_io import _pause
        with mock.patch("builtins.input", side_effect=EOFError):
            _pause()  # must not raise


class TestTuiInfo(unittest.TestCase):
    def test_info_layer_size(self):
        p = REPO_ROOT / "bago_core" / "node_control_tui_info.py"
        self.assertLess(_lines(p), 150)

    def test_run_info_menus_dispatches(self):
        """Each of 1..5 is handled, 6..9 are not."""
        from bago_core.node_control_tui_info import _run_info_menus
        import bago_core.node_control_tui_io as tui_io

        full_summary = {
            "base_path": "/tmp", "store_root": "/x",
            "installations": 0, "pieces": 0, "connectors": 0,
            "compatibility_rows": 0, "evidence_file": "/x/ev",
            "modes": {},
        }

        handled = []
        for choice in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "x"):
            with mock.patch("builtins.print"), \
                 mock.patch("builtins.input", return_value=""), \
                 mock.patch.object(tui_io, "_pause", return_value=None):
                api = {
                    "list_pieces": lambda *a, **kw: {"count": 0, "pieces": []},
                    "list_connectors": lambda *a, **kw: {"count": 0, "connectors": []},
                    "matrix": lambda *a, **kw: {"installations": [], "rows": []},
                    "validate": lambda *a, **kw: (True, {"checks": []}),
                }
                ok = _run_info_menus(
                    choice=choice, base_path=Path("/tmp"),
                    summary=full_summary, api=api,
                )
                handled.append((choice, ok))

        # 1-5 are handled, 6-9 and 'x' are not.
        expected = {
            "1": True, "2": True, "3": True, "4": True, "5": True,
            "6": False, "7": False, "8": False, "9": False, "x": False,
        }
        for choice, ok in handled:
            self.assertEqual(ok, expected[choice], f"choice={choice} got {ok}")


class TestTuiWrite(unittest.TestCase):
    def test_write_layer_size(self):
        p = REPO_ROOT / "bago_core" / "node_control_tui_write.py"
        self.assertLess(_lines(p), 250)

    def test_run_write_menus_dispatches(self):
        from bago_core.node_control_tui_write import _run_write_menus
        import bago_core.node_control_tui_write as tui_write

        summary = {
            "installations_data": [
                {"installation_id": "i1", "path": "/x", "version": "1", "profile": "p"}
            ],
            "pieces_data": [
                {"piece_id": "p1", "type": "translator", "scope": "core", "version": "1"}
            ],
        }
        api = {
            "export_bundle": mock.Mock(return_value=Path("/tmp/out.json")),
            "connect": mock.Mock(return_value={"ok": True}),
            "disconnect": mock.Mock(return_value={"ok": True}),
            "set_mode": mock.Mock(return_value={"ok": True}),
        }

        with mock.patch("builtins.print"), \
             mock.patch("builtins.input", return_value=""), \
             mock.patch.object(tui_write, "_pause", return_value=None), \
             mock.patch.object(tui_write, "_prompt_text", return_value="out.json"), \
             mock.patch.object(tui_write, "_prompt_choice", return_value=0):
            for choice in ("1", "2", "3", "4", "5", "x"):
                ok = _run_write_menus(
                    choice=choice, base_path=Path("/tmp"),
                    summary=summary, api=api,
                )
                self.assertFalse(ok, f"choice={choice} should be info-side")
            for choice in ("6", "7", "8", "9"):
                ok = _run_write_menus(
                    choice=choice, base_path=Path("/tmp"),
                    summary=summary, api=api,
                )
                self.assertTrue(ok, f"choice={choice} should be write-side")
        self.assertTrue(api["export_bundle"].called)
        self.assertTrue(api["connect"].called)
        self.assertTrue(api["disconnect"].called)
        self.assertTrue(api["set_mode"].called)


class TestInteractiveTuiDispatcher(unittest.TestCase):
    def test_dispatcher_is_thin(self):
        """FASE 10: node_control_tui.interactive_tui delegates to the siblings."""
        p = REPO_ROOT / "bago_core" / "node_control_tui.py"
        self.assertLess(_lines(p), 120)
        src = p.read_text(encoding="utf-8")
        self.assertIn("from bago_core.node_control_tui_info import _run_info_menus", src)
        self.assertIn("from bago_core.node_control_tui_write import _run_write_menus", src)

    def test_non_tty_returns_zero(self):
        from bago_core.node_control_tui import interactive_tui
        fake_summary = {
            "base_path": "/tmp", "store_root": "/x",
            "installations": 0, "pieces": 0, "connectors": 0,
            "compatibility_rows": 0, "evidence_file": "/x/ev",
            "modes": {},
        }
        status_fn = mock.Mock(return_value=fake_summary)
        with mock.patch.object(sys.stdin, "isatty", return_value=False), \
             mock.patch("builtins.print"):
            rc = interactive_tui("/tmp", {"status": status_fn})
        self.assertEqual(rc, 0)
        status_fn.assert_called_once_with("/tmp")


if __name__ == "__main__":
    unittest.main()
