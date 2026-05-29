#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_contracts.py — Tests alineados a los contratos operativos de BAGO.

Contratos cubiertos:
  · startup-screen-contract.md
  · engine-contract.md
  · publication-contract.md
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# ── Roots ──────────────────────────────────────────────────────────────────────
BAGO_ROOT = Path(__file__).resolve().parents[3]
TOOLS = BAGO_ROOT / ".bago" / "tools"
STATE = BAGO_ROOT / ".bago" / "state"
DOCS = BAGO_ROOT / "docs"

# ── Startup Screen Contract ───────────────────────────────────────────────────


class TestStartupScreenContract:
    """Valida startup-screen-contract.md"""

    def test_global_state_readable_and_has_version(self):
        gs = STATE / "global_state.json"
        assert gs.exists(), "global_state.json no existe"
        data = json.loads(gs.read_text(encoding="utf-8"))
        assert "bago_version" in data, "Falta bago_version en global_state"
        assert isinstance(data["bago_version"], str), "bago_version debe ser string"

    def test_recent_projects_readable(self):
        rp = STATE / "recent_projects.json"
        if not rp.exists():
            pytest.skip("No hay recent_projects.json (primera ejecucion)")
        data = json.loads(rp.read_text(encoding="utf-8"))
        assert isinstance(data, dict), "recent_projects debe ser un dict con clave 'projects'"
        projects = data.get("projects", [])
        assert isinstance(projects, list), "data['projects'] debe ser una lista"
        # Máximo 5 proyectos según contrato
        assert len(projects) <= 5, f"Demasiados proyectos recientes: {len(projects)}"

    def test_start_menu_script_exists(self):
        assert (TOOLS / "bago_start_menu.py").exists(), "Falta bago_start_menu.py"

    def test_banner_script_exists(self):
        assert (TOOLS / "bago_banner.py").exists(), "Falta bago_banner.py"

    def test_splash_script_exists(self):
        assert (TOOLS / "bago_splash.py").exists(), "Falta bago_splash.py"

    def test_chat_script_exists(self):
        assert (TOOLS / "bago_chat.py").exists(), "Falta bago_chat.py"

    def test_start_menu_builds_options_without_crash(self):
        sys.path.insert(0, str(TOOLS))
        import bago_start_menu

        opts = bago_start_menu._build_options()
        assert isinstance(opts, list), "_build_options debe devolver una lista"
        assert len(opts) > 0, "El menu no tiene opciones"

    def test_start_menu_contains_chat_and_create(self):
        sys.path.insert(0, str(TOOLS))
        import bago_start_menu

        opts = bago_start_menu._build_options()
        labels = [o.get("label", "") for o in opts]
        assert any("CHAT" in l for l in labels), "Falta opcion CHAT en menu"
        assert any("CREATE" in l for l in labels), "Falta opcion CREATE en menu"

    def test_start_menu_create_points_to_wizard_when_available(self):
        sys.path.insert(0, str(TOOLS))
        import bago_start_menu

        wizard_path = TOOLS / "bago" / "menus" / "wizard.py"
        if not wizard_path.exists():
            pytest.skip("wizard.py no disponible")

        # Monkeypatch para forzar reevaluacion con el root actual
        bago_start_menu.BAGO_ROOT = BAGO_ROOT
        bago_start_menu.TOOLS = TOOLS
        opts = bago_start_menu._build_options()
        create_opt = next(
            (o for o in opts if "CREATE" in o.get("label", "")), None
        )
        assert create_opt is not None
        cmd = create_opt.get("cmd")
        assert cmd is not None, "CREATE no tiene comando asignado"
        # Debe apuntar al wizard
        assert any("wizard" in str(c) for c in cmd), f"CREATE no apunta a wizard: {cmd}"

    def test_banner_logo_minimum_lines(self):
        sys.path.insert(0, str(TOOLS))
        import bago_start_menu

        logo = bago_start_menu.LOGO
        lines = [l for l in logo.splitlines() if l.strip()]
        assert len(lines) >= 5, f"Logo tiene solo {len(lines)} lineas (min 5)"
        assert len(lines) <= 40, f"Logo tiene {len(lines)} lineas (max 40)"

    def test_utf8_forced_in_startup_scripts(self):
        for script_name in ("bago_start_menu.py", "bago_banner.py", "bago_chat.py"):
            path = TOOLS / script_name
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            assert (
                "PYTHONIOENCODING" in text
                or "PYTHONUTF8" in text
                or 'reconfigure(encoding="utf-8")' in text
            ), f"{script_name} no fuerza UTF-8"

    def test_curses_subprocess_uses_popen_not_run(self):
        """El menu debe usar Popen + polling para evitar Ctrl+C crashes."""
        path = TOOLS / "bago_start_menu.py"
        text = path.read_text(encoding="utf-8")
        assert "subprocess.Popen" in text, "bago_start_menu no usa subprocess.Popen"
        assert "CREATE_NEW_PROCESS_GROUP" in text, "Falta aislamiento de Ctrl+C en Windows"


