from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BAGO = ROOT / ".bago"


class Sprint4SurfaceTests(unittest.TestCase):
    def test_roles_and_agents_are_restored(self) -> None:
        manifest = json.loads((BAGO / "roles" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["roles"]), 14)
        self.assertTrue((BAGO / "agents" / "agent_factory.py").exists())
        # 2026-Q2 cleanup: 7 v3.5.0-rc1 stubs (MAESTRO_BAGO, CENTINELA_SINCERIDAD, …) were
        # removed because the active runtime uses inline role contracts. We keep the 4
        # long-lived agent briefs and a factory entry point.
        agent_briefs = [p.name for p in (BAGO / "agents").glob("*.md")]
        self.assertGreaterEqual(len(agent_briefs), 4,
                                 f"expected >=4 live agent briefs, found {agent_briefs}")

    def test_mcp_and_extensions_are_present(self) -> None:
        for name in ["bago_mcp_server.py", "mcp_config.json", "toolbox_catalog.json", "agent_tool_matrix.json"]:
            self.assertTrue((BAGO / "mcp" / name).exists(), name)

        mcp_config = (BAGO / "mcp" / "mcp_config.json").read_text(encoding="utf-8")
        self.assertNotIn("Marc_max_20gb", mcp_config)
        run_script = (BAGO / "mcp" / "run_bago_mcp.cmd").read_text(encoding="utf-8")
        self.assertNotIn("Marc_max_20gb", run_script)

    def test_extensions_and_wrappers_exist(self) -> None:
        self.assertTrue((BAGO / "extensions" / "bash-runner" / "extension.mjs").exists())
        for wrapper in ["bago", "bago.cmd", "bago.ps1", "bago.sh"]:
            self.assertTrue((ROOT / wrapper).exists(), wrapper)

    def test_ci_workflows_have_fail_fast(self) -> None:
        workflows = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertGreaterEqual(len(workflows), 6)
        for path in workflows:
            text = path.read_text(encoding="utf-8")
            self.assertRegex(text, r"(?m)^\s*(?:-?\s*)?(?:exit 1|fail\()")

    def test_daemons_are_not_stable_surface(self) -> None:
        text = (ROOT / "docs" / "MODULES.md").read_text(encoding="utf-8").lower()
        self.assertNotRegex(text, r"(whatsapp|telegram).*(working|stable)")


if __name__ == "__main__":
    unittest.main()

