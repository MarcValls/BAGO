from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BAGO = ROOT / ".bago"
LIVE_SURFACES = ROOT / "docs" / "live-surfaces.md"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Sprint4SurfaceTests(unittest.TestCase):
    def test_install_roles_surface_is_live(self) -> None:
        install_roles = load_module(ROOT / "bago_core" / "install_roles.py", "bago_install_roles")
        self.assertEqual(tuple(install_roles.ROLES), ("active", "dev", "launch", "writer", "illustrator"))
        self.assertEqual(install_roles.load_selection(ROOT / "missing-selection.json")["version"], 1)
        preload = (ROOT / "electron" / "preload.cjs").read_text(encoding="utf-8")
        for method in ["readInstallSelection", "writeInstallSelection", "buildRoleCommand"]:
            self.assertIn(method, preload)

    def test_http_api_is_the_live_integration_surface(self) -> None:
        dispatch = load_module(BAGO / "api" / "api_dispatch.py", "bago_api_dispatch")
        routes = {(method, path) for method, path, _module, _fn in dispatch.ROUTE_META}
        for route in [("GET", "/status"), ("GET", "/session"), ("GET", "/menu"), ("POST", "/command")]:
            self.assertIn(route, routes)
        text = LIVE_SURFACES.read_text(encoding="utf-8").lower()
        self.assertIn(".bago/mcp", text)
        self.assertIn("retired", text)

    def test_extensions_are_not_active_runtime_surface(self) -> None:
        self.assertTrue((ROOT / "bago_core" / "execution" / "process_runner.py").exists())
        text = LIVE_SURFACES.read_text(encoding="utf-8").lower()
        self.assertIn(".bago/extensions/bash-runner", text)
        self.assertIn("retired", text)

    def test_wrappers_exist(self) -> None:
        for wrapper in ["bago", "bago.cmd", "bago.ps1", "bago.sh"]:
            self.assertTrue((ROOT / wrapper).exists(), wrapper)

    def test_ci_workflows_are_source_repo_surface_not_runtime_surface(self) -> None:
        source_root = ROOT.parent if (ROOT.parent / ".git").exists() else ROOT
        self.assertTrue((source_root / ".github" / "workflows").exists())
        text = LIVE_SURFACES.read_text(encoding="utf-8").lower()
        self.assertIn(".github/workflows", text)
        self.assertIn("source repository", text)
        for doc in ["README.md", "manual.md"]:
            self.assertNotIn("`.github/workflows/branch-flow-guard.yml`", (ROOT / doc).read_text(encoding="utf-8"))

    def test_daemons_are_not_stable_surface(self) -> None:
        text = (ROOT / "docs" / "modules.md").read_text(encoding="utf-8").lower()
        self.assertNotRegex(text, r"(whatsapp|telegram).*(working|stable)")


if __name__ == "__main__":
    unittest.main()
