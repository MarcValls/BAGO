from pathlib import Path

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from ..ui import _menu_input, _menu_pick, _toggle_menu, pe, pi

_CONFIRM_LABELS = {
    "never":      "Completamente autonomo (nunca pide confirmacion)",
    "adaptativo": "Adaptativo (ajusta autonomia segun contexto y riesgo)",
    "balanceado": "Balanceado (equilibra autonomia y supervision)",
    "always":     "Conservador (confirma cada accion antes de ejecutar)",
}

def _cmd_auto(session):
    """Modo autonomo: conmutadores ON/OFF + nivel de confirmaciones + max iteraciones."""

    while True:
        confirm_txt = _CONFIRM_LABELS.get(session.auto_confirm, session.auto_confirm)

        result = _toggle_menu(
            "BAGO / Modo Autonomo",
            "Espacio/Enter: conmutar o seleccionar.   Esc: volver al chat.",
            [
                {"type": "toggle", "key": "autonomous", "label": "Modo autonomo",
                 "value": session.autonomous},
                {"type": "toggle", "key": "autoroute",  "label": "Auto-routing",
                 "value": session.autoroute},
                {"type": "sep"},
                {"type": "action", "key": "confirm",
                 "label": f"Nivel de autonomia: {confirm_txt}"},
                {"type": "action", "key": "maxiter",
                 "label": f"Maximo de iteraciones: {session.auto_max_iter}"},
            ],
        )

        action = result["action"]

        # R4/R5: Esc (action is None) = descartar cambios, salir
        if action is None:
            break

        # Solo aplicar cambios de toggles cuando el usuario elige una accion
        # (no en Esc — ver R4: Esc no guarda nada)
        if result["toggles"].get("autonomous") != session.autonomous:
            session.autonomous = result["toggles"]["autonomous"]
            pi(f"Modo autonomo: {'ACTIVADO' if session.autonomous else 'DESACTIVADO'}")
            if session.autonomous:
                pi(f"  - Nivel actual: {confirm_txt}")
                pi(f"  - Max iteraciones: {session.auto_max_iter}")

        if result["toggles"].get("autoroute") != session.autoroute:
            session.autoroute = result["toggles"]["autoroute"]
            pi(f"Auto-routing: {'ACTIVADO' if session.autoroute else 'DESACTIVADO'}")

        if action == "confirm":
            level = _menu_pick(
                "Nivel de autonomia",
                f"Nivel actual: {confirm_txt}\n\n"
                "Cuando debe BAGO pedir confirmacion al usuario?",
                [
                    ("never", "Nunca       -- decisiones completamente autonomas"),
                    ("adaptativo", "Adaptativo  -- ajusta autonomia segun contexto y riesgo"),
                    ("balanceado", "Balanceado  -- equilibrio entre autonomia y supervision"),
                    ("always", "Siempre     -- confirmar cada paso antes de ejecutar"),
                ],
            )
            if level and level != session.auto_confirm:
                session.auto_confirm = level
                pi(f"Nivel de autonomia: {_CONFIRM_LABELS[level]}")

        elif action == "maxiter":
            val = _menu_input(
                "Maximo de iteraciones",
                f"Numero maximo de pasos que BAGO ejecuta de forma autonoma\n"
                f"antes de pausar y pedir revision.\n\n"
                f"Valor actual: {session.auto_max_iter}",
                default=str(session.auto_max_iter),
            )
            if val is not None:
                try:
                    nuevo = int(val)
                    if nuevo < 1:
                        pe("El minimo es 1.")
                    else:
                        session.auto_max_iter = nuevo
                        pi(f"Maximo de iteraciones: {session.auto_max_iter}")
                except ValueError:
                    pe("Valor no valido -- introduce un numero entero.")


def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(f"{Path(__file__).name} --test: PASS (imports OK)")
    return 0
if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
