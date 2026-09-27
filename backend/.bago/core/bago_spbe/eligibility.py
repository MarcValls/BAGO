from __future__ import annotations

from .model import CapabilityCandidate, Eligibility, EligibilityDecision, Requirement


class EligibilityEvaluator:
    """Deterministic hard-gate evaluator. No ranking occurs here."""

    def evaluate(self, candidate: CapabilityCandidate, requirements: tuple[Requirement, ...]) -> EligibilityDecision:
        satisfied: list[str] = []
        failed: list[str] = []
        unknown: list[str] = []
        basis: list[str] = []

        for req in requirements:
            result, reason = self._evaluate_requirement(candidate, req)
            basis.append(f"{req.requirement_id}:{reason}")
            if result is True:
                satisfied.append(req.requirement_id)
            elif result is False:
                if req.hard:
                    failed.append(req.requirement_id)
                else:
                    # soft requirement failure is evidence, not ineligibility
                    satisfied.append(f"soft-miss:{req.requirement_id}")
            else:
                if req.hard:
                    unknown.append(req.requirement_id)
                else:
                    satisfied.append(f"soft-unknown:{req.requirement_id}")

        if failed:
            decision = Eligibility.NOT_ELIGIBLE
        elif unknown:
            decision = Eligibility.UNKNOWN
        else:
            decision = Eligibility.ELIGIBLE

        return EligibilityDecision(
            candidate_ref=candidate.ref,
            decision=decision,
            requirements_satisfied=tuple(satisfied),
            requirements_failed=tuple(failed),
            unknown_requirements=tuple(unknown),
            decision_basis=tuple(basis),
        )

    def _evaluate_requirement(self, candidate: CapabilityCandidate, req: Requirement) -> tuple[bool | None, str]:
        p = req.predicate
        a = req.args
        if p == "provides":
            cap = a.get("capability")
            if cap is None:
                return None, "missing capability arg"
            return cap in candidate.provides, f"provides({cap})"
        if p == "not_provides":
            cap = a.get("capability")
            if cap is None:
                return None, "missing capability arg"
            return cap not in candidate.provides, f"not_provides({cap})"
        if p == "attribute_eq":
            key = a.get("key")
            if key is None or "value" not in a:
                return None, "missing attribute_eq args"
            if key not in candidate.attributes:
                return None, f"attribute({key}) unknown"
            return candidate.attributes.get(key) == a["value"], f"attribute({key}) == {a['value']!r}"
        if p == "attribute_in":
            key = a.get("key")
            values = a.get("values")
            if key is None or values is None:
                return None, "missing attribute_in args"
            if key not in candidate.attributes:
                return None, f"attribute({key}) unknown"
            return candidate.attributes.get(key) in values, f"attribute({key}) in {values!r}"
        if p == "evidence_provides":
            evidence = a.get("evidence")
            if evidence is None:
                return None, "missing evidence arg"
            return evidence in candidate.evidence_capabilities, f"evidence_provides({evidence})"
        return None, f"unknown predicate:{p}"
