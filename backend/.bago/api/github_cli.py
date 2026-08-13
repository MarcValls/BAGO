"""Testable adapter around the external GitHub CLI process."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class GitHubCliResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class GitHubCliAdapter:
    def __init__(self, executable: str = "gh", timeout_seconds: float = 30.0) -> None:
        self.executable = executable
        self.timeout_seconds = timeout_seconds

    def run(self, args: Sequence[str]) -> GitHubCliResult:
        try:
            process = subprocess.run(
                [self.executable, *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
                shell=False,
                check=False,
            )
            return GitHubCliResult(
                process.returncode,
                process.stdout.strip(),
                process.stderr.strip(),
            )
        except FileNotFoundError:
            return GitHubCliResult(127, stderr="gh no está instalado")
        except subprocess.TimeoutExpired:
            return GitHubCliResult(124, stderr="GitHub tardó demasiado en responder")


DEFAULT_GITHUB_CLI = GitHubCliAdapter()
