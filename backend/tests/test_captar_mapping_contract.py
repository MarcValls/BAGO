from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "CAPTAR_INTERPRETATION_MAPPING.md"


def test_captar_mapping_document_exists_and_declares_scope() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "Status: canonical_complement" in text
    assert "no sustituye `CANON.MD`" in text
    assert "No corrige una regla vigente. La operacionaliza." in text


def test_captar_phases_are_mapped_to_canonical_artifacts() -> None:
    text = DOC.read_text(encoding="utf-8")

    for phase in ("Capturar", "Aislar", "Perfilar", "Trazar", "Arquitectar", "Revisar"):
        assert f"| {phase} |" in text

    for artifact in (
        "ReflexiveQuestionRecord",
        "ContextEnvelope",
        "ContextReceipt",
        "literal_question",
        "object_level_target",
        "evidence_anchor_ids",
        "response_contract",
    ):
        assert artifact in text


def test_captar_preserves_boundaries_required_by_canon() -> None:
    text = DOC.read_text(encoding="utf-8")

    for boundary in (
        "No convierte una interpretacion estable en verdad factual.",
        "No autoriza ejecucion si falta capacidad, permiso o evidencia.",
        "No permite presentar inferencias como hechos confirmados.",
    ):
        assert boundary in text


def test_reflexive_implementation_references_captar_mapping() -> None:
    doc = (ROOT / "docs" / "REFLEXIVE_INTERPRETER.md").read_text(encoding="utf-8")

    assert "Complemento operativo CAPTAR" in doc
    assert "docs/CAPTAR_INTERPRETATION_MAPPING.md" in doc
