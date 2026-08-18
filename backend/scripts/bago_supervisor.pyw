#!/usr/bin/env pythonw
"""Wrapper silencioso para arrancar el supervisor sin consola (sin parpadeo).
Se ejecuta con pythonw.exe en lugar de python.exe: no abre ventana CMD.
El supervisor escribe su log en la raíz mutable de usuario de BAGO.
"""
import sys
import os

# Forzar UTF-8 por si acaso
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# Importar el módulo del supervisor (está en el mismo dir que este .pyw)
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

try:
    import bago_supervisor
except Exception as e:
    # Si falla, escribimos a un archivo de error para diagnóstico (sin ventana)
    err = os.path.join(os.environ.get("LOCALAPPDATA") or os.environ.get("USERPROFILE", "."), "BAGO", "state", "supervisor_silent.err")
    try:
        os.makedirs(os.path.dirname(err), exist_ok=True)
        with open(err, "a", encoding="utf-8") as f:
            import datetime
            f.write(f"[{datetime.datetime.now().isoformat()}] import error: {e!r}\n")
    except Exception:
        pass
    raise SystemExit(1)

raise SystemExit(bago_supervisor.main())
