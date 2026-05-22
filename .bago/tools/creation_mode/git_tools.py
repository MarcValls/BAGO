"""creation_mode.git_tools — Git, preview de archivos y ejecución de comandos."""
from __future__ import annotations

import subprocess
from pathlib import Path

from .layers import matches_layer


def preview_file(path: str, max_lines: int = 40) -> list[str]:
    p = Path(path)
    if not p.exists() or p.is_dir():
        return ["  (no existe)"]
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        total = len(lines)
        out = [f"  {l.rstrip()}" for l in lines[:max_lines]]
        if total > max_lines:
            out.append(f"  ... ({total - max_lines} líneas más)")
        return out or ["  (vacío)"]
    except Exception as exc:
        return [f"  Error: {exc}"]


def run_command(cmd: list[str], cwd: str | None = None, timeout: int = 60) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout, encoding="utf-8", errors="replace")
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as exc:
        return -1, "", str(exc)


def git_status_lines(root: Path, layer: str = "") -> list[str]:
    try:
        proc = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True, text=True, cwd=str(root), encoding="utf-8", errors="replace", timeout=10
        )
        out = proc.stdout.strip()
        lines = out.splitlines() if out else []
        if not lines:
            return ["  Sin cambios"]
        if not layer or layer == "all":
            return lines
        filtered = [l for l in lines if matches_layer(l.split()[-1] if l.split() else l, layer)]
        return filtered or ["  Sin cambios en esta capa"]
    except Exception:
        return ["  (git no disponible)"]


def git_file_tree(root: Path, layer: str = "") -> list[str]:
    try:
        proc = subprocess.run(
            ["git", "ls-files"],
            capture_output=True, text=True, cwd=str(root), encoding="utf-8", errors="replace", timeout=10
        )
        out = proc.stdout.strip()
        lines = out.splitlines()
        if layer and layer != "all":
            lines = [l for l in lines if matches_layer(l, layer)]
        lines = lines[:30]
        return [f"  {l}" for l in lines] or ["  (vacío)"]
    except Exception:
        return ["  (git no disponible)"]
