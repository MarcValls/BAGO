#!/usr/bin/env python3
"""bago_rl_hooks.py — Hooks no-invasivos para instrumentar BAGO con RL.

Fase 0 del plan de integración de RL.
Estos hooks se activan automáticamente si BAGO_RL_INSTRUMENTATION=1
o si existe `.bago/state/rl_instrumentation.json` con `"enabled": true`.

Diseño:
  - Wrappers funcionales: envuelven métodos clave sin modificar su código fuente.
  - Opt-in: sin activación explícita, BAGO funciona exactamente igual.
  - Zero-cost cuando están desactivados: los wrappers devuelven la función original.

Uso manual:
    from bago_rl_hooks import instrument_orchestrator, instrument_neural_toolbox
    instrument_orchestrator()   # una vez al inicio del proceso
    instrument_neural_toolbox() # una vez al inicio del proceso

Códigos: RL-H001 (instrumentación OK), RL-H002 (ya instrumentado), RL-H003 (error)
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

TOOLS_DIR = Path(__file__).resolve().parent
BAGO_ROOT = TOOLS_DIR.parent
STATE_DIR = BAGO_ROOT / "state"
CONFIG_FILE = STATE_DIR / "rl_instrumentation.json"

# Estado global de instrumentación
_instrumented: set[str] = set()
_episode_id: str | None = None
_step_counters: dict[str, int] = {}


def _is_enabled() -> bool:
    """Determina si la instrumentación RL está activada."""
    if os.environ.get("BAGO_RL_INSTRUMENTATION", "").lower() in ("1", "true", "yes"):
        return True
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return bool(cfg.get("enabled", False))
        except Exception:
            pass
    return False


def _get_logger() -> Any | None:
    """Lazy import del logger para evitar dependencia circular."""
    try:
        from bago_rl_logger import BagoRLLogger
        return BagoRLLogger()
    except Exception as e:
        print(f"[RL-Hooks] Warning: no se pudo cargar BagoRLLogger: {e}", file=sys.stderr)
        return None


def _ensure_episode(module_name: str) -> str:
    """Genera o recupera el episode_id para este módulo."""
    global _episode_id
    if _episode_id is None:
        _episode_id = str(uuid.uuid4())
        _step_counters[module_name] = 0
    return _episode_id


def _log_transition(
    module: str,
    obs: dict[str, Any],
    action: str | int,
    reward: dict[str, float] | float,
    next_obs: dict[str, Any],
    done: bool,
    info: dict[str, Any],
) -> None:
    """Loguea una transición si está habilitado."""
    if not _is_enabled():
        return
    logger = _get_logger()
    if logger is None:
        return
    ep_id = _ensure_episode(module)
    step = _step_counters.get(module, 0)
    logger.log_transition(ep_id, step, obs, action, reward, next_obs, done, info)
    _step_counters[module] = step + 1


# ── Wrappers por componente ─────────────────────────────────────────────────


def _wrap_method(obj: Any, method_name: str, wrapper: Callable) -> None:
    """Envuelve un método de instancia o clase de forma no destructiva."""
    original = getattr(obj, method_name, None)
    if original is None:
        return
    if getattr(original, "_rl_wrapped", False):
        return

    def wrapped(*args, **kwargs):
        return wrapper(original, *args, **kwargs)

    wrapped._rl_wrapped = True          # type: ignore[attr-defined]
    wrapped._rl_original = original     # type: ignore[attr-defined]
    setattr(obj, method_name, wrapped)


def _unwrap_method(obj: Any, method_name: str) -> None:
    """Restaura el método original."""
    current = getattr(obj, method_name, None)
    if current is None:
        return
    original = getattr(current, "_rl_original", None)
    if original:
        setattr(obj, method_name, original)


# ── Orchestrator hooks ────────────────────────────────────────────────────


def _orchestrator_run_tool_wrapper(original, self, *args, **kwargs):
    """Wrapper alrededor de orchestrator.run_tool() y run_workflow()."""
    # run_tool(cmd, dry_run=False, timeout=90)
    cmd_arg = args[0] if args else kwargs.get("cmd", "unknown")
    dry_run = kwargs.get("dry_run", False) if len(args) < 2 else args[1]
    obs = {
        "component": "orchestrator",
        "cmd": str(cmd_arg),
        "dry_run": bool(dry_run),
        "context": getattr(self, "_workflow_name", "ad-hoc"),
    }
    result = original(self, *args, **kwargs)
    next_obs = {
        "component": "orchestrator",
        "cmd": str(cmd_arg),
        "rc": result.get("rc", -1),
        "elapsed": result.get("elapsed", 0.0),
    }
    reward = {
        "success": 1.0 if result.get("rc") == 0 else 0.0,
        "latency_penalty": -0.1 * min(result.get("elapsed", 0.0) / 60.0, 1.0),
    }
    _log_transition(
        module="orchestrator",
        obs=obs,
        action=str(cmd_arg),
        reward=reward,
        next_obs=next_obs,
        done=False,
        info={"rc": result.get("rc"), "elapsed": result.get("elapsed")},
    )
    return result


def instrument_orchestrator() -> bool:
    """Instrumenta el orquestador si está disponible y no instrumentado ya."""
    if "orchestrator" in _instrumented:
        return True
    try:
        spec = __import__("importlib.util").util.spec_from_file_location(
            "_orchestrator_mod", str(TOOLS_DIR / "orchestrator.py")
        )
        mod = __import__("importlib.util").util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # Envolvemos las funciones run_tool y run_workflow a nivel de módulo
        if hasattr(mod, "run_tool"):
            original = mod.run_tool
            def wrapped(*args, **kwargs):
                return _orchestrator_run_tool_wrapper(original, None, *args, **kwargs)
            wrapped._rl_wrapped = True  # type: ignore[attr-defined]
            wrapped._rl_original = original  # type: ignore[attr-defined]
            mod.run_tool = wrapped
        _instrumented.add("orchestrator")
        print("[RL-Hooks] Orchestrator instrumentado.")
        return True
    except Exception as e:
        print(f"[RL-Hooks] Error instrumentando orchestrator: {e}", file=sys.stderr)
        return False


# ── Neural Toolbox hooks ──────────────────────────────────────────────────


def _neural_toolbox_activate_wrapper(original, self, *args, **kwargs):
    """Wrapper alrededor de NeuralToolbox.activate()."""
    context_text = args[0] if args else kwargs.get("context_text", "")
    obs = {
        "component": "neural_toolbox",
        "context_length": len(str(context_text)),
        "top_n": kwargs.get("top_n", 6) if not args else (args[3] if len(args) > 3 else 6),
    }
    activations = original(self, *args, **kwargs)
    actions = [a.cmd for a in activations] if activations else []
    next_obs = {
        "component": "neural_toolbox",
        "num_activated": len(activations),
        "top_score": round(activations[0].score, 4) if activations else 0.0,
    }
    reward = {
        "num_activated": 0.1 * len(activations),
        "top_score": next_obs["top_score"],
    }
    _log_transition(
        module="neural_toolbox",
        obs=obs,
        action=",".join(actions) if actions else "none",
        reward=reward,
        next_obs=next_obs,
        done=False,
        info={"context": str(context_text)[:80]},
    )
    return activations


def instrument_neural_toolbox() -> bool:
    """Instrumenta NeuralToolbox si está disponible."""
    if "neural_toolbox" in _instrumented:
        return True
    try:
        spec = __import__("importlib.util").util.spec_from_file_location(
            "_neural_toolbox_mod", str(TOOLS_DIR / "neural_toolbox.py")
        )
        mod = __import__("importlib.util").util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "NeuralToolbox"):
            _wrap_method(
                mod.NeuralToolbox, "activate",
                lambda original, self, *args, **kwargs: _neural_toolbox_activate_wrapper(original, self, *args, **kwargs)
            )
        _instrumented.add("neural_toolbox")
        print("[RL-Hooks] NeuralToolbox instrumentado.")
        return True
    except Exception as e:
        print(f"[RL-Hooks] Error instrumentando neural_toolbox: {e}", file=sys.stderr)
        return False


# ── Agent Router hooks ────────────────────────────────────────────────────


def _agent_router_resolve_wrapper(original, self, *args, **kwargs):
    """Wrapper alrededor de agent_router.resolve() o similar."""
    # No sabemos la firma exacta; hacemos un wrapper genérico
    task_text = kwargs.get("task", "") if kwargs else (args[0] if args else "")
    obs = {
        "component": "agent_router",
        "task_length": len(str(task_text)),
    }
    result = original(self, *args, **kwargs)
    next_obs = {
        "component": "agent_router",
        "result_type": type(result).__name__,
    }
    reward = {
        "resolution": 1.0 if result is not None else 0.0,
    }
    _log_transition(
        module="agent_router",
        obs=obs,
        action=str(result) if result else "none",
        reward=reward,
        next_obs=next_obs,
        done=False,
        info={"task": str(task_text)[:80]},
    )
    return result


def instrument_agent_router() -> bool:
    """Instrumenta agent_router si está disponible."""
    if "agent_router" in _instrumented:
        return True
    try:
        spec = __import__("importlib.util").util.spec_from_file_location(
            "_agent_router_mod", str(TOOLS_DIR / "agent_router.py")
        )
        mod = __import__("importlib.util").util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # Buscamos la clase principal
        for name in dir(mod):
            obj = getattr(mod, name)
            if isinstance(obj, type) and "router" in name.lower():
                if hasattr(obj, "resolve"):
                    _wrap_method(
                        obj, "resolve",
                        lambda original, self, *args, **kwargs: _agent_router_resolve_wrapper(original, self, *args, **kwargs)
                    )
                break
        _instrumented.add("agent_router")
        print("[RL-Hooks] AgentRouter instrumentado.")
        return True
    except Exception as e:
        print(f"[RL-Hooks] Error instrumentando agent_router: {e}", file=sys.stderr)
        return False


# ── Auto-instrumentación ──────────────────────────────────────────────────


def auto_instrument() -> None:
    """Intenta instrumentar todos los componentes conocidos si está habilitado."""
    if not _is_enabled():
        return
    instrument_orchestrator()
    instrument_neural_toolbox()
    instrument_agent_router()


# Si se importa directamente y está habilitado, auto-instrumentar
auto_instrument()


# ── CLI ───────────────────────────────────────────────────────────────────

def main() -> int:
    print(f"[RL-Hooks] Instrumentación habilitada: {_is_enabled()}")
    print(f"[RL-Hooks] Componentes instrumentados: {_instrumented}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
