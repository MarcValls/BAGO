"""Guardrails para bago.constants.

Estos tests evitan que la ruta de usuario vuelva a bifurcarse entre
constants.py y launcher.py, y verifican que la resolución respeta el entorno.
"""
from __future__ import annotations

import importlib
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import bago.constants as constants


def test_default_user_bago_is_single_source_of_truth():
    """La ruta por defecto debe vivir en constants.py y apuntar al repo user/."""
    assert constants.DEFAULT_USER_BAGO == constants.BAGO_DIR / "user"


def test_resolve_user_bago_prefers_env_and_creates_state_dir(monkeypatch):
    """Si BAGO_USER_HOME está definido, _resolve_user_bago debe respetarlo."""
    with tempfile.TemporaryDirectory() as tmp:
        custom = Path(tmp) / "bago-user"
        monkeypatch.setenv("BAGO_USER_HOME", str(custom))
        monkeypatch.delenv("BAGO_USER_DIR", raising=False)

        module = importlib.reload(constants)
        resolved = module._resolve_user_bago()

        assert resolved == custom.resolve()
        assert (resolved / "state").is_dir()
        assert module.USER_BAGO == resolved


def test_launcher_consumes_default_from_constants():
    """launcher.py no debe definir una segunda ruta por su cuenta."""
    launcher_path = Path(__file__).resolve().parents[3] / "bago_core" / "launcher.py"
    text = launcher_path.read_text(encoding="utf-8")

    assert "from bago.constants import DEFAULT_USER_BAGO" in text
    assert "def _default_user_home" not in text
    assert 'BAGO_ROOT / "user"' not in text

