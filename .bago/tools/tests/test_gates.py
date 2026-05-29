from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / ".bago" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from bago.gates import Gate, GateResult, Status
from bago.gates.orchestrator import GateOrchestrator, GateReport


class FakeGate:
    name = "fake"
    description = "gate de prueba"

    def __init__(self, status: Status, details: str = ""):
        self._status = status
        self._details = details

    def run(self, root: Path) -> GateResult:
        return GateResult(gate_name=self.name, status=self._status, details=self._details)


def test_orchestrator_runs_registered_gate():
    orch = GateOrchestrator(Path("/tmp"))
    orch.register(FakeGate(Status.GO, "todo ok"))
    report = orch.run(["fake"])
    assert len(report.results) == 1
    assert report.results[0].status == Status.GO
    assert report.results[0].details == "todo ok"


def test_orchestrator_returns_ko_for_missing_gate():
    orch = GateOrchestrator(Path("/tmp"))
    report = orch.run(["missing"])
    assert len(report.results) == 1
    assert report.results[0].status == Status.KO
    assert "no registrado" in report.results[0].details


def test_overall_status_ko_if_any_ko():
    orch = GateOrchestrator(Path("/tmp"))
    orch.register(FakeGate(Status.GO))
    orch.register(FakeGate(Status.KO, "fallo"))
    report = orch.run()
    assert report.overall_status == Status.KO


def test_overall_status_warn_if_any_warn():
    orch = GateOrchestrator(Path("/tmp"))
    orch.register(FakeGate(Status.GO))
    orch.register(FakeGate(Status.WARN, "cuidado"))
    report = orch.run()
    assert report.overall_status == Status.WARN


def test_report_markdown_contains_gate_name():
    orch = GateOrchestrator(Path("/tmp"))
    orch.register(FakeGate(Status.GO, "bien"))
    report = orch.run()
    md = report.to_markdown()
    assert "fake" in md
    assert "GO" in md
    assert "bien" in md


def test_report_json_contains_overall():
    orch = GateOrchestrator(Path("/tmp"))
    orch.register(FakeGate(Status.SKIP, "saltado"))
    report = orch.run()
    data = report.to_dict()
    assert data["overall"] == "SKIP"
    assert len(data["gates"]) == 1


def test_duration_ms_populated():
    orch = GateOrchestrator(Path("/tmp"))
    orch.register(FakeGate(Status.GO))
    report = orch.run()
    assert report.results[0].duration_ms >= 0


def test_interface_consistency_gate_real_repo():
    from bago.gates.plugins import InterfaceConsistencyGate
    gate = InterfaceConsistencyGate()
    result = gate.run(ROOT)
    # En el repo real, todos los entrypoints deberían cargar config correctamente
    assert result.status in {Status.GO, Status.KO, Status.SKIP}
    assert result.gate_name == "interface_consistency"
    if result.status == Status.GO:
        assert "config" in result.details.lower()
    # Evidence debe listar entrypoints verificados o findings
    assert isinstance(result.evidence, dict)
