
import datetime
import json
from pathlib import Path

from ..constants import BAGO_SYSTEM, SESSIONS_DIR
from ..ui import _menu_action, _menu_confirm, _menu_select, pe, pi

def _cmd_session(session):
    """Gestión de sesiones: temporal, disco, sync, repliegue."""
    while True:
        temp_label = "[TEMP]" if session.temp_mode else "[DISK]"
        choices = [
            ("new_temp",  f"Nueva sesion temporal {temp_label}  (RAM only, sin guardar automaticamente)"),
            ("load",      "Cargar sesion desde disco"),
            ("list",      "Listar sesiones guardadas"),
            ("save_now",  "Guardar sesion ahora"),
            ("export",    "Exportar sesion como Markdown"),
            ("toggle_temp", f"Modo {'DISCO (desactivar temporal)' if session.temp_mode else 'TEMPORAL (activar)'}"),
        ]
        sel = _menu_select("BAGO / Sesion", f"Sesion activa: {len(session.history)-1} msgs  |  modo: {temp_label}", choices)
        if sel is None: break

        if sel == "toggle_temp":
            session.temp_mode = not session.temp_mode
            label = "TEMPORAL (RAM only)" if session.temp_mode else "DISCO (guardado automatico)"
            pi(f"Modo sesion: {label}")

        elif sel == "save_now":
            path = session.save()
            pi(f"Guardado: {path}")

        elif sel == "new_temp":
            if _menu_confirm("Nueva sesion", "Esto limpiara el historial actual. Continuar?"):
                session.history = [{"role": "system", "content": BAGO_SYSTEM}]
                session.temp_mode = True
                session.started_at = datetime.datetime.now()
                pi("Nueva sesion temporal iniciada. Historial limpio.")

        elif sel == "list":
            _session_list()

        elif sel == "load":
            _session_load(session)

        elif sel == "export":
            _session_export(session)

def _session_list():
    sdir = SESSIONS_DIR
    if not sdir.exists():
        pi("No hay sesiones guardadas todavia."); return
    files = sorted(sdir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        pi("No hay sesiones guardadas."); return
    choices = []
    for f in files[:20]:
        try:
            d = json.loads(f.read_text(encoding="utf-8-sig"))
            ts  = d.get("timestamp", f.stem)[:16]
            model = d.get("model", "?")
            msgs  = len(d.get("history", [])) - 1
            choices.append((str(f), f"{ts}  [{model}]  {msgs} msgs"))
        except Exception:
            choices.append((str(f), f.name))
    sel = _menu_select("Sesiones guardadas", "Sesiones recientes (las 20 ultimas):", choices)
    if sel:
        _menu_action(f"Sesion: {Path(sel).name}", f"Ruta: {sel}", [("Cerrar","ok")])

def _session_load(session):
    sdir = SESSIONS_DIR
    if not sdir.exists() or not list(sdir.glob("*.json")):
        pi("No hay sesiones guardadas."); return
    files = sorted(sdir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    choices = []
    for f in files[:20]:
        try:
            d = json.loads(f.read_text(encoding="utf-8-sig"))
            ts  = d.get("timestamp", f.stem)[:16]
            model = d.get("model", "?")
            msgs  = len(d.get("history", [])) - 1
            choices.append((str(f), f"{ts}  [{model}]  {msgs} msgs"))
        except Exception:
            choices.append((str(f), f.name))
    sel = _menu_select("Cargar sesion", "Selecciona una sesion:", choices)
    if not sel: return
    try:
        d = json.loads(Path(sel).read_text(encoding="utf-8-sig"))
        hist = d.get("history", [])
        if not hist:
            pe("Sesion vacia."); return
        if _menu_confirm("Cargar sesion", f"Cargar {len(hist)-1} msgs? Se sobreescribira el historial actual."):
            session.history = hist
            if d.get("model") and d.get("provider"):
                session.switch_model(d["model"], silent=True)
            pi(f"Sesion cargada: {len(hist)-1} mensajes.")
    except Exception as e:
        pe(f"Error cargando sesion: {e}")

def _session_export(session):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    export_path = SESSIONS_DIR / f"export_{ts}.md"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# BAGO Session Export — {ts}\n",
             f"**Modelo:** {session.model_name} ({session.provider})\n",
             f"**Mensajes:** {len(session.history)-1}\n\n---\n"]
    for msg in session.history:
        role = msg["role"]
        if role == "system": continue
        prefix = "**Usuario:**" if role == "user" else f"**{session.model_name}:**"
        lines.append(f"\n{prefix}\n\n{msg['content']}\n\n---\n")
    export_path.write_text("".join(lines), encoding="utf-8")
    pi(f"Exportado: {export_path}")
