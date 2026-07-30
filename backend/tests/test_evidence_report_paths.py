from pathlib import Path

from bago_core.evidence_report import _build_report_header, _validation_commands
from bago_core.evidence_model import PROFILES


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "evidence" / "release_4_8_1"


def test_real_evidence_commands_reproduce_the_actual_output_path():
    commands = _validation_commands("real", "community-knowledge", OUTPUT, "copilot", "gpt-5.4-mini")
    assert "python -m bago_core.evidence_cli --test" in commands
    assert 'docs/evidence/release_4_8_1' in commands[-1]
    assert '--provider copilot --model "gpt-5.4-mini" --base-path .' in commands[-1]


def test_report_header_uses_actual_repo_relative_path():
    header = _build_report_header(
        profile=PROFILES["community-knowledge"],
        mode="real",
        provider="copilot",
        model="gpt-5.4-mini",
        session_id="session-real",
        output_dir=OUTPUT,
    )
    assert "- **Generado en:** `docs/evidence/release_4_8_1`" in header