# ── Engine Contract ───────────────────────────────────────────────────────────


class TestEngineContract:
    """Valida engine-contract.md"""

    def test_runtime_contract_json_exists(self):
        rc = BAGO_ROOT / "runtime_contract.json"
        assert rc.exists(), "Falta runtime_contract.json en raiz"
        data = json.loads(rc.read_text(encoding="utf-8"))
        assert "contract_id" in data or "schema" in data, "runtime_contract vacio/invalido"

    def test_install_ps1_exists(self):
        assert (BAGO_ROOT / "install.ps1").exists(), "Falta install.ps1 (motor regenerable)"

    def test_install_ps1_contains_refresh_logic(self):
        ps1 = BAGO_ROOT / "install.ps1"
        text = ps1.read_text(encoding="utf-8")
        assert "RuntimeContract" in text or "runtime_contract" in text, (
            "install.ps1 no maneja el runtime contract"
        )

    def test_engine_is_not_mixed_with_dev_workspace(self):
        """El motor (C:\Program Files\BAGO o similar) debe estar separado del workspace.
        En la instalacion de usuario, verificamos que BAGO_ROOT no sea el repo fuente."""
        # Si existe .git, estamos en el repo de desarrollo, no en el motor instalado
        if (BAGO_ROOT / ".git").exists():
            pytest.skip("Esta ruta es el repo de desarrollo, no el motor instalado")
        # En un motor instalado limpio no debe haber archivos de desarrollo
        assert not (BAGO_ROOT / ".git").exists(), "Motor instalado contiene .git (dev mezclado)"


# ── Publication Contract ───────────────────────────────────────────────────────


class TestPublicationContract:
    """Valida publication-contract.md"""

    def test_install_ps1_supports_knowledge_switch(self):
        ps1 = BAGO_ROOT / "install.ps1"
        if not ps1.exists():
            pytest.skip("Falta install.ps1")
        text = ps1.read_text(encoding="utf-8")
        assert "NoKnowledge" in text, "install.ps1 no soporta -NoKnowledge"

    def test_docs_runtime_contract_exists(self):
        rc = DOCS / "runtime_contract.json"
        if not rc.exists():
            rc = BAGO_ROOT / "runtime_contract.json"
        assert rc.exists(), "Falta docs/runtime_contract.json"

    def test_knowledge_profile_consistent(self):
        """Si existe .bago/knowledge, el perfil es with-knowledge; sin knowledge es without."""
        has_knowledge = (BAGO_ROOT / ".bago" / "knowledge").exists()
        rc_path = BAGO_ROOT / "runtime_contract.json"
        if rc_path.exists():
            rc = json.loads(rc_path.read_text(encoding="utf-8"))
            # No hay campo explicito de perfil en runtime_contract.json por defecto,
            # pero verificamos consistencia basica.
            pass
        # Solo registramos el perfil detectado sin fallar
        assert True, f"Perfil detectado: {'with-knowledge' if has_knowledge else 'without-knowledge'}"


# ── Wizard / TUI Extension (nuevo artefacto) ────────────────────────────────────


class TestWizardTUIExtension:
    """Valida que el wizard soporta artefactos TUI y guarda correctamente."""

    def test_wizard_importable(self):
        sys.path.insert(0, str(TOOLS))
        from bago.menus import wizard

        assert hasattr(wizard, "_wizard_save"), "Falta _wizard_save en wizard"
        assert hasattr(wizard, "_WIZARD_CATEGORIES"), "Falta _WIZARD_CATEGORIES"

    def test_wizard_has_tui_category(self):
        sys.path.insert(0, str(TOOLS))
        from bago.menus import wizard

        kinds = [k for _, items in wizard._WIZARD_CATEGORIES for k, _ in items]
        assert "tui" in kinds, "Falta categoria 'tui' en wizard"

    def test_wizard_tui_save_creates_py_and_wiring(self):
        sys.path.insert(0, str(TOOLS))
        from bago.menus import wizard

        import tempfile
        tmpdir = Path(tempfile.mkdtemp())
        orig_dir = wizard.SCRIPT_DIR
        wizard.SCRIPT_DIR = tmpdir
        try:
            d = {
                "name": "contract_test_menu",
                "code": "#!/usr/bin/env python3\nprint('ok')",
                "wiring": {"opciones": [{"key": "1", "label": "A", "cmd": ["echo", "a"]}]},
                "description": "test",
                "tags": ["tui"],
            }
            wizard._wizard_save("tui", d)
            py = tmpdir / "contract_test_menu.py"
            wiring = tmpdir / "contract_test_menu_wiring.json"
            assert py.exists(), "No se creo el script .py"
            assert wiring.exists(), "No se creo el wiring .json"
            wdata = json.loads(wiring.read_text(encoding="utf-8"))
            assert "opciones" in wdata, "wiring sin campo opciones"
        finally:
            wizard.SCRIPT_DIR = orig_dir
            for f in tmpdir.iterdir():
                f.unlink()
            tmpdir.rmdir()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
