"""
Gate: Sincerity Detector
Wrapper sobre sincerity_detector.py que escanea markdown en busca de
lenguaje inflado, éxitos cosméticos sin evidencia, etc.
"""

from __future__ import annotations

import sys
from pathlib import Path

from bago.gates import Gate, GateResult, Status


class SincerityGate:
    name = "sincerity"
    description = "Detecta lenguaje inflado y éxitos sin evidencia en docs .md"

    def run(self, root: Path) -> GateResult:
        detector_path = root / ".bago" / "tools" / "sincerity_detector.py"
        if not detector_path.exists():
            return GateResult(
                gate_name=self.name,
                status=Status.SKIP,
                details="sincerity_detector.py no encontrado",
            )

        # Ejecutar sincerity_detector con --json para parsear resultado
        import subprocess
        result = subprocess.run(
            [sys.executable, str(detector_path), "--json", "--path", str(root)],
            cwd=str(root),
            text=True,
            capture_output=True,
        )

        try:
            data = result.stdout.strip()
            payload = {} if not data else __import__("json").loads(data)
        except Exception:
            payload = {}

        totals = payload.get("totals", {})
        errors = totals.get("ERROR", 0)
        warns = totals.get("WARN", 0)
        findings = payload.get("findings", [])

        if errors > 0:
            status = Status.KO
        elif warns > 0:
            status = Status.WARN
        else:
            status = Status.GO

        return GateResult(
            gate_name=self.name,
            status=status,
            details=f"{errors} ERROR, {warns} WARN en {payload.get('scanned_files', 0)} ficheros .md",
            evidence={"totals": totals, "findings_count": len(findings)},
        )
