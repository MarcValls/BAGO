from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / ".bago" / "core")]


def test_affirmative_creation_request_remains_work_intent():
    from intent_engine import classify_intent

    assert classify_intent("Quiero crear una aplicación") == "work"
    assert classify_intent("¿Puedes crear una aplicación sencilla?") == "work"
    assert classify_intent("Crea una app, ¿vale?") == "work"
    assert classify_intent("¿Me creas una app?") == "work"
    assert classify_intent("¿Crear una app nueva, por favor?") == "work"


def test_negated_creation_is_not_action_authority():
    from intent_engine import classify_command_intent, classify_intent

    assert classify_intent("No quiero crear una app") == "chat"
    assert classify_intent("No necesito crear una aplicación") == "chat"
    assert classify_intent("No voy a crear una app") == "chat"
    assert classify_intent("Nunca quiero crear una app") == "chat"
    assert classify_intent("No ejecutes el plan") == "chat"
    assert classify_command_intent("No ejecutes el plan") is None


def test_question_about_creation_is_not_creation_authority():
    from intent_engine import classify_command_intent, classify_intent

    assert classify_intent("¿Por qué quiero crear una app?") == "chat"
    assert classify_intent("¿Para qué crear una aplicación?") == "chat"
    assert classify_intent("¿Debo crear una app?") == "chat"
    assert classify_intent("¿Conviene ejecutar el plan?") == "chat"
    assert classify_command_intent("¿Debo ejecutar el plan?") is None


def test_affirmative_clause_after_negation_keeps_explicit_authority():
    from intent_engine import classify_intent

    assert classify_intent("No la revises, crea una app nueva") == "work"
    assert classify_intent("No abras eso y crea una app nueva") == "work"


def test_incidental_sin_and_explanation_question_do_not_invert_stance():
    from intent_engine import classify_intent

    assert classify_intent("Sin duda crea una app") == "work"
    assert classify_intent("¿Puedes explicarme cómo crear una app?") == "chat"
    assert classify_intent("Explícame cómo crear una app") == "chat"
    assert classify_intent("Quiero saber cómo crear una app") == "chat"


def test_negated_cessation_preserves_continue_work_intent():
    from intent_engine import classify_intent

    assert classify_intent("No quiero dejar de crear la app") == "work"
