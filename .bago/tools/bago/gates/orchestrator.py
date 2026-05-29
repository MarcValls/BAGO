"""
GateOrchestrator — motor de ejecución unificada.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from . import Gate, GateResult, Status


class GateReport:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.results: list[GateResult] = []

    def add(self, result: GateResult) -> None:
        self.results.append(result)

    @property
    def overall_status(self) -> Status:
        if any(r.status == Status.KO for r in self.results):
            return Status.KO
        if any(r.status == Status.WARN for r in self.results):
            return Status.WARN
        if all(r.status == Status.SKIP for r in self.results):
            return Status.SKIP
        return Status.GO

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "overall": self.overall_status.value,
            "gates": [
                {
                    "name": r.gate_name,
                    "status": r.status.value,
                    "details": r.details,
                    "evidence": r.evidence,
                    "duration_ms": r.duration_ms,
                }
                for r in self.results
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def to_markdown(self) -> str:
        lines = [
            "# BAGO Gate Report",
            "",
            f"**Root:** `{self.root}`",
            f"**Overall:** {self.overall_status.value}",
            "",
            "| Gate | Status | Duration | Details |",
            "|------|--------|----------|---------|",
        ]
        for r in self.results:
            details = r.details.replace("|", "\\|").replace("\n", " ")
            if len(details) > 120:
                details = details[:117] + "..."
            lines.append(
                f"| {r.gate_name} | {r.status.value} | {r.duration_ms}ms | {details} |"
            )
        lines.append("")
        for r in self.results:
            if r.evidence:
                lines.append(f"## {r.gate_name} evidence")
                lines.append("```json")
                lines.append(json.dumps(r.evidence, ensure_ascii=False, indent=2))
                lines.append("```")
                lines.append("")
        return "\n".join(lines)


class GateOrchestrator:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._gates: dict[str, Gate] = {}

    def register(self, gate: Gate) -> None:
        self._gates[gate.name] = gate

    def list_gates(self) -> list[str]:
        return sorted(self._gates.keys())

    def run(self, gate_names: list[str] | None = None) -> GateReport:
        report = GateReport(self.root)
        names = gate_names or self.list_gates()
        for name in names:
            gate = self._gates.get(name)
            if gate is None:
                report.add(
                    GateResult(
                        gate_name=name,
                        status=Status.KO,
                        details=f"Gate '{name}' no registrado.",
                    )
                )
                continue
            t0 = time.time()
            try:
                result = gate.run(self.root)
            except Exception as exc:
                result = GateResult(
                    gate_name=gate.name,
                    status=Status.KO,
                    details=f"Excepción interna: {exc}",
                )
            result.duration_ms = int((time.time() - t0) * 1000)
            report.add(result)
        return report
