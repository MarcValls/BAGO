"""
sim_startup_scenarios.py — Simulador de arranques peligrosos de BAGO
Ejecutar desde la raíz del repo:
    python tests/sim_startup_scenarios.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '.bago', 'tools'))

from bago.providers import load_providers, auto_detect_provider, get_default_model, scan_provider_health
from bago.credentials import CredentialManager
from bago.llm import _is_ollama_model_not_found, _is_ollama_unreachable

SEP  = "─" * 62
SEP2 = "═" * 62

# ── Helpers ────────────────────────────────────────────────────────────────────
BUGS = []

def bug(code, msg):
    BUGS.append((code, msg))
    print(f"  ⚠  BUG-{code}: {msg}")

def ok(msg):
    print(f"  ✔  OK: {msg}")

def info(msg):
    print(f"  ·  {msg}")

# ── Escenario 1: Sin ningún provider ──────────────────────────────────────────
def scenario_1_no_providers():
    print(f"\n[ E1 ] SIN TOKENS, SIN OLLAMA, MÁQUINA LIMPIA")
    print(SEP)

    # Guardar y limpiar env
    saved = {k: os.environ.pop(k, None) for k in [
        'GITHUB_TOKEN','GH_TOKEN','OPENAI_API_KEY',
        'ANTHROPIC_API_KEY','OPENROUTER_API_KEY','OLLAMA_HOST'
    ]}

    try:
        class _EmptyCreds:
            def active_bago_providers(self): return []

        providers = load_providers()
        creds = _EmptyCreds()
        active = creds.active_bago_providers()
        info(f"active_providers = {active}")

        # Replicar lógica de auto_detect_provider
        chosen = next(
            (p for p in ('ollama-local','copilot','codex','anthropic','ollama-cloud')
             if p in active and p in providers),
            next((n for n in providers if n in active), next(iter(providers), 'ollama-local'))
        )
        info(f"auto_detect → \"{chosen}\"")

        name, wire, prov = get_default_model(chosen, providers)
        info(f"get_default_model → name={name!r}")

        if not name:
            info("→ Panel 'No hay providers activos' + name='sin-modelo'")
            bug("SIM-1A", "Usuario escribe mensaje → chat('sin-modelo') → RuntimeError NO-Ollama → pe() sin recovery ni /login")
        else:
            info(f"→ Arranca con {prov}/{name} SIN verificar si funciona")
            bug("SIM-1B", f"Arranca con {prov}/{name} que no tiene credenciales → primer mensaje explota sin recovery")
    finally:
        for k, v in saved.items():
            if v is not None: os.environ[k] = v


# ── Escenario 2: Copilot token expirado en runtime ────────────────────────────
def scenario_2_expired_token():
    print(f"\n[ E2 ] COPILOT TOKEN VÁLIDO EN HEALTH SCAN, EXPIRADO EN RUNTIME")
    print(SEP)

    import litellm
    auth_errors = []
    for attr in dir(litellm):
        if any(w in attr.lower() for w in ['auth','credential','permission','unauthorized']):
            auth_errors.append(attr)
    info(f"litellm auth-errors: {auth_errors[:8]}")

    # Simular lo que lanza litellm con un 401
    class FakeAuthError(Exception):
        pass

    e_msg = "AuthenticationError: 401 Unauthorized - Invalid token"
    exc = RuntimeError(e_msg)
    is_ollama, _ = _is_ollama_model_not_found(exc)
    is_unreach    = _is_ollama_unreachable(exc)
    info(f"_is_ollama_model_not_found → {is_ollama}")
    info(f"_is_ollama_unreachable     → {is_unreach}")

    if not is_ollama and not is_unreach:
        bug("SIM-2A", "AuthenticationError (copilot 401) no activará recovery flow → pe() sin orientación")
    else:
        ok("Error de auth detectado correctamente")

    # Simular timeout / connection refused en cloud provider
    e_timeout = RuntimeError("APIConnectionError: Connection timed out reaching api.github.com")
    is_ollama2, _ = _is_ollama_model_not_found(e_timeout)
    is_unreach2    = _is_ollama_unreachable(e_timeout)
    info(f"ConnectionTimeout (cloud): is_ollama={is_ollama2}, is_unreach={is_unreach2}")
    if not is_ollama2 and not is_unreach2:
        bug("SIM-2B", "ConnectionTimeout en cloud provider → pe() sin recovery")


# ── Escenario 3: Health scan rojo en cloud, skip_providers no actualizado ──────
def scenario_3_health_scan_red_cloud():
    print(f"\n[ E3 ] HEALTH SCAN → COPILOT ROJO, PERO skip_providers NO SE ACTUALIZA")
    print(SEP)

    # Simular resultados del health scan (todos caídos)
    fake_health = {
        "ollama-local": {"ok": False, "detail": "no encontrado"},
        "copilot":      {"ok": False, "detail": "sin GITHUB_TOKEN"},
        "codex":        {"ok": False, "detail": "sin OPENAI_API_KEY"},
        "anthropic":    {"ok": False, "detail": "sin ANTHROPIC_API_KEY"},
        "openrouter":   {"ok": False, "detail": "sin OPENROUTER_API_KEY"},
    }

    # Código actual en bago_chat.py líneas 454-460:
    skip = set()
    _ol = fake_health.get("ollama-local", {})
    if _ol.get("ok") and _ol.get("url"):
        skip.discard("ollama-local")
        skip.discard("ollama-cloud")
    elif not _ol.get("ok"):
        skip.update({"ollama-local", "ollama-cloud"})

    info(f"skip_providers después del health scan: {skip}")

    # ¿Qué pasa con copilot/codex en rojo?
    for prov in ("copilot", "codex", "anthropic"):
        ph = fake_health.get(prov, {})
        if not ph.get("ok") and prov not in skip:
            bug("SIM-3A", f"\"{prov}\" en ROJO pero NO en skip_providers → auto_route() lo elegirá → error en runtime")
            break
    else:
        ok("Todos los providers rojos en skip_providers")

    # Caso adicional: solo copilot rojo con Ollama OK
    fake2 = {
        "ollama-local": {"ok": False, "detail": "no modelos"},
        "copilot":      {"ok": False, "detail": "token expirado (401)"},
    }
    skip2 = set()
    if not fake2["ollama-local"]["ok"]:
        skip2.update({"ollama-local","ollama-cloud"})
    info(f"Ollama rojo + Copilot rojo → skip_providers={skip2}")
    if "copilot" not in skip2:
        bug("SIM-3B", "Copilot rojo en health scan pero NO excluido → auto_route() redirige a copilot → falla")


# ── Escenario 4: Recovery exitoso pero retry también falla ────────────────────
def scenario_4_retry_also_fails():
    print(f"\n[ E4 ] RECOVERY EXITOSO PERO SEGUNDO CHAT() TAMBIÉN FALLA")
    print(SEP)

    # Simular flujo: _ollama_recovery_flow() → True (cambió a copilot)
    # Pero copilot también está caído → segundo chat() → RuntimeError
    # Código actual líneas 536-541 de bago_chat.py:
    #   except RuntimeError as e2:
    #       pe(str(e2))
    #   continue  ← vuelve al loop sin más recovery

    info("Flujo: chat() → Ollama error → recovery → copilot → retry chat() → RuntimeError(401)")
    info("Código actual: except RuntimeError as e2: pe(str(e2))  # sin recovery de 2do nivel")
    bug("SIM-4A", "Retry tras recovery falla con error cloud → pe() simple sin /login ni recovery de 2do nivel")


# ── Escenario 5: Ollama activo, auto_route lo elige, modelo no instalado ───────
def scenario_5_ollama_no_models_no_skip():
    print(f"\n[ E5 ] OLLAMA ACTIVO (SIN MODELOS) → skip_providers VACÍO → auto_route LO ELIGE")
    print(SEP)

    # Health scan dice: ollama ok (url existe pero 0 modelos)
    fake_health_5 = {
        "ollama-local": {"ok": True, "detail": "http://127.0.0.1:11434 — sin modelos instalados", "models": [], "url": "http://127.0.0.1:11434"},
        "copilot":      {"ok": False, "detail": "sin GITHUB_TOKEN"},
    }

    skip = set()
    _ol = fake_health_5.get("ollama-local", {})
    if _ol.get("ok") and _ol.get("url"):
        skip.discard("ollama-local")
        skip.discard("ollama-cloud")

    info(f"skip_providers = {skip}  (ollama OK con 0 modelos → no se añade a skip)")
    info("auto_route puede elegir ollama-local → chat() → 'model not found' → _ollama_recovery_flow")
    info("_ollama_recovery_flow: Ollama activo, sin modelos → menú install/other → OK")
    ok("Escenario 5 cubierto por _ollama_recovery_flow (menú install/other)")


# ── Escenario 6: Arranque con provider="none" y model="sin-modelo" ─────────────
def scenario_6_sin_modelo_chat():
    print(f"\n[ E6 ] CHAT CON provider='none' / model='sin-modelo'")
    print(SEP)

    info("Simulando: session.provider='none', session.wire_name='sin-modelo'")

    # Esto ocurre cuando name="sin-modelo" en líneas 419 de bago_chat.py
    # auto_route en session.py:
    # Si provider es 'none' → ¿qué hace auto_route()?
    from bago.session import BagoSession
    from bago.providers import load_providers
    creds_mock = type('C', (), {'active_bago_providers': lambda s: []})()
    try:
        sess = BagoSession("none", "sin-modelo", "sin-modelo", creds_mock)
        info(f"BagoSession creada: provider={sess.provider}, model={sess.model_name}")
        # ¿auto_route funciona?
        sess.autoroute = True
        try:
            result = sess.auto_route("Hola")
            info(f"auto_route('Hola') → {result}")
            if result[2] in ("none", "ollama-local") and result[0] == "sin-modelo":
                bug("SIM-6A", f"auto_route con sin-modelo devuelve provider inútil → litellm fallará sin recovery de Ollama")
        except Exception as e:
            bug("SIM-6B", f"auto_route lanza excepción con sin-modelo: {e}")
    except Exception as e:
        info(f"Error creando sesión: {e}")


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print(SEP2)
    print("  BAGO — SIMULADOR DE ARRANQUES SIN LLM")
    print(SEP2)

    scenario_1_no_providers()
    scenario_2_expired_token()
    scenario_3_health_scan_red_cloud()
    scenario_4_retry_also_fails()
    scenario_5_ollama_no_models_no_skip()
    scenario_6_sin_modelo_chat()

    print(f"\n{SEP2}")
    print(f"  RESUMEN: {len(BUGS)} bug(s) encontrado(s)")
    print(SEP2)
    for i, (code, msg) in enumerate(BUGS, 1):
        print(f"  {i}. [{code}] {msg}")
    print()


if __name__ == "__main__":
    main()
