
from ..ui import _menu_input, _menu_select, pe, pi

def _cmd_auto(session):
    """Modo autonomo: toggle, nivel de confirmaciones, max iteraciones."""
    while True:
        auto_str = f"[green]ON[/green]" if session.autonomous else "[red]OFF[/red]"
        choices = [
            ("toggle",   f"Modo autonomo: {auto_str}  (toggle)"),
            ("confirm",  f"Nivel confirmaciones: [cyan]{session.auto_confirm}[/cyan]"),
            ("maxiter",  f"Max iteraciones: [cyan]{session.auto_max_iter}[/cyan]"),
            ("autoroute",f"Auto-routing: [cyan]{'ON' if session.autoroute else 'OFF'}[/cyan]"),
            ("__exit__", "Volver"),
        ]
        sel = _menu_select("BAGO / Modo Autonomo",
                           "Configura el comportamiento autonomo del orquestador:", choices)
        if sel is None or sel == "__exit__": break

        if sel == "toggle":
            session.autonomous = not session.autonomous
            state = "ACTIVADO" if session.autonomous else "DESACTIVADO"
            pi(f"Modo autonomo: {state}")
            if session.autonomous:
                pi("BAGO tomara decisiones sin pedir confirmacion (segun nivel configurado).")

        elif sel == "confirm":
            level = _menu_select("Nivel de confirmaciones",
                                 "Cuando pide confirmacion al usuario?",
                                 [("never",  "Nunca — completamente autonomo"),
                                  ("smart",  "Inteligente — solo en acciones de alto riesgo"),
                                  ("always", "Siempre — confirmar cada accion")])
            if level:
                session.auto_confirm = level
                pi(f"Nivel de confirmaciones: {level}")

        elif sel == "maxiter":
            val = _menu_input("Max iteraciones",
                              "Numero maximo de iteraciones en modo autonomo:",
                              default=str(session.auto_max_iter))
            if val:
                try:
                    session.auto_max_iter = int(val)
                    pi(f"Max iteraciones: {session.auto_max_iter}")
                except ValueError:
                    pe("Valor no valido.")

        elif sel == "autoroute":
            session.autoroute = not session.autoroute
            pi(f"Auto-routing: {'ON' if session.autoroute else 'OFF'}")
