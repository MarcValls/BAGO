import sys
from pathlib import Path

import json

from ..constants import USER_BAGO
from ..ui import _menu_input, _menu_pick, _toggle_menu, pi

_CONFIG_FILE = USER_BAGO / "bago_chat_config.json"
_DEFAULT_CONFIG = {
    "autoroute": True,
    "autonomous": False,
    "auto_confirm": "adaptativo",
    "auto_max_iter": 10,
    "orch_mode": "standard",
    "sync_after": "continuar",
    "temp_mode": False,
    "banner": True,
}
_CONFIRM_ALIASES = {"smart": "adaptativo"}
_MODE_ALIASES = {"economico": "eco", "estandar": "standard"}


def _normalize_config(cfg):
    out = dict(_DEFAULT_CONFIG)
    if isinstance(cfg, dict):
        out.update(cfg)
    out["auto_confirm"] = _CONFIRM_ALIASES.get(out.get("auto_confirm"), out.get("auto_confirm", "adaptativo"))
    out["orch_mode"] = _MODE_ALIASES.get(out.get("orch_mode"), out.get("orch_mode", "standard"))
    return out


def _load_config():
    if _CONFIG_FILE.exists():
        try:
            return _normalize_config(json.loads(_CONFIG_FILE.read_text(encoding="utf-8-sig")))
        except Exception:
            pass
    return dict(_DEFAULT_CONFIG)


def _save_config(cfg):
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps(_normalize_config(cfg), indent=2, ensure_ascii=False), encoding="utf-8")


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
                 "label": f"Nivel de confirmacion:  {cfg.get('auto_confirm', 'adaptativo')}"},
                {"type": "action", "key": "auto_max",
                 "label": f"Max iteraciones:        {cfg.get('auto_max_iter', 10)}"},
                {"type": "action", "key": "orch_mode",
                 "label": f"Modo orquestador:       {cfg.get('orch_mode', 'standard')}"},
                {"type": "action", "key": "sync_after",
                 "label": f"Post-sync:              {cfg.get('sync_after', 'continuar')}"},
                {"type": "sep"},
                {"type": "action", "key": "apply",
                 "label": "Aplicar y guardar configuracion"},
            ],
        )

        for key in ("autoroute", "autonomous", "temp_mode"):
            if key in result["toggles"]:
                cfg[key] = result["toggles"][key]

        action = result["action"]

        if action is None:
            break

        elif action == "apply":
            cfg = _normalize_config(cfg)
            _save_config(cfg)
            session.autoroute = cfg.get("autoroute", True)
            session.autonomous = cfg.get("autonomous", False)
            session.auto_confirm = cfg.get("auto_confirm", "adaptativo")
            session.auto_max_iter = cfg.get("auto_max_iter", 10)
            session.orch_mode = cfg.get("orch_mode", "standard")
            session.sync_after = cfg.get("sync_after", "continuar")
            session.temp_mode = cfg.get("temp_mode", False)
            pi("Config guardada y aplicada a la sesion actual.")
            break

        elif action == "auto_confirm":
            v = _menu_pick(
                "Nivel de confirmacion",
                "Cuando debe BAGO pedir confirmacion al usuario?",
                [
                    ("never", "Nunca       -- decisiones completamente autonomas"),
                    ("adaptativo", "Adaptativo  -- ajusta autonomia segun contexto y riesgo"),
                    ("balanceado", "Balanceado  -- equilibrio entre autonomia y supervision"),
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
                    ("offline", "Offline   -- solo modelos locales"),
                    ("eco", "Eco       -- prioriza modelos rapidos y de bajo coste"),
                    ("standard", "Standard  -- balance coste/calidad"),
                    ("full", "Full      -- maxima calidad, sin restricciones"),
                    ("auto", "Auto      -- BAGO decide segun contexto y complejidad"),
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
                    ("letargo", "Letargo   -- modo de minimo consumo"),
                ],
            )
            if v:
                cfg["sync_after"] = v


def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(f"{Path(__file__).name} --test: PASS (imports OK)")
    return 0
if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
