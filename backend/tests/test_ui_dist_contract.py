from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "ui-react" / "dist"


class UIDistContractTests(unittest.TestCase):
    def test_ui_dist_artifacts_exist(self) -> None:
        self.assertTrue((DIST / "index.html").is_file())
        self.assertTrue((DIST / "ui_config.json").is_file())
        self.assertGreaterEqual(len(list(DIST.glob("assets/*"))), 2)

    def test_ui_config_version_matches_release_version(self) -> None:
        config = json.loads((DIST / "ui_config.json").read_text(encoding="utf-8"))
        release_version = (ROOT / "release_version.txt").read_text(encoding="utf-8").strip()
        self.assertEqual(config["version"], release_version)
        self.assertTrue(config["nav"]["chat"])
        self.assertTrue(config["nav"]["manager"])
        self.assertTrue(config["nav"]["terminal"])

    def test_ui_dist_is_local_only_and_secret_free(self) -> None:
        html = (DIST / "index.html").read_text(encoding="utf-8")
        self.assertIn("./assets/index-", html)
        self.assertNotIn("https://", html.lower())
        self.assertNotIn("http://", html.lower())

        secret_patterns = [
            re.compile(r"sk-[A-Za-z0-9]{32,}"),
            re.compile(r"\d{8,12}:AA[A-Za-z0-9_-]{30,}"),
        ]
        for path in DIST.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".html", ".js", ".css", ".json"}:
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in secret_patterns:
                self.assertIsNone(pattern.search(text), f"secret pattern found in {path}")


if __name__ == "__main__":
    unittest.main()
