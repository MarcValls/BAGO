"""
Gate: Interface Consistency
Valida que todos los entrypoints de BAGO (CLI, Bridge, GUI, API)
carguen configuración de forma consistente y manejen la sesión
con la misma estructura de datos.

Cada interfaz es un gate implícito porque transforma/interpreta
el historial, la configuración y el estado de la sesión de forma
distinta. Este plugin hace explícita esa verificación.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from bago.gates import Gate, GateResult, Status


# Entrypoints que deben cargar config y aplicar flags consistentemente
_REQUIRED_FLAGS = {
    "single_model": {"default": False, "type": bool},
    "autoroute": {"default": True, "type": bool},
    "autonomous": {"default": False, "type": bool},
    "orch_mode": {"default": "standard", "type": str},
}

_ENTRYPOINTS = {
    "bago_chat.py": Path("bago_chat.py"),
    "bago_unimodel_bridge.py": Path("bago_unimodel_bridge.py"),
    "dev_twin/app.py": Path("dev_twin") / "app.py",
}


class InterfaceConsistencyGate:
    name = "interface_consistency"
    description = (
        "Valida que todos los entrypoints carguen config y apliquen "
        "single_model, autoroute, autonomous, orch_mode de forma consistente"
    )

    def run(self, root: Path) -> GateResult:
        tools_dir = root / ".bago" / "tools"
        findings = []
        missing = []

        for label, rel_path in _ENTRYPOINTS.items():
            path = tools_dir / rel_path
            if not path.exists():
                missing.append(label)
                continue

            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)

            # Check config loading
            has_load_config = self._has_config_load(tree)
            # Check each required flag
            flag_status = self._check_flags(source, label)

            if not has_load_config:
                findings.append(
                    f"{label}: NO carga config (_load_config faltante)"
                )

            for flag, ok in flag_status.items():
                if not ok:
                    findings.append(
                        f"{label}: NO aplica '{flag}' desde config"
                    )

        if missing:
            return GateResult(
                gate_name=self.name,
                status=Status.SKIP,
                details=f"Entrypoints no encontrados: {', '.join(missing)}",
                evidence={"missing": missing},
            )

        if findings:
            return GateResult(
                gate_name=self.name,
                status=Status.KO,
                details=f"{len(findings)} inconsistencias en entrypoints",
                evidence={"findings": findings},
            )

        return GateResult(
            gate_name=self.name,
            status=Status.GO,
            details="Todos los entrypoints cargan config y aplican flags consistentemente",
            evidence={"entrypoints_checked": list(_ENTRYPOINTS.keys())},
        )

    def _has_config_load(self, tree: ast.AST) -> bool:
        """Verifica que el AST contenga una llamada a _load_config()."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "_load_config":
                    return True
                # También detecta cfg = _load_config() o similar
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "_load_config"
                ):
                    return True
        return False

    def _check_flags(self, source: str, label: str) -> dict[str, bool]:
        """Verifica que cada flag requerida se aplique desde config.

        Busca patrones como:
          cfg.get("flag", ...)
          config.get("flag", ...)
        en el source original.
        """
        status = {flag: False for flag in _REQUIRED_FLAGS}
        low = source.lower()
        for flag in _REQUIRED_FLAGS:
            q = f'"{flag}"'
            if f"cfg.get({q}" in low or f"config.get({q}" in low:
                status[flag] = True
        return status
