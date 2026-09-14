"""Compatibility facade for versioned provider routing policy."""

from bago_core.providers.routing import (
    EquivalenceMap,
    ModelSpec,
    TransferStrategy,
    TransferVerdict,
)

__all__ = ["EquivalenceMap", "ModelSpec", "TransferStrategy", "TransferVerdict"]


def _run_tests() -> int:
    policy = EquivalenceMap()
    assert policy.get_tier("gpt-5.4") == "tier_1_frontier"
    assert policy.get_tier("qwen25-coder") == "tier_2_everyday"
    assert policy.can_transfer("gpt-5.4", "claude-sonnet-4.6")
    assert policy.can_transfer("gpt-5.4", "qwen25-coder", strict=False)
    assert not policy.can_transfer("gpt-5.4", "qwen25-coder", strict=True)
    assert not policy.can_transfer("qwen25-mini", "gpt-5.4")
    assert "llama32" in policy.find_equivalents("qwen25-coder")
    assert policy.get_spec("unknown-model") is None
    print("model_equivalence.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
