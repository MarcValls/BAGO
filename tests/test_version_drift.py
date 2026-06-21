from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = (ROOT / "release_version.txt").read_text(encoding="utf-8").strip()


class VersionDriftTests(unittest.TestCase):
    def test_new_session_metadata_uses_release_version(self) -> None:
        import sys

        core = ROOT / ".bago" / "core"
        if str(core) not in sys.path:
            sys.path.insert(0, str(core))

        from session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmp:
            state_root = Path(tmp) / "state"
            old = os.environ.get("BAGO_STATE_ROOT")
            os.environ["BAGO_STATE_ROOT"] = str(state_root)
            try:
                mgr = SessionManager(base_path=tmp, state_root=str(state_root))
                try:
                    meta_path = state_root / "sessions" / mgr.session_id / "meta.json"
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    self.assertEqual(meta.get("bago_version"), EXPECTED_VERSION)
                finally:
                    mgr.close()
            finally:
                if old is None:
                    os.environ.pop("BAGO_STATE_ROOT", None)
                else:
                    os.environ["BAGO_STATE_ROOT"] = old

    def test_runtime_entrypoints_do_not_declare_legacy_release_version(self) -> None:
        paths = [
            ROOT / ".bago" / "core" / "session_manager.py",
            ROOT / ".bago" / "core" / "context_store.py",
            ROOT / ".bago" / "tools" / "orchestrator_v4.py",
            ROOT / "scripts" / "bago_supervisor.py",
            ROOT / "bago_core" / "evidence_report.py",
            ROOT / "test_e2e.py",
        ]
        for path in paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertNotIn("4.1.5", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
