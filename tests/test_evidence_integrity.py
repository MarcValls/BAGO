from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bago_core.versioning import read_release_version


ROOT = Path(__file__).resolve().parents[1]
CURRENT_RELEASE = read_release_version(ROOT)
CURRENT_RELEASE_EVIDENCE = ROOT / "docs" / "evidence" / f"release_{CURRENT_RELEASE.replace('.', '_')}"
EVIDENCE_DIRS = [
    ROOT / "docs" / "evidence" / "simulated_reference_bundle",
    ROOT / "docs" / "evidence" / "example_bundle",
    CURRENT_RELEASE_EVIDENCE,
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        data = handle.read()
    # Normalize text artifacts to LF for cross-platform reproducibility.
    suffix = path.suffix.lower()
    if suffix in {".json", ".jsonl", ".md", ".txt"} or path.name in {"checksums.sha256"}:
        data = data.replace(b"\r\n", b"\n")
        data = data.replace(b"\r", b"\n")
    digest.update(data)
    return digest.hexdigest()


def _is_text_artifact(path: Path) -> bool:
    suffix = path.suffix.lower()
    return suffix in {".json", ".jsonl", ".md", ".txt"} or path.name == "checksums.sha256"


class EvidenceIntegrityTests(unittest.TestCase):
    def _load_session_version(self, evidence_dir: Path) -> str:
        session_meta = json.loads((evidence_dir / "session" / "meta.json").read_text(encoding="utf-8"))
        return session_meta["bago_version"]

    def test_historical_evidence_hashes_match_packaged_bytes(self) -> None:
        for evidence_dir in EVIDENCE_DIRS:
            with self.subTest(evidence=str(evidence_dir.relative_to(ROOT))):
                manifest_path = evidence_dir / "manifest.json"
                checksums_path = evidence_dir / "checksums.sha256"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

                manifest_files = manifest.get("files", [])
                self.assertNotIn("manifest.json", {entry["path"] for entry in manifest_files})
                self.assertNotIn("checksums.sha256", {entry["path"] for entry in manifest_files})
                for entry in manifest_files:
                    file_path = evidence_dir / entry["path"]
                    self.assertTrue(file_path.exists(), entry["path"])
                    self.assertEqual(_sha256(file_path), entry["sha256"], entry["path"])
                    # Size in manifest must match normalized size for text artifacts,
                    # or raw size for binary artifacts.
                    expected_size = entry["size_bytes"]
                    if _is_text_artifact(file_path):
                        raw = file_path.read_bytes()
                        normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
                        expected_size = len(normalized)
                    self.assertEqual(file_path.stat().st_size, expected_size, entry["path"])

                checksum_paths: set[str] = set()
                for raw in checksums_path.read_text(encoding="utf-8").splitlines():
                    if not raw.strip():
                        continue
                    expected, rel = raw.split(maxsplit=1)
                    rel = rel.lstrip("*")
                    checksum_paths.add(rel)
                    file_path = evidence_dir / rel
                    self.assertTrue(file_path.exists(), rel)
                    self.assertEqual(_sha256(file_path), expected, rel)
                self.assertIn("manifest.json", checksum_paths)
                self.assertNotIn("checksums.sha256", checksum_paths)

    def test_current_evidence_names_match_manifest_content(self) -> None:
        for evidence_dir in EVIDENCE_DIRS:
            manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["contract_version"], self._load_session_version(evidence_dir))
            self.assertNotIn("cpp", evidence_dir.name.lower())
            self.assertNotIn("4_1_5", evidence_dir.name.lower())
            self.assertNotIn("C:\\", json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
