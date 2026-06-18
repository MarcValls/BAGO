from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIRS = [
    ROOT / "docs" / "evidence" / "simulated_reference_bundle",
    ROOT / "docs" / "evidence" / "example_bundle",
    ROOT / "docs" / "evidence" / "release_4_6_3",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


class EvidenceIntegrityTests(unittest.TestCase):
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
                    self.assertEqual(file_path.stat().st_size, entry["size_bytes"], entry["path"])

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
            self.assertEqual(manifest["contract_version"], "4.6.3")
            self.assertNotIn("cpp", evidence_dir.name.lower())
            self.assertNotIn("4_1_5", evidence_dir.name.lower())
            self.assertNotIn("C:\\", json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
