from __future__ import annotations

import pytest

from integrations.pi.identity_paths import artifact_component


def test_artifact_component_is_injective_for_protocol_ids() -> None:
    assert artifact_component("exec-1") == "exec-1"
    assert artifact_component("exec:1") != artifact_component("exec1")
    assert artifact_component("a.b") != artifact_component("ab")


@pytest.mark.parametrize("identity", [".", "..", "CON", "Lpt1", "", "x" * 129, "bad/name"])
def test_artifact_component_encodes_or_rejects_special_components(identity: str) -> None:
    if identity in {"", "x" * 129, "bad/name"}:
        with pytest.raises(ValueError):
            artifact_component(identity)
        return
    component = artifact_component(identity)
    assert component not in {".", ".."}
    assert component.upper() not in {"CON", "LPT1"}
