"""bago.chat.startup_ui — selector de modo de inicio con curses."""


def _startup_choice_curses(stdscr):
    """Curses UI: el usuario elige Manual o Asistente. Devuelve 'manual' o 'asistente'."""
    import curses
    curses.curs_set(0)
    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN,  -1)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(3, curses.COLOR_WHITE, -1)
        curses.init_pair(4, curses.COLOR_BLACK, -1)

    # Detectar pen BAGO
    _pen = _detect_portable_drive()
    _infra = _load_infra_status()

    choices = [
        ("manual",    "  ⚙  Manual      bago menu",  "Navega el menú interactivo"),
        ("asistente", "  🤖  Asistente   chat IA",    "Habla directamente con BAGO"),
        ("create",    "  🎨  Creación    modo 3 paneles", "Layout tipo AI Studio para flujo de trabajo"),
        ("focus",     "  🎯  Enfoque     tarea activa",   "Panel minimalista de la tarea en curso"),
    ]

    if _pen:
        choices.insert(0, ("portable", f"  💾  Pen BAGO    {_pen}", "Arranca BAGO desde el pen drive"))
    else:
        choices.append(("portable", "  💾  Portable    crear en pen", "Crea instalación BAGO portable en pen drive"))

    if _infra and _infra.get("available"):
        svc_list = ", ".join(_infra["available"][:4])
        choices.append(("infra", f"  \U0001f310  Infra       {len(_infra['available'])} svcs", f"Servicios: {svc_list}"))
    else:
        choices.append(("infra", "  \U0001f310  Infra       escanear", "Escanea servicios de modelos en la red local"))
    sel   = 0
    BOX_W = 46

    def draw():
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        cx = max(0, (w - BOX_W) // 2)
        cy = max(0, (h - 10) // 2)

        badge = "◆ BAGO — Elige modo de inicio"
        bx = max(0, (w - len(badge)) // 2)
        attr = curses.color_pair(1) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD
        stdscr.addstr(cy, bx, badge, attr)

        border_attr = curses.color_pair(4) if curses.has_colors() else curses.A_DIM
        try:
            stdscr.addstr(cy + 2, cx, "┌" + "─" * (BOX_W - 2) + "┐", border_attr)
            for row in range(len(choices) * 2 + 1):
                stdscr.addstr(cy + 3 + row, cx, "│" + " " * (BOX_W - 2) + "│", border_attr)
            stdscr.addstr(cy + 3 + len(choices) * 2 + 1, cx,
                          "└" + "─" * (BOX_W - 2) + "┘", border_attr)
        except curses.error:
            pass

        for i, (key, label, hint) in enumerate(choices):
            row_y = cy + 3 + i * 2 + 1
            if i == sel:
                attr = (curses.color_pair(2) | curses.A_BOLD
                        if curses.has_colors() else curses.A_REVERSE | curses.A_BOLD)
                marker = "▶"
            else:
                attr   = curses.color_pair(3) if curses.has_colors() else curses.A_NORMAL
                marker = " "
            try:
                entry = f" {marker} {label:<{BOX_W - 6}} "
                stdscr.addstr(row_y, cx + 1, entry[:BOX_W - 2], attr)
            except curses.error:
                pass
            hint_attr = curses.color_pair(4) if curses.has_colors() else curses.A_DIM
            try:
                stdscr.addstr(row_y + 1, cx + 5, hint, hint_attr)
            except curses.error:
                pass

        footer = " ↑/↓  Mover    Enter  Confirmar    q  Salir "
        fy = min(h - 1, cy + 3 + len(choices) * 2 + 3)
        fx = max(0, (w - len(footer)) // 2)
        hint_attr = curses.color_pair(4) if curses.has_colors() else curses.A_DIM
        try:
            stdscr.addstr(fy, fx, footer, hint_attr)
        except curses.error:
            pass
        stdscr.refresh()

    while True:
        draw()
        key = stdscr.getch()
        if key in (curses.KEY_UP, ord('k')) and sel > 0:
            sel -= 1
        elif key in (curses.KEY_DOWN, ord('j')) and sel < len(choices) - 1:
            sel += 1
        elif key in (curses.KEY_ENTER, 10, 13):
            return choices[sel][0]
        elif key in (ord('q'), 27):
            return "manual"


def _chat_curses(stdscr):
    """Lanza el REPL prompt_toolkit desde dentro de un contexto curses."""
    import curses
    from bago_chat import main   # importación tardía para evitar ciclo
    curses.endwin()
    try:
        main()
    except SystemExit:
        pass
    return None
