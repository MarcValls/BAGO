"""
Gate: Pre-Push Guard
Wrapper sobre pre_push_guard.py que ejecuta todas las validaciones
pre-push (secrets, orphans, clean tree, remote sync, tests, health, etc.).
"""

from __future__ import annotations

import sys
from pathlib import Path

from bago.gates import Gate, GateResult, Status


class PrePushGate:
    name = "prepush"
    description = "Validaciones pre-push: secrets, orphans, tree, remote, tests, health, sincerity, stability"

    def run(self, root: Path) -> GateResult:
        script = root / ".bago" / "tools" / "pre_push_guard.py"
        if not script.exists():
            return GateResult(
                gate_name=self.name,
                status=Status.SKIP,
                details="pre_push_guard.py no encontrado",
            )

        import subprocess
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(root),
            text=True,
            capture_output=True,
        )

        # pre_push_guard.py imprime "DECISION: GO" o "DECISION: KO"
        output = result.stdout + "\n" + result.stderr
        if "DECISION: GO" in output:
            status = Status.GO
        elif "DECISION: KO" in output:
            status = Status.KO
        else:
            status = Status.KO if result.returncode != 0 else Status.GO

        lines = output.strip().splitlines()
        # Resumen de los checks que fallaron
        failed = [ln for ln in lines if ln.strip().startswith("FAIL")]
        details = f"exit={result.returncode}; {len(failed)} check(s) en KO" if failed else f"exit={result.returncode}; todos los checks OK"

        return GateResult(
            gate_name=self.name,
            status=status,
            details=details,
            evidence={
                "exit_code": result.returncode,
                "failed_checks": failed[:10],
                "stdout_tail": "\n".join(lines[-30:]),
            },
        )
