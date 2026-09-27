from __future__ import annotations

from .model import CapabilityCandidate, EligibilityDecision, Eligibility, ResolutionDecision, ResolutionMode, ResolutionPolicy


class CapabilityResolver:
    """Resolve only among ELIGIBLE candidates; ranking never rescues ineligibility."""

    def resolve(
        self,
        candidates: tuple[CapabilityCandidate, ...],
        decisions: tuple[EligibilityDecision, ...],
        policy: ResolutionPolicy,
    ) -> ResolutionDecision | None:
        by_key = {c.ref.stable_key: c for c in candidates}
        eligible = [by_key[d.candidate_ref.stable_key] for d in decisions if d.decision is Eligibility.ELIGIBLE]
        rejected = [d.candidate_ref.stable_key for d in decisions if d.decision is not Eligibility.ELIGIBLE]
        if not eligible:
            return None

        mode_rank = {mode: i for i, mode in enumerate(policy.reuse_preference)}
        preferred = min(
            eligible,
            key=lambda c: (
                mode_rank.get(c.mode, 999),
                c.semantic_loss,
                c.adaptation_cost,
                c.procedural_complexity,
                c.evidence_burden,
                c.ref.stable_key,
            ),
        )
        best_quality = min(
            eligible,
            key=lambda c: (
                c.semantic_loss,
                c.adaptation_cost,
                c.procedural_complexity,
                c.evidence_burden,
                mode_rank.get(c.mode, 999),
                c.ref.stable_key,
            ),
        )

        selected = preferred
        override: list[str] = []
        if best_quality.ref != preferred.ref:
            if preferred.semantic_loss - best_quality.semantic_loss >= policy.semantic_loss_override_threshold:
                override.append("semantic_loss")
            if preferred.adaptation_cost - best_quality.adaptation_cost >= policy.adaptation_cost_override_threshold:
                override.append("adaptation_cost")
            if preferred.procedural_complexity - best_quality.procedural_complexity >= policy.complexity_override_threshold:
                override.append("procedural_complexity")
            if preferred.evidence_burden - best_quality.evidence_burden >= policy.evidence_burden_override_threshold:
                override.append("evidence_burden")
            if override:
                selected = best_quality

        return ResolutionDecision(
            policy_ref=f"{policy.policy_id}@{policy.policy_version}",
            selected_capability_refs=(selected.ref,),
            eligible_candidates=tuple(c.ref.stable_key for c in eligible),
            rejected_candidates=tuple(rejected),
            selected_mode=selected.mode,
            override_of_default_preference=bool(override),
            override_basis=tuple(override),
            explanation=(
                "default REUSE→EXTEND→NEW preference overridden on material basis: " + ", ".join(override)
                if override
                else "selected by governed REUSE→EXTEND→NEW preference and deterministic tie-breaks"
            ),
        )
