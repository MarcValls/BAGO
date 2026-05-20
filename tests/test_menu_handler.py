"""test_menu_handler.py — Tests para el handler ! del menu Sistema BAGO"""

import os
import sys
from pathlib import Path

# Resolve BAGO root from env or cwd
BAGO_ROOT = Path(os.environ.get("BAGO_ROOT", Path.cwd())).resolve()


def test_bang_handler_exists():
    """Verifica que cmd.py tiene handler para comandos con !."""
    cmd_path = BAGO_ROOT / ".bago" / "tools" / "bago" / "cmd.py"
    if not cmd_path.exists():
        cmd_path = Path.cwd() / ".bago" / "tools" / "bago" / "cmd.py"
    assert cmd_path.exists(), f"cmd.py not found at {cmd_path}"
    content = cmd_path.read_text(encoding="utf-8")
    assert "elif v.startswith" in content and "!" in content
    assert "subprocess.run" in content
    assert "git-dirty" in content
    assert "git dirty" in content


def test_menu_has_bang_entries():
    """Verifica que el menu principal tiene entradas con !."""
    menu_path = BAGO_ROOT / ".bago" / "tools" / "bago" / "menus" / "main_menu.py"
    if not menu_path.exists():
        menu_path = Path.cwd() / ".bago" / "tools" / "bago" / "menus" / "main_menu.py"
    assert menu_path.exists()
    content = menu_path.read_text(encoding="utf-8")
    assert "!validate" in content
    assert "!health" in content
    assert "!git-dirty" in content
    assert "!prompt-router" in content


def test_launcher_has_bang_commands():
    """Verifica que el launcher reconoce los comandos del menu !."""
    launcher = BAGO_ROOT / "bago_core" / "launcher.py"
    if not launcher.exists():
        launcher = Path.cwd() / "bago_core" / "launcher.py"
    assert launcher.exists()
    content = launcher.read_text(encoding="utf-8")
    cmds = ["validate", "health", "audit", "version", "autonomous", "git-dirty",
            "test", "encoding", "census", "map", "prompt-router", "role-spiral",
            "model-gate", "token-analytics", "api-only"]
    missing = []
    for c in cmds:
        if f'elif cmd == "{c}"' not in content:
            missing.append(c)
    assert not missing, f"Missing commands in launcher: {missing}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
