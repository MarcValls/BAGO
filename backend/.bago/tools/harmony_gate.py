#!/usr/bin/env python3
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bago_utils import print_test_results

_CONSONANCE = {
    0: 1.00,
    1: 0.08,
    2: 0.17,
    3: 0.50,
    4: 0.80,
    5: 0.83,
    6: 0.00,
}


def phase_consonance(phase_a: int, phase_b: int) -> float:
    diff = abs(int(phase_a) - int(phase_b)) % 12
    semitones = min(diff, 12 - diff)
    return float(_CONSONANCE.get(semitones, max(0.0, 1.0 - semitones / 6.0)))


class SpiralState:
    __slots__ = ("entity_id", "phase", "validate", "fingerprint", "radius_gained", "extra")

    def __init__(
        self,
        entity_id: str = "",
        phase: int = 0,
        validate: str = "WARN",
        fingerprint: list[str] | None = None,
        radius_gained: float = 0.0,
        extra: dict | None = None,
    ):
        self.entity_id = entity_id
        self.phase = int(phase) % 12
        self.validate = validate
        self.fingerprint = list(fingerprint or [])
        self.radius_gained = float(radius_gained)
        self.extra = dict(extra or {})

    @classmethod
    def from_skill_result(cls, result: object) -> "SpiralState":
        state_vector = getattr(result, "state_vector", {}) or {}
        return cls(
            entity_id=getattr(result, "skill_id", ""),
            phase=state_vector.get("phase", 0),
            validate=getattr(result, "validate", "WARN"),
            fingerprint=list(getattr(result, "fingerprint", []) or []),
            radius_gained=float(getattr(result, "radius_gained", 0.0)),
        )

    @classmethod
    def from_dict(cls, data: dict) -> "SpiralState":
        return cls(
            entity_id=data.get("entity_id", data.get("skill_id", data.get("agent_id", ""))),
            phase=data.get("phase", 0),
            validate=data.get("validate", "WARN"),
            fingerprint=data.get("fingerprint", []),
            radius_gained=data.get("radius_gained", 0.0),
            extra=data.get("extra", {}),
        )


@dataclass
class GateResult:
    open: bool
    score: float
    reason: str


class HarmonyGate:
    def __init__(self, threshold: float = 0.6):
        self.threshold = float(threshold)

    def score(self, a: SpiralState, b: SpiralState) -> float:
        phase_score = phase_consonance(a.phase, b.phase)
        validate_score = 1.0 if a.validate == b.validate else (0.6 if "FAIL" not in {a.validate, b.validate} else 0.2)
        tags_a = set(a.fingerprint)
        tags_b = set(b.fingerprint)
        overlap = (len(tags_a & tags_b) / len(tags_a | tags_b)) if (tags_a or tags_b) else 1.0
        radius_gap = abs(a.radius_gained - b.radius_gained)
        radius_score = max(0.0, 1.0 - min(radius_gap, 1.0))
        score = (phase_score * 0.4) + (validate_score * 0.25) + (overlap * 0.2) + (radius_score * 0.15)
        return round(score, 4)

    def is_open(self, a: SpiralState, b: SpiralState) -> bool:
        return self.score(a, b) >= self.threshold

    def check_before(self, previous: SpiralState, current: SpiralState) -> GateResult:
        score = self.score(previous, current)
        return GateResult(score >= self.threshold, score, "before")

    def check_after(self, current: SpiralState, nxt: SpiralState) -> GateResult:
        score = self.score(current, nxt)
        return GateResult(score >= self.threshold, score, "after")


def _run_tests() -> int:
    gate = HarmonyGate(threshold=0.6)
    a = SpiralState(entity_id="a", phase=0, validate="GO", fingerprint=["x"], radius_gained=0.2)
    b = SpiralState(entity_id="b", phase=4, validate="GO", fingerprint=["x", "y"], radius_gained=0.3)
    c = SpiralState(entity_id="c", phase=6, validate="FAIL", fingerprint=["z"], radius_gained=1.0)
    results = [
        ("phase_consonance", phase_consonance(0, 4) > phase_consonance(0, 6), "music interval weighting works"),
        ("score_range", 0.0 <= gate.score(a, b) <= 1.0, "score stays in range"),
        ("open_gate", gate.is_open(a, b), "similar spiral states open the gate"),
        ("closed_gate", not gate.is_open(a, c), "dissonant states close the gate"),
    ]
    return print_test_results(results)


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
    print("harmony_gate: use as a library or run with --test")
