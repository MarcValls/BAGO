
import json

from ..constants import USER_BAGO
from ..ui import _menu_input, _menu_select, pi

_CONFIG_FILE = USER_BAGO / "bago_chat_config.json"

def _load_config():
    if _CONFIG_FILE.exists():
        try:
            return json.loads(_CONFIG_FILE.read_text(encoding="utf-8-sig"))
        except Exception:
            pass
    return {"autoroute": True, "autonomous": False, "auto_confirm": "smart",
            "auto_max_iter": 10, "orch_mode": "estandar", "sync_after": "continuar",
            "temp_mode": False, "banner": True}

def _save_config(cfg):
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

def _cmd_config(session):
    """Configuracion global — se persiste en ~/.bago/bago_chat_config.json."""
    cfg = _load_config()
    while True:
        choices = [
            ("autoroute",   f"Auto-routing:        [cyan]{cfg.get('autoroute', True)}[/cyan]"),
            ("autonomous",  f"Modo autonomo:       [cyan]{cfg.get('autonomous', False)}[/cyan]"),
            ("auto_confirm",f"Nivel confirmacion:  [cyan]{cfg.get('auto_confirm','smart')}[/cyan]"),
            ("auto_max",    f"Max iteraciones:     [cyan]{cfg.get('auto_max_iter', 10)}[/cyan]"),
            ("orch_mode",   f"Modo orquestador:    [cyan]{cfg.get('orch_mode','estandar')}[/cyan]"),
            ("sync_after",  f"Post-sync:           [cyan]{cfg.get('sync_after','continuar')}[/cyan]"),
            ("temp_mode",   f"Sesion temporal:     [cyan]{cfg.get('temp_mode', False)}[/cyan]"),
            ("apply",       "[bold green]Aplicar y guardar configuracion[/bold green]"),
        ]
        field = _menu_select("BAGO / Config",
                             "Configuracion global (se guarda en ~/.bago/bago_chat_config.json):",
                             choices)
        if field is None: break

        if field == "apply":
            _save_config(cfg)
            # Aplicar a la sesion actual
            session.autoroute    = cfg.get("autoroute", True)
            session.autonomous   = cfg.get("autonomous", False)
            session.auto_confirm = cfg.get("auto_confirm", "smart")
            session.auto_max_iter= cfg.get("auto_max_iter", 10)
            session.orch_mode    = cfg.get("orch_mode", "estandar")
            session.sync_after   = cfg.get("sync_after", "continuar")
            session.temp_mode    = cfg.get("temp_mode", False)
            pi("Config guardada y aplicada a la sesion actual.")
            break

        elif field == "autoroute":
            cfg["autoroute"] = not cfg.get("autoroute", True)
        elif field == "autonomous":
            cfg["autonomous"] = not cfg.get("autonomous", False)
        elif field == "auto_confirm":
            v = _menu_select("Nivel confirmacion", "Cuando confirmar:",
                             [("never","Nunca"),("smart","Inteligente"),("always","Siempre")])
            if v: cfg["auto_confirm"] = v
        elif field == "auto_max":
            v = _menu_input("Max iteraciones", "Numero:", default=str(cfg.get("auto_max_iter",10)))
            if v:
                try: cfg["auto_max_iter"] = int(v)
                except: pass
        elif field == "orch_mode":
            v = _menu_select("Modo orquestador", "Selecciona:",
                             [("offline","offline"),("economico","economico"),
                              ("estandar","estandar"),("full","full")])
            if v: cfg["orch_mode"] = v
        elif field == "sync_after":
            v = _menu_select("Post-sync", "Comportamiento tras sync:",
                             [("continuar","Continuar"),("repliegue","Repliegue"),("letargo","Letargo")])
            if v: cfg["sync_after"] = v
        elif field == "temp_mode":
            cfg["temp_mode"] = not cfg.get("temp_mode", False)
