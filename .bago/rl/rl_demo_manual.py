#!/usr/bin/env python3
"""rl_demo_manual.py — Demo manual del pipeline RL para BAGO.

Ejecuta un mini-workflow simulado que activa hooks + sandbox + logger,
demostrando que todo el pipeline RL funciona antes de usar BAGO real.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Paths
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".bago" / "tools"))
sys.path.insert(0, str(ROOT / ".bago" / "rl" / "adapters"))

# Activar instrumentación
os.environ["BAGO_RL_INSTRUMENTATION"] = "1"

from bago_rl_hooks import auto_instrument
from bago_rl_logger import BagoRLLogger
from bago_sandbox import BagoSandbox

def main() -> int:
    print("[RL-Demo] Activando sandbox + hooks...")
    sb = BagoSandbox(mode="simulate")
    sb.activate()

    # Simular un mini pipeline de 3 pasos
    logger = BagoRLLogger()
    for step, (tool, success, elapsed) in enumerate([
        ("lint", True, 5.0),
        ("build", True, 12.0),
        ("test", False, 30.0),
    ]):
        obs = {"stage": step, "tool": tool}
        action = f"run_{tool}"
        reward = 1.0 if success else -0.5
        next_obs = {"stage": step + 1, "tool": tool, "rc": 0 if success else 1}
        logger.log_transition(
            episode_id="demo_pipeline_001",
            step=step,
            observation=obs,
            action=action,
            reward=reward,
            next_observation=next_obs,
            done=(step == 2),
            info={"elapsed": elapsed, "success": success},
        )
        print(f"  Step {step}: {tool} → reward={reward:.1f} done={step==2}")

    sb.deactivate()
    logger.flush()

    log_path = logger.log_path
    if log_path.exists():
        count = sum(1 for _ in open(log_path, "r", encoding="utf-8"))
        print(f"\n✅ [RL-Demo] {count} transiciones guardadas en {log_path}")
    else:
        print(f"\n❌ [RL-Demo] No se creó el archivo de log.")
        return 1

    print("\n[RL-Demo] Ahora puedes entrenar con:")
    print(f'  python .bago\\rl\\training\\train_bc.py --input {log_path} --epochs 10')
    return 0


if __name__ == "__main__":
    sys.exit(main())
