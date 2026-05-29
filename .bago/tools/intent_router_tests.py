"""Tests focalizados para intent_router.py."""

from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso


def run_tests(api: dict) -> int:
    identify_intents = api["identify_intents"]
    score_intent = api["score_intent"]
    resolve_intent = api["resolve_intent"]
    load_intents = api["load_intents"]

    results = []
    loaded_intents = load_intents()

    intents = identify_intents("mi código tiene passwords hardcodeados")
    ok1 = len(intents) > 0 and intents[0][1]["id"] == "security_check"
    results.append(("intent_router:security_intent", ok1,
                     f"top={intents[0][1]['id'] if intents else 'none'}"))

    intents = identify_intents("quiero hacer merge y push a producción")
    ok2 = len(intents) > 0 and intents[0][1]["id"] == "pre_merge"
    results.append(("intent_router:merge_intent", ok2,
                     f"top={intents[0][1]['id'] if intents else 'none'}"))

    intents = identify_intents("las funciones son muy largas y complejas")
    ok3 = len(intents) > 0 and intents[0][1]["id"] == "complexity_check"
    results.append(("intent_router:complexity_intent", ok3,
                     f"top={intents[0][1]['id'] if intents else 'none'}"))

    intents = identify_intents("xyz123 nada relevante aquí")
    ok4 = len(intents) == 0
    results.append(("intent_router:no_match", ok4, f"count={len(intents)}"))

    s = score_intent("secretos y passwords", loaded_intents[0])
    ok5 = isinstance(s, int) and s > 0
    results.append(("intent_router:score_positive", ok5, f"score={s}"))

    required = {"id", "name", "triggers", "tools", "description"}
    ok6 = all(required.issubset(intent.keys()) for intent in loaded_intents)
    results.append(("intent_router:intents_schema_valid", ok6,
                     f"intents={len(loaded_intents)}"))

    intents = identify_intents("quiero hacer un proyecto en ableton")
    ok7 = len(intents) > 0 and intents[0][1]["id"] == "ableton_project"
    results.append(("intent_router:ableton_intent", ok7,
                     f"top={intents[0][1]['id'] if intents else 'none'}"))

    intents = identify_intents("nuevo proyecto python sin PR aún")
    ok8 = len(intents) == 0 or intents[0][1]["id"] != "pre_merge"
    results.append(("intent_router:pr_no_false_positive", ok8,
                     f"top={intents[0][1]['id'] if intents else 'none'}"))

    plan = resolve_intent("mi código tiene passwords hardcodeados")
    ok9 = plan.get("matched") and plan.get("intent") == "security_check" and plan.get("rewrite")
    results.append(("intent_router:resolve_rewrite", ok9,
                     f"intent={plan.get('intent')} rewrite={bool(plan.get('rewrite'))}"))

    plan = resolve_intent("reparar framework y registrar tool automáticamente")
    ok10 = plan.get("intent") == "self_heal" and plan.get("requires_confirmation") is True
    results.append(("intent_router:resolve_destructive_gate", ok10,
                     f"intent={plan.get('intent')} confirm={plan.get('requires_confirmation')}"))

    plan = resolve_intent("dejar modelos o servicios enteros desactivados para que BAGO ni se acuerde")
    ok11 = plan.get("intent") == "idea_feature_config_provider_disable"
    results.append(("intent_router:provider_disable_idea", ok11,
                     f"intent={plan.get('intent')}"))

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  {status}  {name}: {detail}")
    print(f"\n  {passed}/{len(results)} pasaron")
    return 0 if failed == 0 else 1
