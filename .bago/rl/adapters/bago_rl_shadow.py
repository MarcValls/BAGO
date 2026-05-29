#!/usr/bin/env python3
"""shadow_mode.py — Shadow Mode para RL en BAGO.

Recopila transiciones REALES del orquestador sin interferir con él.
El modelo BC entrenado hace predicciones en paralelo (shadow predictions)
para comparar con la decisión real del orquestador.

Uso:
    from bago_rl_shadow import ShadowMode
    shadow = ShadowMode()
    shadow.on_pre_chat(session, user_input)  # antes de chat_bridge
    # ... chat_bridge se ejecuta normalmente ...
    shadow.on_post_chat(session, result, exc, elapsed_sec)  # después de chat_bridge

Las transiciones se guardan en .bago/logs/rl_transitions_shadow.jsonl
y se pueden usar para reentrenar BC con:
    python .bago/rl/training/train_bc.py --input .bago/logs/rl_transitions_shadow.jsonl --epochs 20
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

TOOLS_DIR = Path(__file__).resolve().parent.parent
BAGO_ROOT = TOOLS_DIR.parent.parent
LOGS_DIR = BAGO_ROOT / ".bago" / "logs"
SHADOW_LOG = LOGS_DIR / "rl_transitions_shadow.jsonl"
CHECKPOINTS_DIR = BAGO_ROOT / ".bago" / "rl" / "checkpoints"

sys.path.insert(0, str(BAGO_ROOT / ".bago" / "rl"))
sys.path.insert(0, str(BAGO_ROOT / ".bago" / "rl" / "training"))

from train_bc import BCSimpleNN, _flatten_obs  # noqa: E402


class ShadowMode:
    """Shadow mode: predice en paralelo, loguea transiciones reales."""

    def __init__(self, model_path: Path | None = None):
        if model_path:
            self.model_path = model_path
        else:
            # Busca el mejor modelo disponible: router > user > synthetic
            candidates = [
                CHECKPOINTS_DIR / "bc_router" / "bc_model.pkl",
                CHECKPOINTS_DIR / "bc_user" / "bc_model.pkl",
                CHECKPOINTS_DIR / "bc_synthetic.pt",
            ]
            self.model_path = next((c for c in candidates if c.exists()), candidates[0])
        self.net: BCSimpleNN | None = None
        self.action_map: dict[int, str] = {}
        self._load_model()
        self._pending: dict[str, Any] | None = None
        self._total_logged = 0

    def _load_model(self) -> None:
        """Carga el modelo BC entrenado."""
        if not self.model_path.exists():
            print(f"[Shadow] Modelo no encontrado: {self.model_path}. Shadow mode sin predicciones.")
            return
        try:
            self.net = BCSimpleNN.load(self.model_path)
            print(f"[Shadow] Modelo BC cargado: {self.model_path}")
        except Exception as exc:
            print(f"[Shadow] Error cargando modelo: {exc}")

    def _build_obs(self, session, user_input: str) -> dict[str, Any]:
        """Construye la observación del estado actual del sistema."""
        prov = getattr(session, "provider", "none")
        model = getattr(session, "model_name", "sin-modelo")
        autoroute = getattr(session, "autoroute", False)
        local_lock = getattr(session, "local_lock", False)
        switches = getattr(session, "switches", 0)
        mode = getattr(session, "orch_mode", "standard")
        input_len = len(user_input)
        has_code = any(k in user_input.lower() for k in ("code", "script", "función", "funcion", "class", "debug", "refactor"))
        has_long = input_len > 100

        return {
            "provider": prov,
            "model": model,
            "autoroute": 1.0 if autoroute else 0.0,
            "local_lock": 1.0 if local_lock else 0.0,
            "switches": float(switches),
            "mode": mode,
            "input_len": float(input_len),
            "has_code": 1.0 if has_code else 0.0,
            "has_long": 1.0 if has_long else 0.0,
        }

    def _encode_action(self, provider: str, model: str) -> str:
        """Codifica la acción como string."""
        return f"{provider}/{model}"

    def predict(self, session, user_input: str) -> str | None:
        """Predice la acción recomendada por el modelo BC."""
        if self.net is None:
            return None
        obs = self._build_obs(session, user_input)
        x = _flatten_obs(obs).reshape(1, -1)
        pred_idx = int(self.net.predict(x)[0])
        # Invertir action_to_idx para obtener idx -> action
        idx_to_action = {v: k for k, v in getattr(self.net, "action_to_idx", {}).items()}
        return idx_to_action.get(pred_idx, str(pred_idx))

    def on_pre_chat(self, session, user_input: str) -> None:
        """Llamar ANTES de chat_bridge. Captura el estado inicial."""
        if not os.environ.get("BAGO_RL_SHADOW", "").lower() in ("1", "true", "yes"):
            return
        obs = self._build_obs(session, user_input)
        shadow_pred = self.predict(session, user_input)
        self._pending = {
            "obs": obs,
            "shadow_pred": shadow_pred,
            "start_time": time.time(),
            "user_input": user_input[:200],
        }

    def on_post_chat(self, session, result: str | None, exc: Exception | None, elapsed_sec: float) -> None:
        """Llamar DESPUÉS de chat_bridge. Calcula recompensa y loguea."""
        if self._pending is None:
            return
        pending = self._pending
        self._pending = None

        # Acción real tomada
        real_provider = getattr(session, "provider", "none")
        real_model = getattr(session, "model_name", "sin-modelo")
        action = self._encode_action(real_provider, real_model)

        # Calcular recompensa basada en resultado real
        reward = self._compute_reward(result, exc, elapsed_sec)

        # Transición
        transition = {
            "episode_id": f"shadow_{int(time.time())}",
            "step": self._total_logged,
            "observation": pending["obs"],
            "action": action,
            "reward": reward,
            "done": False,
            "info": {
                "shadow_pred": pending.get("shadow_pred"),
                "elapsed_sec": round(elapsed_sec, 2),
                "user_input": pending["user_input"],
                "exc_type": type(exc).__name__ if exc else None,
                "result_len": len(result) if result else 0,
            },
        }

        self._append_transition(transition)
        self._total_logged += 1
        print(f"  [dim][Shadow] logged: action={action} reward={reward:.2f}[/dim]")

    def _compute_reward(self, result: str | None, exc: Exception | None, elapsed_sec: float) -> float:
        """Calcula recompensa basada en el resultado real de la interacción."""
        if exc is not None:
            exc_name = type(exc).__name__
            if "Auth" in exc_name or "Authentication" in exc_name or "BadRequest" in exc_name:
                return -1.0
            if "RateLimit" in exc_name or "rate" in str(exc).lower():
                return -0.8
            if "Timeout" in exc_name or "timeout" in str(exc).lower():
                return -0.5
            if "Connection" in exc_name or "ConnectionError" in exc_name:
                return -0.3
            return -0.2  # Error genérico de API

        # Sin error: respuesta exitosa
        reward = 1.0
        if result and len(result) > 500:
            reward += 0.2  # Respuesta larga y completa
        if elapsed_sec < 3.0:
            reward += 0.1  # Respuesta rápida
        return reward

    def _append_transition(self, transition: dict[str, Any]) -> None:
        """Append JSONL al log de shadow mode."""
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with SHADOW_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(transition, ensure_ascii=False) + "\n")


# Singleton global
_shadow_instance: ShadowMode | None = None


def get_shadow() -> ShadowMode:
    """Obtiene la instancia singleton de ShadowMode."""
    global _shadow_instance
    if _shadow_instance is None:
        _shadow_instance = ShadowMode()
    return _shadow_instance
