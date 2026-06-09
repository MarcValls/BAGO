#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        venv_dir = Path(td) / "clean-install"
        builder = venv.EnvBuilder(with_pip=True, clear=True)
        builder.create(venv_dir)
        py = _venv_python(venv_dir)
        env = os.environ.copy()
        env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
        env["PIP_NO_INPUT"] = "1"

        subprocess.run([str(py), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], check=True, cwd=ROOT, env=env)
        subprocess.run([str(py), "-m", "pip", "install", "-r", "requirements.txt"], check=True, cwd=ROOT, env=env)
        subprocess.run([str(py), "-c", "import pypdf, numpy, playwright; print('clean-install imports ok')"], check=True, cwd=ROOT, env=env)

    print("clean_install_smoke.py: ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
