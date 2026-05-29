"""
Gate: Truth Gate
Verifica trazabilidad de claims: si hay un trace activo, valida que
exista al menos una claim task_complete con evidencia pytest rc=0.
"""

from __future__ import annotations

from pathlib import Path

from bago.gates import Gate, GateResult, Status


class TruthGate:
    name = "truth"
    description = "Trazabilidad de claims (task_complete con evidencia)"

    def run(self, root: Path) -> GateResult:
        try:
            from bago.truth_gate import TruthGateError, assert_can_close_task
        except Exception as exc:
            return GateResult(
                gate_name=self.name,
                status=Status.SKIP,
                details=f"No se pudo importar truth_gate: {exc}",
            )

        # Solo validar si hay un trace activo (env var o archivo existe)
        import os
        if not os.environ.get("BAGO_TRACE_SESSION"):
            trace_dir = root / ".bago" / "traces"
            if not trace_dir.exists() or not any(trace_dir.glob("*.jsonl")):
                return GateResult(
                    gate_name=self.name,
                    status=Status.SKIP,
                    details="No hay trace activo; truth gate no aplica en esta ejecución",
                )

        try:
            assert_can_close_task(root)
            return GateResult(
                gate_name=self.name,
                status=Status.GO,
                details="Trace validado: existe task_complete con evidencia pytest rc=0",
            )
        except TruthGateError as exc:
            return GateResult(
                gate_name=self.name,
                status=Status.KO,
                details=str(exc),
            )
