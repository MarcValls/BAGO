from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / ".bago" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from sincerity_detector import run_scan


@pytest.mark.parametrize(
    ("name", "content", "expected_kind", "expected"),
    [
        ("flat.md", "Sistema espectacular\n", "FLATTERY", True),
        (
            "evidence.md",
            "Siempre funciona segun test_result.json\n",
            "UNSUBSTANTIATED",
            False,
        ),
        ("future.rst", "# Done\nse va a implementar luego\n", "FUTURE_AS_DONE", True),
        ("check.txt", "- [x] ok\n", "EMPTY_CHECKLIST", True),
    ],
)
def test_detector_rules(name: str, content: str, expected_kind: str, expected: bool, tmp_path: Path) -> None:
    document = tmp_path / name
    document.write_text(content, encoding="utf-8")

    _, findings = run_scan(tmp_path, document)

    assert any(item.kind == expected_kind for item in findings) is expected


def test_directory_scan_and_evidence_missing_detection(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("PASSED\n", encoding="utf-8")
    (docs / "b.txt").write_text("todo OK\n", encoding="utf-8")

    files, findings = run_scan(tmp_path, docs)

    assert len(files) == 2
    assert any(item.kind == "EVIDENCE_MISSING" for item in findings)
