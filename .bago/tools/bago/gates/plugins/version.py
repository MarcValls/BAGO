"""
Gate: Version Truth
Verifica que la versión en pack.json sea consistente en todos los
ficheros que la referencian (pyproject.toml, README.md, install.ps1, etc.).
"""

from __future__ import annotations

import sys
from pathlib import Path

from bago.gates import Gate, GateResult, Status


class VersionGate:
    name = "version"
    description = "Consistencia de versiones en todos los artefactos del pack"

    def run(self, root: Path) -> GateResult:
        script = root / ".bago" / "tools" / "version_truth.py"
        if not script.exists():
            return GateResult(
                gate_name=self.name,
                status=Status.SKIP,
                details="version_truth.py no encontrado",
            )

        import subprocess
        result = subprocess.run(
            [sys.executable, str(script), "audit", "--json"],
            cwd=str(root),
            text=True,
            capture_output=True,
        )

        try:
            data = result.stdout.strip()
            payload = {} if not data else __import__("json").loads(data)
        except Exception:
            payload = {}

        mismatches = payload.get("mismatches", [])
        truth = payload.get("truth", "unknown")

        if mismatches:
            status = Status.KO
            details = f"{len(mismatches)} mismatch(es) contra versión '{truth}'"
        else:
            status = Status.GO
            details = f"Versión '{truth}' consistente en todos los ficheros"

        return GateResult(
            gate_name=self.name,
            status=status,
            details=details,
            evidence={"truth": truth, "mismatches": mismatches},
        )
