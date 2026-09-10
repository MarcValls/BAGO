from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / ".bago" / "core"))


def test_first_substantive_work_turn_seeds_session_goal():
    from session_turn_mixin import SessionTurnMixin

    class Store:
        def __init__(self):
            self.meta = {}

        def update_meta(self, values):
            self.meta.update(values)

    class Session(SessionTurnMixin):
        def __init__(self):
            self.persistent_goal = ""
            self.store = Store()

        def set_goal(self, value):
            self.persistent_goal = value.strip()

    session = Session()
    captured = session._capture_conversational_goal(
        "Quiero crear una aplicación sencilla para organizar mis ideas.",
        "work",
    )

    assert captured is True
    assert session.persistent_goal.startswith("Quiero crear una aplicación")
    assert session.store.meta["persistent_goal"] == session.persistent_goal


def test_short_confirmation_does_not_replace_existing_goal():
    from session_turn_mixin import SessionTurnMixin

    class Session(SessionTurnMixin):
        persistent_goal = "Crear la aplicación de ideas"

    session = Session()
    assert session._capture_conversational_goal("Sí, confirmo", "work") is False
    assert session.persistent_goal == "Crear la aplicación de ideas"


def test_reflexive_interpretation_is_rendered_as_advisory_model_context():
    from session_turn_mixin import SessionTurnMixin

    block = SessionTurnMixin._reflexive_prompt_block({
        "intent": "implementar",
        "operational_intent": "execute",
        "formalization": {"objective": "crear una aplicación"},
        "restrictions": [{"kind": "constraint", "value": "preservar la API"}],
        "unknowns": [{"kind": "missing", "value": "ruta"}],
        "confidence": 0.74,
        "metrics": {"ambiguity": 0.25},
    })

    assert "BAGO OPERATIONAL INTENT" in block
    assert '"operational_intent": "execute"' in block
    assert "original user message remains authoritative" in block
    assert "preservar la API" in block
