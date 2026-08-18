"""Tests for the BAGO Code Forge 3B patch parser."""
from __future__ import annotations

import json
import textwrap
import unittest

from bago_core.codegen.patch_parser import (
    MAX_PATCH_BYTES,
    Hunk,
    Patch,
    PatchParseError,
    parse_patch,
)


SIMPLE_PATCH = textwrap.dedent(
    """\
    --- a/src/demo.py
    +++ b/src/demo.py
    @@ -1,2 +1,5 @@
     def greet(name: str) -> str:
         return f"hi {name}"
    +    if not name:
    +        raise ValueError("name required")
    +    return f"hi {name}"
    """
)


class PatchParserTests(unittest.TestCase):
    def test_parse_simple_patch(self) -> None:
        patch = parse_patch(SIMPLE_PATCH)
        self.assertIsInstance(patch, Patch)
        self.assertEqual(patch.old_path, "src/demo.py")
        self.assertEqual(patch.new_path, "src/demo.py")
        self.assertEqual(len(patch.hunks), 1)
        hunk = patch.hunks[0]
        self.assertEqual(hunk.old_start, 1)
        self.assertEqual(hunk.old_len, 2)
        self.assertEqual(hunk.new_start, 1)
        self.assertEqual(hunk.new_len, 5)
        self.assertEqual(hunk.additions(), 3)
        self.assertEqual(hunk.deletions(), 0)
        # JSON-safe
        json.dumps(patch.to_dict())

    def test_parse_rejects_mismatched_counts(self) -> None:
        bad = textwrap.dedent(
            """\
            --- a/x.py
            +++ b/x.py
            @@ -1,5 +1,2 @@
             a
            -b
             c
            """
        )
        with self.assertRaises(PatchParseError) as ctx:
            parse_patch(bad)
        self.assertEqual(ctx.exception.code, "hunk_line_count_mismatch")

    def test_parse_rejects_missing_headers(self) -> None:
        with self.assertRaises(PatchParseError) as ctx:
            parse_patch("@@ -1 +1 @@\n-x\n+y\n")
        self.assertEqual(ctx.exception.code, "missing_file_headers")

    def test_parse_rejects_different_paths(self) -> None:
        bad = textwrap.dedent(
            """\
            --- a/x.py
            +++ b/y.py
            @@ -1 +1 @@
            -a
            +b
            """
        )
        with self.assertRaises(PatchParseError) as ctx:
            parse_patch(bad)
        self.assertEqual(ctx.exception.code, "inconsistent_file_pair")

    def test_parse_rejects_oversized_patch(self) -> None:
        # Cheap blow-up: a single line of " " repeated past the cap.
        huge = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n" + (" " * (MAX_PATCH_BYTES + 1))
        with self.assertRaises(PatchParseError) as ctx:
            parse_patch(huge)
        self.assertEqual(ctx.exception.code, "patch_too_large")

    def test_parse_rejects_unknown_marker(self) -> None:
        bad = textwrap.dedent(
            """\
            --- a/x.py
            +++ b/x.py
            @@ -1 +1 @@
            ~something
            """
        )
        with self.assertRaises(PatchParseError) as ctx:
            parse_patch(bad)
        self.assertEqual(ctx.exception.code, "unknown_hunk_line_prefix")

    def test_parse_supports_no_newline_marker(self) -> None:
        patch_text = (
            "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n\\ No newline at end of file\n"
        )
        patch = parse_patch(patch_text)
        self.assertEqual(len(patch.hunks), 1)
        self.assertEqual(patch.hunks[0].additions(), 1)
        self.assertEqual(patch.hunks[0].deletions(), 1)

    def test_parse_supports_multiple_hunks(self) -> None:
        multi = textwrap.dedent(
            """\
            --- a/x.py
            +++ b/x.py
            @@ -1,2 +1,3 @@
             a
            +a2
             b
            @@ -10,4 +11,4 @@
             j
            -k
            +K
             l
             m
            """
        )
        patch = parse_patch(multi)
        self.assertEqual(len(patch.hunks), 2)
        self.assertEqual(patch.hunks[0].new_start, 1)
        self.assertEqual(patch.hunks[1].old_start, 10)
        self.assertEqual(patch.hunks[0].old_len, 2)
        self.assertEqual(patch.hunks[0].new_len, 3)
        self.assertEqual(patch.hunks[1].old_len, 4)
        self.assertEqual(patch.hunks[1].new_len, 4)


if __name__ == "__main__":
    unittest.main()
