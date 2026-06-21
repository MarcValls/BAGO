"""Tests for the BAGO Code Forge 3B execution subpackage."""
from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from bago_core.codegen.patch_parser import parse_patch
from bago_core.execution.atomic_patch import (
    DEFAULT_FORBIDDEN_PATHS,
    PATCH_APPLY_IO_ERROR,
    PATCH_BINARY_FILE,
    PATCH_FORBIDDEN_PATH,
    PATCH_OK,
    PATCH_PATH_OUTSIDE_WORKSPACE,
    PatchApplyError,
    apply_patch_atomically,
    rollback_patch,
)
from bago_core.execution.process_runner import (
    ProcessOutcome,
    ProcessRunner,
    RC_SPAWN_FAILED,
    RC_TIMED_OUT,
    SubprocessProcessRunner,
)
from bago_core.execution.staging_workspace import (
    STAGING_FORBIDDEN,
    StagingError,
    StagingWorkspace,
    open_staging_workspace,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class _FakeRunner(ProcessRunner):
    """Minimal fake that records every command and returns scripted outcomes."""

    def __init__(self, outcomes: dict[str, ProcessOutcome] | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self._outcomes = outcomes or {}

    def run(self, command, *, stdin="", cwd=None, timeout_seconds=120, env=None):
        self.calls.append({
            "command": command,
            "stdin": stdin,
            "cwd": cwd,
            "timeout_seconds": timeout_seconds,
            "env": dict(env) if env else None,
        })
        if command in self._outcomes:
            return self._outcomes[command]
        return ProcessOutcome(
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=1,
            command_id=command,
        )


def _make_patch(new_path: str, old_body: str, new_body: str) -> Patch:
    """Build a single-hunk patch between two bodies."""
    # Build the diff text in a parse-friendly form. ``textwrap.dedent``
    # on a multi-line string built with concatenation is fragile, so we
    # use explicit line joining.
    old_lines = old_body.splitlines() if old_body else [""]
    new_lines = new_body.splitlines() if new_body else [""]
    diff = (
        f"--- a/{new_path}\n"
        f"+++ b/{new_path}\n"
        f"@@ -1,{len(old_lines)} +1,{len(new_lines)} @@\n"
        + "".join(f"-{line}\n" for line in old_lines)
        + "".join(f"+{line}\n" for line in new_lines)
    )
    return parse_patch(diff)


def _make_workspace(tmp: Path) -> Path:
    """Create a tiny project with a couple of files plus some ignored dirs."""
    workspace = tmp / "ws"
    workspace.mkdir()
    (workspace / "src").mkdir()
    (workspace / "src" / "a.py").write_text("a = 1\n", encoding="utf-8")
    (workspace / "tests").mkdir()
    (workspace / "tests" / "test_a.py").write_text("def test_a(): assert True\n", encoding="utf-8")
    (workspace / ".bago").mkdir()
    (workspace / ".bago" / "session.sqlite").write_text("x", encoding="utf-8")
    (workspace / "__pycache__").mkdir()
    (workspace / "__pycache__" / "junk.pyc").write_text("junk", encoding="utf-8")
    (workspace / ".env").write_text("SECRET=1", encoding="utf-8")
    return workspace


# ---------------------------------------------------------------------------
# process_runner
# ---------------------------------------------------------------------------


class SubprocessProcessRunnerTests(unittest.TestCase):
    def test_runs_simple_command(self) -> None:
        runner = SubprocessProcessRunner()
        outcome = runner.run(
            'python -c "import sys; sys.stdout.write(\'hi\')"',
            timeout_seconds=10,
        )
        self.assertEqual(outcome.returncode, 0)
        self.assertIn("hi", outcome.stdout)
        self.assertFalse(outcome.timed_out)

    def test_reports_missing_binary(self) -> None:
        runner = SubprocessProcessRunner()
        outcome = runner.run(
            "definitely_not_a_real_binary_xyz",
            timeout_seconds=10,
        )
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.returncode, RC_SPAWN_FAILED)
        self.assertIn("binary not found", outcome.stderr)

    def test_reports_non_zero_exit(self) -> None:
        runner = SubprocessProcessRunner()
        outcome = runner.run(
            'python -c "import sys; sys.exit(2)"',
            timeout_seconds=10,
        )
        self.assertEqual(outcome.returncode, 2)
        self.assertFalse(outcome.ok)

    def test_timeout_zero_is_normalised(self) -> None:
        runner = SubprocessProcessRunner(default_timeout_seconds=0)
        outcome = runner.run(
            "python -c \"print('still ok')\"",
            timeout_seconds=5,
        )
        self.assertEqual(outcome.returncode, 0)

    def test_empty_command_returns_never_started(self) -> None:
        runner = SubprocessProcessRunner()
        outcome = runner.run("")
        self.assertEqual(outcome.returncode, -1)
        self.assertFalse(outcome.ok)


# ---------------------------------------------------------------------------
# staging_workspace
# ---------------------------------------------------------------------------


class StagingWorkspaceTests(unittest.TestCase):
    def test_copies_project_minuses_ignored_dirs(self) -> None:
        tmp = Path(tempfile_mkdtemp())
        try:
            workspace = _make_workspace(tmp)
            staging = open_staging_workspace(workspace)
            self.assertNotEqual(staging.root, str(workspace))
            self.assertTrue(Path(staging.root, "src", "a.py").is_file())
            self.assertTrue(Path(staging.root, "tests", "test_a.py").is_file())
            # Ignored entries must not be copied.
            self.assertFalse(Path(staging.root, ".bago").exists())
            self.assertFalse(Path(staging.root, "__pycache__").exists())
            self.assertFalse(Path(staging.root, ".env").exists())
            staging.close()
            self.assertFalse(Path(staging.root).exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_resolve_blocks_path_escape(self) -> None:
        tmp = Path(tempfile_mkdtemp())
        try:
            workspace = _make_workspace(tmp)
            staging = open_staging_workspace(workspace)
            try:
                with self.assertRaises(StagingError) as ctx:
                    staging.resolve("../outside.txt")
                self.assertEqual(ctx.exception.code, STAGING_FORBIDDEN)
            finally:
                staging.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_read_text_returns_empty_on_missing(self) -> None:
        tmp = Path(tempfile_mkdtemp())
        try:
            workspace = _make_workspace(tmp)
            staging = open_staging_workspace(workspace)
            try:
                self.assertEqual(staging.read_text("does/not/exist.py"), "")
                self.assertEqual(staging.read_text("src/a.py"), "a = 1\n")
            finally:
                staging.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_context_manager_cleans_up(self) -> None:
        tmp = Path(tempfile_mkdtemp())
        try:
            workspace = _make_workspace(tmp)
            with open_staging_workspace(workspace) as staging:
                self.assertTrue(Path(staging.root).is_dir())
            self.assertFalse(Path(staging.root).exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_snapshot_lists_copied_paths(self) -> None:
        tmp = Path(tempfile_mkdtemp())
        try:
            workspace = _make_workspace(tmp)
            staging = open_staging_workspace(workspace)
            try:
                copied = set(staging.snapshot.copied_paths)
                self.assertIn("src/a.py", copied)
                self.assertIn("tests/test_a.py", copied)
            finally:
                staging.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def tempfile_mkdtemp() -> str:
    import tempfile
    return tempfile.mkdtemp(prefix="bago_exec_test_")


# ---------------------------------------------------------------------------
# atomic_patch
# ---------------------------------------------------------------------------


class AtomicPatchTests(unittest.TestCase):
    def test_apply_modifies_file_and_returns_hashes(self) -> None:
        tmp = Path(tempfile_mkdtemp())
        try:
            workspace = _make_workspace(tmp)
            old_body = (workspace / "src" / "a.py").read_text(encoding="utf-8")
            patch = _make_patch("src/a.py", old_body, "a = 2\n")
            result = apply_patch_atomically(
                [patch],
                workspace_root=workspace,
                keep_snapshot=False,
            )
            self.assertEqual(result.status, PATCH_OK)
            self.assertEqual(len(result.applied), 1)
            self.assertEqual(result.applied[0].path, "src/a.py")
            # The hash_before is empty because the pre-image is a
            # newline; the SHA-256 of "" is well-known and stable.
            self.assertNotEqual(result.applied[0].hash_after, "")
            self.assertEqual((workspace / "src" / "a.py").read_text(encoding="utf-8"), "a = 2\n")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_apply_refuses_forbidden_path(self) -> None:
        tmp = Path(tempfile_mkdtemp())
        try:
            workspace = _make_workspace(tmp)
            patch = _make_patch(".env", "SECRET=1", "SECRET=2")
            result = apply_patch_atomically(
                [patch], workspace_root=workspace, keep_snapshot=False,
            )
            self.assertEqual(result.status, "failed")
            self.assertEqual(result.error_code, PATCH_FORBIDDEN_PATH)
            self.assertEqual((workspace / ".env").read_text(encoding="utf-8"), "SECRET=1")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_apply_refuses_path_escape(self) -> None:
        tmp = Path(tempfile_mkdtemp())
        try:
            workspace = _make_workspace(tmp)
            patch = _make_patch("../outside.py", "", "x = 1\n")
            result = apply_patch_atomically(
                [patch], workspace_root=workspace, keep_snapshot=False,
            )
            self.assertEqual(result.status, "failed")
            self.assertEqual(result.error_code, PATCH_PATH_OUTSIDE_WORKSPACE)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_apply_rolls_back_on_failure(self) -> None:
        tmp = Path(tempfile_mkdtemp())
        try:
            workspace = _make_workspace(tmp)
            old_body = (workspace / "src" / "a.py").read_text(encoding="utf-8")
            good_patch = _make_patch("src/a.py", old_body, "a = 2\n")
            # Patch whose ``new_body`` deliberately does not match the
            # source context, so the in-memory applier raises
            # ``apply_io_error`` and the apply rolls back.
            bad_patch = _make_patch(
                "tests/test_a.py",
                "def test_a(): assert True\n",
                "def test_a(): assert False\n",
            )
            # Mutate the file so the in-memory check fails.
            (workspace / "tests" / "test_a.py").write_text(
                "# completely different content\nx = 99\n",
                encoding="utf-8",
            )
            result = apply_patch_atomically(
                [good_patch, bad_patch],
                workspace_root=workspace,
                keep_snapshot=False,
            )
            self.assertEqual(result.status, "failed")
            self.assertEqual(result.error_code, PATCH_APPLY_IO_ERROR)
            # Rollback must restore the original file.
            self.assertEqual(
                (workspace / "src" / "a.py").read_text(encoding="utf-8"),
                old_body,
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_apply_returns_failed_result_for_forbidden_path(self) -> None:
        tmp = Path(tempfile_mkdtemp())
        try:
            workspace = _make_workspace(tmp)
            patch = _make_patch(".bago/session.sqlite", "x", "y")
            result = apply_patch_atomically(
                [patch], workspace_root=workspace, keep_snapshot=False,
            )
            self.assertEqual(result.status, "failed")
            self.assertEqual(result.error_code, PATCH_FORBIDDEN_PATH)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_rollback_restores_snapshot(self) -> None:
        tmp = Path(tempfile_mkdtemp())
        try:
            workspace = _make_workspace(tmp)
            old_body = (workspace / "src" / "a.py").read_text(encoding="utf-8")
            patch = _make_patch("src/a.py", old_body, "a = 99\n")
            result = apply_patch_atomically(
                [patch], workspace_root=workspace, keep_snapshot=True,
            )
            self.assertEqual(result.status, PATCH_OK)
            self.assertEqual((workspace / "src" / "a.py").read_text(encoding="utf-8"), "a = 99\n")
            self.assertTrue(Path(result.rollback_snapshot).is_dir())
            rollback_patch(result.rollback_snapshot, workspace)
            self.assertEqual((workspace / "src" / "a.py").read_text(encoding="utf-8"), old_body)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_default_forbidden_paths_match_compiler(self) -> None:
        # Sanity check: the execution layer must refuse the same set
        # of paths the compiler refuses.
        for path in (".bago", ".env", ".git", "state", "dist"):
            self.assertIn(path, DEFAULT_FORBIDDEN_PATHS)


if __name__ == "__main__":
    unittest.main()