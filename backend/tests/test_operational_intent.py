from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_operational_intent_separates_intent_operation_product_and_acceptance():
    from operational_intent import OperationalIntent

    spec = OperationalIntent(
        source="Corrige el parser y genera un informe",
        intent="obtener una corrección entregable",
        operation="transformar y documentar",
        product="parser corregido e informe",
        constraints=("preservar la API pública",),
        acceptance=("pruebas pasan", "informe generado"),
    )

    assert spec.to_dict()["intent"] != spec.to_dict()["operation"]
    assert spec.to_dict()["product"] == "parser corregido e informe"
    assert spec.to_dict()["acceptance"] == ["pruebas pasan", "informe generado"]


def test_operational_intent_round_trip_normalizes_collections():
    from operational_intent import OperationalIntent

    spec = OperationalIntent.from_dict({
        "source": "revisa el código",
        "intent": "revisión",
        "operation": "revisar",
        "context": [" backend ", "", 42],
        "constraints": None,
        "acceptance": [" evidencia ", " "],
    })

    assert spec.context == ("backend", "42")
    assert spec.constraints == ()
    assert spec.acceptance == ("evidencia",)
    assert OperationalIntent.from_dict(spec.to_dict()) == spec


@pytest.mark.parametrize(
    ("interpreted_intent", "operation", "product"),
    [
        ("review", "revisar", "hallazgos y evidencia de revisión"),
        ("execute", "ejecutar", "resultado de ejecución"),
        ("work", "transformar", "cambio materializado"),
        ("general", "interpretar", "resultado de interpretación"),
    ],
)
def test_derived_operational_intent_is_conservative(
    interpreted_intent, operation, product
):
    from operational_intent import derive_operational_intent

    spec = derive_operational_intent(
        "petición",
        interpreted_intent=interpreted_intent,
        acceptance=["evidence available"],
    )

    assert spec.operation == operation
    assert spec.product == product
    assert spec.lifecycle_state == "PROPOSED"
    assert spec.acceptance == ("evidence available",)


def test_operational_intent_rejects_invalid_lifecycle_state():
    from operational_intent import OperationalIntent

    with pytest.raises(ValueError, match="invalid lifecycle state"):
        OperationalIntent(
            source="x",
            intent="y",
            operation="z",
            lifecycle_state="DONE",
        )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("corrige el parser", "update_resource"),
        ("genera un informe", "create_resource"),
        ("ejecuta las pruebas", "execution"),
        ("revisa el código", "general"),
    ],
)
def test_interpretation_detects_operational_spanish_verbs(text, expected):
    from handlers_interpretations import _detect_intent

    assert _detect_intent(text) == expected


def test_derived_operational_intent_preserves_explicit_user_specification():
    from operational_intent import derive_operational_intent

    spec = derive_operational_intent(
        "corrige el código y genera un ZIP validado",
        interpreted_intent="work",
        operation="corregir, empaquetar y validar",
        product="ZIP validado",
        context=["workspace", "backend"],
        constraints=["no tocar credenciales"],
        acceptance=["build PASS", "ZIP abre correctamente"],
    )

    assert spec.operation == "corregir, empaquetar y validar"
    assert spec.product == "ZIP validado"
    assert spec.context == ("workspace", "backend")
    assert spec.constraints == ("no tocar credenciales",)
    assert spec.acceptance == ("build PASS", "ZIP abre correctamente")
