"""BagoSafetyValidator — validador de invariantes para sandbox RL.

Verifica que una acción no viole restricciones de seguridad
antes de permitir su ejecución en el entorno real.

Ejemplo:
    validator = BagoSafetyValidator()
    validator.add_rule("budget_minimum", lambda s, a: s["budget_left"] > 0.05)
    valid, reason = validator.check(obs, action)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np


@dataclass
class ValidationRule:
    name: str
    check: Callable[[dict[str, Any], int], bool]
    description: str = ""


class BagoSafetyValidator:
    """Validador independiente de invariantes del sistema BAGO."""

    def __init__(self) -> None:
        self._rules: list[ValidationRule] = []
        self._history: list[dict[str, Any]] = []

    def add_rule(self, name: str, check: Callable[[dict[str, Any], int], bool], description: str = "") -> None:
        """Registra una nueva regla de validación."""
        self._rules.append(ValidationRule(name, check, description))

    def check(self, state: dict[str, Any], action: int) -> tuple[bool, str]:
        """Evalúa todas las reglas para (state, action).

        Returns:
            (True, "") si pasa todas las reglas.
            (False, reason) si falla alguna regla.
        """
        for rule in self._rules:
            try:
                if not rule.check(state, action):
                    return False, f"Rule '{rule.name}' failed: {rule.description}"
            except Exception as exc:
                return False, f"Rule '{rule.name}' exception: {exc}"
        return True, ""

    def log(self, state: dict[str, Any], action: int, valid: bool, reason: str) -> None:
        """Registra la decisión para auditoría."""
        self._history.append({
            "state": state,
            "action": action,
            "valid": valid,
            "reason": reason,
        })

    def reset_history(self) -> None:
        self._history.clear()

    @classmethod
    def default_validator(cls) -> "BagoSafetyValidator":
        """Retorna un validador con reglas de seguridad por defecto."""
        v = cls()

        # Regla 1: no ejecutar si presupuesto está agotado
        v.add_rule(
            "budget_minimum",
            lambda s, a: float(s.get("budget_left", [1.0])[0]) > 0.01,
            description="Budget must be > 0.01 to execute actions",
        )

        # Regla 2: no más de 5 reintentos consecutivos
        v.add_rule(
            "retry_limit",
            lambda s, a: int(s.get("retry_count", 0)) < 5,
            description="Max 5 consecutive retries allowed",
        )

        # Regla 3: validator_score debe mantenerse > 0.2
        v.add_rule(
            "score_minimum",
            lambda s, a: float(s.get("last_validator_score", [1.0])[0]) > 0.2,
            description="Validator score must stay above 0.2",
        )

        return v

    def _self_test(self) -> int:
        print("[BagoSafetyValidator] Self-test starting...")

        v = BagoSafetyValidator.default_validator()

        # Test 1: budget rule
        ok, reason = v.check({"budget_left": [0.1], "retry_count": 0, "last_validator_score": [0.5]}, 0)
        assert ok, f"Expected pass, got: {reason}"
        print("   ✓ Budget rule pass OK")

        ok, reason = v.check({"budget_left": [0.0], "retry_count": 0, "last_validator_score": [0.5]}, 0)
        assert not ok, f"Expected fail, got: {reason}"
        print("   ✓ Budget rule fail OK")

        # Test 2: retry rule
        ok, reason = v.check({"budget_left": [1.0], "retry_count": 4, "last_validator_score": [0.5]}, 0)
        assert ok
        print("   ✓ Retry rule pass OK")

        ok, reason = v.check({"budget_left": [1.0], "retry_count": 5, "last_validator_score": [0.5]}, 0)
        assert not ok
        print("   ✓ Retry rule fail OK")

        # Test 3: score rule
        ok, reason = v.check({"budget_left": [1.0], "retry_count": 0, "last_validator_score": [0.1]}, 0)
        assert not ok
        print("   ✓ Score rule fail OK")

        # Test 4: log
        v.log({"budget_left": [1.0]}, 0, True, "")
        assert len(v._history) == 1
        print("   ✓ Log OK")

        print("[BagoSafetyValidator] Self-test PASSED (4/4)")
        return 0


if __name__ == "__main__":
    import sys

    validator = BagoSafetyValidator()
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        sys.exit(validator._self_test())
    print("BagoSafetyValidator loaded — run with --test to validate")
