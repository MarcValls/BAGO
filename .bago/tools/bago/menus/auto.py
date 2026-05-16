
from ..ui import _menu_input, _menu_select, _menu_confirm, pe, pi

# Descripciones legibles para el nivel de confirmaciones
_CONFIRM_LABELS = {
    "never":  "Completamente autónomo (nunca pide confirmación)",
    "smart":  "Inteligente (solo en acciones de alto riesgo)",
    "always": "Conservador (confirma cada acción antes de ejecutar)",
}

def _cmd_auto(session):
    """Modo autónomo: toggle, nivel de confirmaciones, max iteraciones."""

    auto_icon   = "✔ ON" if session.autonomous else "✘ OFF"
    route_icon  = "✔ ON" if session.autoroute  else "✘ OFF"
    confirm_txt = _CONFIRM_LABELS.get(session.auto_confirm, session.auto_confirm)

    choices = [
        ("toggle",
         f"{'Desactivar' if session.autonomous else 'Activar'} modo autónomo  [{auto_icon}]"),
        ("confirm",
         f"Nivel de autonomía: {confirm_txt}"),
        ("maxiter",
         f"Máximo de iteraciones autónomas: {session.auto_max_iter}"),
        ("autoroute",
         f"{'Desactivar' if session.autoroute else 'Activar'} auto-routing  [{route_icon}]"),
    ]

    sel = _menu_select(
        "BAGO / Modo Autónomo",
        "Selecciona el ajuste que quieres cambiar.\n"
        "Pulsa Cancelar o Escape para volver al chat.",
        choices,
        cancel_label="Cerrar",
    )

    # Cancelar / Escape → salir sin cambios
    if sel is None:
        return

    if sel == "toggle":
        session.autonomous = not session.autonomous
        state = "ACTIVADO" if session.autonomous else "DESACTIVADO"
        pi(f"Modo autónomo: {state}")
        if session.autonomous:
            nivel = _CONFIRM_LABELS.get(session.auto_confirm, session.auto_confirm)
            pi(f"  · Nivel actual: {nivel}")
            pi(f"  · Max iteraciones: {session.auto_max_iter}")

    elif sel == "confirm":
        level = _menu_select(
            "Nivel de autonomía",
            f"Nivel actual: {confirm_txt}\n\n"
            "¿Cuándo debe BAGO pedir confirmación al usuario?",
            [
                ("never",  "Nunca       — decisiones completamente autónomas"),
                ("smart",  "Inteligente — solo ante acciones irreversibles o de riesgo"),
                ("always", "Siempre     — confirmar cada paso antes de ejecutar"),
            ],
            cancel_label="Cancelar (sin cambios)",
        )
        if level and level != session.auto_confirm:
            session.auto_confirm = level
            pi(f"Nivel de autonomía establecido: {_CONFIRM_LABELS[level]}")
        elif level == session.auto_confirm:
            pi("Sin cambios (ya estaba en ese nivel).")

    elif sel == "maxiter":
        val = _menu_input(
            "Máximo de iteraciones",
            f"Número máximo de pasos que BAGO ejecuta de forma autónoma\n"
            f"antes de pausar y pedir revisión.\n\n"
            f"Valor actual: {session.auto_max_iter}",
            default=str(session.auto_max_iter),
        )
        if val is not None:
            try:
                nuevo = int(val)
                if nuevo < 1:
                    pe("El mínimo es 1.")
                else:
                    session.auto_max_iter = nuevo
                    pi(f"Máximo de iteraciones: {session.auto_max_iter}")
            except ValueError:
                pe("Valor no válido — introduce un número entero.")

    elif sel == "autoroute":
        session.autoroute = not session.autoroute
        pi(f"Auto-routing: {'ACTIVADO' if session.autoroute else 'DESACTIVADO'}")
