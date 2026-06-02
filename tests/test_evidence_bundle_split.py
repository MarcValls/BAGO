#!/usr/bin/env python3
"""FASE 9 tests: evidence_bundle was split into model/generator/cli in FASE 6.3
and the generator's _generate_bundle_with_manager was further decomposed in
FASE 9. These tests pin the R0/R1/R4 modular rules.
"""
from __future__ import annotations

import ast
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import bago_core.evidence_bundle as bundle
import bago_core.evidence_cli as cli
import bago_core.evidence_generator as generator
import bago_core.evidence_model as model


REPO_ROOT = Path(__file__).resolve().parents[1]


class TestEvidenceFacades(unittest.TestCase):
    def test_facade_is_thin(self):
        """evidence_bundle.py is a pure re-export shim (R0, R1)."""
        src = (REPO_ROOT / "bago_core" / "evidence_bundle.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(src)
        funcdefs = [
            n for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        # The facade must not define any new business logic.
        self.assertEqual(
            funcdefs, [],
            f"facade defines functions: {[f.name for f in funcdefs]}",
        )
        # Must re-export the public API.
        for name in (
            "ContractMockAdapter",
            "ObjectiveProfile",
            "PROFILES",
            "generate_bundle",
            "build_parser",
            "main",
            "run",
        ):
            self.assertIn(name, src)

    def test_model_no_io(self):
        """evidence_model has no filesystem / HTTP / subprocess calls (R0)."""
        src = (REPO_ROOT / "bago_core" / "evidence_model.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(src)
        forbidden = ("open", "subprocess", "urllib", "httpx", "requests")
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                fn = ast.unparse(n.func) if hasattr(ast, "unparse") else ""
                for token in forbidden:
                    self.assertNotIn(token, fn, f"forbidden call: {fn}")
        # And no `print()` (R8).
        for n in ast.walk(tree):
            self.assertFalse(
                isinstance(n, ast.Call) and ast.unparse(n.func) == "print",
                "model layer must not print",
            )

    def test_io_layer_size(self):
        """FASE 9.2: evidence_io.py is the file-IO layer (R0, R1)."""
        io_path = REPO_ROOT / "bago_core" / "evidence_io.py"
        self.assertTrue(io_path.exists())
        lines = io_path.read_text(encoding="utf-8").splitlines()
        self.assertLess(
            len(lines), 250,
            f"evidence_io.py has {len(lines)} lines; R0 wants < 250",
        )
        # No high-level imports of model/cli/manager (R1).
        src = io_path.read_text(encoding="utf-8")
        for forbidden in (
            "from bago_core.evidence_model",
            "from bago_core.evidence_cli",
            "from bago_core.evidence_generator",
            "from session_manager",
            "from switch_engine",
        ):
            self.assertNotIn(forbidden, src, f"io imports {forbidden}")

    def test_generator_orchestrator_size(self):
        """FASE 9.2: evidence_generator.py is the orchestrator (R0)."""
        gen_path = REPO_ROOT / "bago_core" / "evidence_generator.py"
        lines = gen_path.read_text(encoding="utf-8").splitlines()
        # R3 objective: < 500. Hard limit 600.
        self.assertLess(
            len(lines), 600,
            f"evidence_generator.py has {len(lines)} lines; R3 hard limit 600",
        )

    def test_generator_io_uses_evidence_io(self):
        """FASE 9.2: generator delegates IO to evidence_io (R1, R5)."""
        src = (REPO_ROOT / "bago_core" / "evidence_generator.py").read_text(
            encoding="utf-8"
        )
        # The old `_write_json`, `_write_text`, `_now_iso`, etc. are gone.
        for old in (
            "def _now_iso(",
            "def _write_json(",
            "def _write_text(",
            "def _sha256(",
            "def _copy_if_exists(",
            "def _prepare_output_dir(",
            "def _collect_file_digests(",
            "def _write_checksums(",
            "def _copy_session_artifacts(",
        ):
            self.assertNotIn(old, src, f"generator still defines {old}")
        # And the canonical helpers are imported.
        for new in (
            "from bago_core.evidence_io import",
            "write_json",
            "write_text",
            "now_iso",
            "collect_file_digests",
            "copy_session_artifacts",
            "write_checksums",
            "prepare_output_dir",
        ):
            self.assertIn(new, src, f"generator missing {new}")

    def test_cli_no_business_logic(self):
        """evidence_cli only wires argparse -> run() (R1 dispatch)."""
        src = (REPO_ROOT / "bago_core" / "evidence_cli.py").read_text(
            encoding="utf-8"
        )
        # Public entry points: build_parser, run, main, _run_tests
        tree = ast.parse(src)
        names = {
            n.name
            for n in tree.body
            if isinstance(n, ast.FunctionDef)
        }
        self.assertTrue(
            {"build_parser", "run", "main", "_run_tests"}.issubset(names),
            f"cli missing public names: {names}",
        )

    def test_generator_decomposed(self):
        """_generate_bundle_with_manager is a thin orchestrator (R3 <80)."""
        tree = ast.parse(
            (REPO_ROOT / "bago_core" / "evidence_generator.py").read_text(
                encoding="utf-8"
            )
        )
        for n in tree.body:
            if isinstance(n, ast.FunctionDef) and n.name == "_generate_bundle_with_manager":
                size = n.end_lineno - n.lineno + 1
                self.assertLess(
                    size, 80, f"_generate_bundle_with_manager = {size} lines",
                )

    def test_public_api_round_trip(self):
        """Facades still expose PROFILES, ObjectiveProfile, etc. (R9)."""
        self.assertEqual(set(model.PROFILES.keys()),
                         {"community-knowledge"})
        self.assertTrue(callable(bundle.generate_bundle))
        self.assertTrue(callable(bundle.main))
        self.assertTrue(callable(generator._generate_bundle_with_manager))


class TestEvidenceBundleSmoke(unittest.TestCase):
    def test_simulated_bundle_in_tempdir(self):
        """End-to-end smoke: simulated bundle writes manifest + report."""
        from bago_core.evidence_model import registered_mock_adapter

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bundle"
            with registered_mock_adapter():
                manifest_path = bundle.generate_bundle(
                    mode="simulated",
                    objective="community-knowledge",
                    output_dir=output,
                    provider="mock-contract",
                    model="mock-test",
                    base_path=Path(tmp),
                    overwrite=True,
                )
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "pass")
            self.assertTrue((output / "report.md").exists())
            self.assertTrue((output / "assistant_response.txt").exists())


if __name__ == "__main__":
    unittest.main()
