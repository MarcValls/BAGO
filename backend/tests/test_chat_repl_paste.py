from __future__ import annotations

import tempfile
import unittest

import repl as repl_module  # noqa: E402
from repl import BagoREPL  # noqa: E402


class ChatReplPasteTests(unittest.TestCase):
    def test_pasted_block_is_sent_once(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repl = BagoREPL(base_path=td)
            seen: list[str] = []
            repl._handle_chat = lambda text: seen.append(text)  # type: ignore[method-assign]
            repl._print_status = lambda: None  # type: ignore[method-assign]
            original_print_message = repl_module.R.print_message
            repl_module.R.print_message = lambda *args, **kwargs: None  # type: ignore[assignment]
            try:
                handled = repl._handle_pasted_block("line1\nline2\n")
            finally:
                repl_module.R.print_message = original_print_message  # type: ignore[assignment]
                repl.mgr.close()

            self.assertTrue(handled)
            self.assertEqual(seen, ["line1\nline2"])


if __name__ == "__main__":
    unittest.main()
