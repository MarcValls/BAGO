from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / ".bago" / "core")]


def test_affirmative_creation_request_remains_work_intent():
    from intent_engine import classify_intent

    assert classify_intent("Quiero crear una aplicación") == "work"
    assert classify_intent("¿Puedes crear una aplicación sencilla?") == "work"


def test_negated_creation_is_not_action_authority():
    from intent_engine import classify_intent

    assert classify_intent("No quiero crear una app") == "chat"
    assert classify_intent("No necesito crear una aplicación") == "chat"


def test_question_about_creation_is_not_creation_authority():
    from intent_engine import classify_intent

    assert classify_intent("¿Por qué quiero crear una app?") == "chat"
    assert classify_intent("¿Para qué crear una aplicación?") == "chat"
