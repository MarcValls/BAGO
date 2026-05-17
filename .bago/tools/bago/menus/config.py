
import json

from ..constants import USER_BAGO
from ..ui import _menu_input, _menu_pick, _toggle_menu, pi

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
    """Configuracion global -- se persiste en ~/.bago/bago_chat_config.json."""
    cfg = _load_config()

    while True:
        result = _toggle_menu(
            "BAGO / Config",
            "Configuracion global (se guarda en ~/.bago/bago_chat_config.json).\n"
            "Espacio/Enter: conmutar o seleccionar.   Esc: salir sin guardar.",
            [
                {"type": "toggle", "key": "autoroute",
                 "label": "Auto-routing",
                 "value": cfg.get("autoroute", True)},
                {"type": "toggle", "key": "autonomous",
                 "label": "Modo autonomo",
                 "value": cfg.get("autonomous", False)},
                {"type": "toggle", "key": "temp_mode",
                 "label": "Sesion temporal (sin historial persistente)",
                 "value": cfg.get("temp_mode", False)},
                {"type": "sep"},
                {"type": "action", "key": "auto_confirm",
                 "label": f"Nivel de confirmacion:  {cfg.get('auto_confirm','smart')}"},
                {"type": "action", "key": "auto_max",
                 "label": f"Max iteraciones:        {cfg.get('auto_max_iter', 10)}"},
                {"type": "action", "key": "orch_mode",
                 "label": f"Modo orquestador:       {cfg.get('orch_mode','estandar')}"},
                {"type": "action", "key": "sync_after",
                 "label": f"Post-sync:              {cfg.get('sync_after','continuar')}"},
                {"type": "sep"},
                {"type": "action", "key": "apply",
                 "label": "Aplicar y guardar configuracion"},
            ],
        )

        # Recoger cambios de los toggles en cfg
        for key in ("autoroute", "autonomous", "temp_mode"):
            if key in result["toggles"]:
                cfg[key] = result["toggles"][key]

        action = result["action"]

        if action is None:
            # Esc: salir sin guardar
            break

        elif action == "apply":
            _save_config(cfg)
            session.autoroute     = cfg.get("autoroute", True)
            session.autonomous    = cfg.get("autonomous", False)
            session.auto_confirm  = cfg.get("auto_confirm", "smart")
            session.auto_max_iter = cfg.get("auto_max_iter", 10)
            session.orch_mode     = cfg.get("orch_mode", "estandar")
            session.sync_after    = cfg.get("sync_after", "continuar")
            session.temp_mode     = cfg.get("temp_mode", False)
            pi("Config guardada y aplicada a la sesion actual.")
            break

        elif action == "auto_confirm":
            v = _menu_pick(
                "Nivel de confirmacion",
                "Cuando debe BAGO pedir confirmacion al usuario?",
                [
                    ("never",  "Nunca       -- decisiones completamente autonomas"),
                    ("smart",  "Inteligente -- solo ante acciones irreversibles"),
                    ("always", "Siempre     -- confirmar cada paso"),
                ],
            )
            if v:
                cfg["auto_confirm"] = v

        elif action == "auto_max":
            v = _menu_input(
                "Max iteraciones",
                "Numero maximo de pasos autonomos antes de pausar:",
                default=str(cfg.get("auto_max_iter", 10)),
            )
            if v:
                try:
                    cfg["auto_max_iter"] = int(v)
                except ValueError:
                    pass

        elif action == "orch_mode":
            v = _menu_pick(
                "Modo orquestador",
                "Selecciona el modo de orquestacion:",
                [
                    ("offline",   "Offline   -- solo modelos locales"),
                    ("economico", "Economico -- prioriza modelos de bajo coste"),
                    ("estandar",  "Estandar  -- balance coste/calidad"),
                    ("full",      "Full      -- maxima calidad, sin restricciones"),
                ],
            )
            if v:
                cfg["orch_mode"] = v

        elif action == "sync_after":
            v = _menu_pick(
                "Post-sync",
                "Comportamiento de BAGO tras una sincronizacion:",
                [
                    ("continuar", "Continuar -- sigue la sesion normalmente"),
                    ("repliegue", "Repliegue -- reduce actividad autonoma"),
                    ("letargo",   "Letargo   -- modo de minimo consumo"),
                ],
            )
            if v:
                cfg["sync_after"] = v
