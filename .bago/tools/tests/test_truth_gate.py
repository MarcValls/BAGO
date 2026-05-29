from pathlib import Path
import os
import sys

import pytest

# Ajusta sys.path para repo local de BAGO si el paquete no está instalado.
ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / ".bago" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from bago.truth_gate import (
    TruthGateError,
    add_claim,
    assert_can_close_task,
    render_trace_report,
    run_command,
)


def test_blocks_assertive_claim_without_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("BAGO_TRACE_SESSION", "test-no-evidence")
    with pytest.raises(TruthGateError):
        add_claim(
            "Trabajo completado y verificado",
            conclusion="Todo pasa",
            evidence_ids=[],
            kind="task_complete",
            root=tmp_path,
        )


def test_test_pass_requires_pytest_rc_zero(tmp_path, monkeypatch):
    monkeypatch.setenv("BAGO_TRACE_SESSION", "test-pass-requires-pytest")
    ev = run_command(
        f'{sys.executable} -c "print(123)"',
        cwd=tmp_path,
        purpose="non pytest command",
        root=tmp_path,
    )
    with pytest.raises(TruthGateError):
        add_claim(
            "Los tests pasan",
            conclusion="No hay regresiones",
            evidence_ids=[ev.evidence_id],
            kind="test_pass",
            root=tmp_path,
        )


def test_absence_requires_two_searches(tmp_path, monkeypatch):
    monkeypatch.setenv("BAGO_TRACE_SESSION", "test-absence")
    (tmp_path / "a.txt").write_text("hola\n", encoding="utf-8")

    # Python command no cuenta como búsqueda; debe ser rg/grep/Select-String/findstr.
    ev = run_command(
        f'{sys.executable} -c "print(\'not found\')"',
        cwd=tmp_path,
        purpose="fake search",
        root=tmp_path,
    )

    with pytest.raises(TruthGateError):
        add_claim(
            "El test no aparece",
            conclusion="No existe",
            evidence_ids=[ev.evidence_id],
            kind="absence",
            root=tmp_path,
        )


def test_preexisting_failure_requires_baseline(tmp_path, monkeypatch):
    monkeypatch.setenv("BAGO_TRACE_SESSION", "test-preexisting")
    test_file = tmp_path / "test_fail.py"
    test_file.write_text("def test_x():\n    assert False\n", encoding="utf-8")

    ev = run_command(
        f"{sys.executable} -m pytest {test_file.name} -q",
        cwd=tmp_path,
        purpose="current failing test",
        allow_fail=True,
        root=tmp_path,
    )

    with pytest.raises(TruthGateError):
        add_claim(
            "El fallo es preexistente",
            conclusion="Ajeno a este trabajo",
            evidence_ids=[ev.evidence_id],
            kind="preexisting_failure",
            root=tmp_path,
        )


def test_can_close_with_pytest_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("BAGO_TRACE_SESSION", "test-close-ok")
    test_file = tmp_path / "test_ok.py"
    test_file.write_text("def test_x():\n    assert True\n", encoding="utf-8")

    ev = run_command(
        f"{sys.executable} -m pytest {test_file.name} -q",
        cwd=tmp_path,
        purpose="validation pytest",
        root=tmp_path,
    )

    add_claim(
        "Validación de tests",
        conclusion="pytest pasa con rc=0",
        evidence_ids=[ev.evidence_id],
        kind="test_pass",
        root=tmp_path,
    )

    add_claim(
        "Trabajo completado",
        conclusion="Cierre permitido por evidencia pytest rc=0",
        evidence_ids=[ev.evidence_id],
        kind="task_complete",
        root=tmp_path,
    )

    assert_can_close_task(root=tmp_path)
    report = render_trace_report(root=tmp_path)
    assert "Claim" in report
    assert "Command" in report
    assert "Conclusion" in report
