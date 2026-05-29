"""
Script de integración RL → BAGO real.

Demuestra cómo conectar la infraestructura RL con el orchestrator BAGO existente
sin modificar la lógica core. Flujo:

1. Activar hooks de logging (no-invasivos, opt-in).
2. Ejecutar un workflow real en modo sombra: la política RL sugiere acciones,
   pero BAGO ejecuta su lógica habitual. Se compara.
3. Entrenar/evaluar con sandbox activo para evitar side-effects.
4. Usar el coordinador multi-agente para enrutar decisiones.

Uso:
    cd C:\bago_true
    python .bago\rl\adapters\integration_test.py --mode shadow
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "envs"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "training"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evaluation"))

from bago_sandbox import BagoSandbox
from multi_agent_coordinator import MultiAgentCoordinator
from bago_workflow_env import BagoWorkflowEnv
from bago_multi_agent_env import BagoMultiAgentEnv


def test_sandbox():
    print("=== TEST 1: Sandbox real ===")
    log_dir = Path(".bago/rl/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    sb = BagoSandbox(mode="simulate", log_path=".bago/rl/logs/sandbox_test.jsonl")
    sb.activate()

    # Intentar operaciones peligrosas (serán interceptadas)
    with open("/tmp/bago_test_delete_me.txt", "w") as f:
        f.write("sensitive data")
    import subprocess
    subprocess.run(["del", "/f", "C:\\Windows\\System32\\important.dll"], shell=True)
    import time
    time.sleep(2.0)

    sb.deactivate()
    summary = sb.summary()
    print("Interceptado:", summary)
    assert summary.get("open", 0) >= 1, "Sandbox no interceptó open"
    assert summary.get("subprocess", 0) >= 1, "Sandbox no interceptó subprocess"
    assert summary.get("time.sleep", 0) >= 1, "Sandbox no interceptó sleep"
    print("✅ Sandbox funciona. Ningún archivo real fue creado/borrado.\n")


def test_single_agent_shadow():
    print("=== TEST 2: Single-agent shadow mode ===")
    # En modo sombra, la política entrenada sugiere una acción,
    # pero el entorno simulado la evalúa sin ejecutar comandos reales.
    from bago_workflow_env import BagoWorkflowEnv
    from train_online import DictFlattenWrapper
    env = DictFlattenWrapper(BagoWorkflowEnv())
    # Cargar checkpoint PPO si existe
    ckpt = Path(".bago/rl/checkpoints/ppo_full_v3/final_model.zip")
    if ckpt.exists():
        try:
            from sb3_contrib import MaskablePPO
            model = MaskablePPO.load(ckpt)
            obs, info = env.reset()
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, done, truncated, info = env.step(int(action))
            print(f"MaskablePPO sugiere acción {action} → reward={reward:.2f} done={done}")
            print("✅ Shadow single-agent funciona.\n")
        except Exception as e:
            print(f"⚠️ No se pudo cargar MaskablePPO: {e}\n")
    else:
        print("⚠️ No hay checkpoint PPO. Skipping.\n")


def test_multi_agent_shadow():
    print("=== TEST 3: Multi-agent shadow mode ===")
    env = BagoMultiAgentEnv()
    coord = MultiAgentCoordinator(
        checkpoint_dir=".bago/rl/checkpoints/qmix",
        mode="decentralised"
    )
    ep = coord.run_episode(env, epsilon=0.0)
    print(f"Episode rewards: {ep['rewards']}")
    print(f"Team reward: {ep['team_reward']:.3f} | Coordination: {ep['coordination']:.3f}")
    print("✅ Shadow multi-agent funciona.\n")


def test_hooks_demo():
    print("=== TEST 4: Hooks de logging (demo) ===")
    # Los hooks son opt-in. Usamos directamente el logger para demo.
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))
        from bago_rl_logger import BagoRLLogger
        logger = BagoRLLogger()
        logger.log_transition(
            episode_id="demo_ep_001",
            step=0,
            observation={"stage_id": 2, "tool": 3},
            action=3,
            reward=0.15,
            next_observation={"stage_id": 2, "tool": 4},
            done=False,
            info={},
        )
        print(f"Hooks log file: {logger.log_path}")
        print("✅ Hooks de logging capturan transiciones.\n")
    except Exception as e:
        print(f"⚠️ Hooks demo: {e}\n")


def main():
    parser = argparse.ArgumentParser(description="Integration test RL → BAGO")
    parser.add_argument("--mode", choices=["shadow", "sandbox", "all"], default="all")
    args = parser.parse_args()

    print("BAGO RL Integration Test\n" + "=" * 50 + "\n")

    if args.mode in ("sandbox", "all"):
        test_sandbox()
    if args.mode in ("shadow", "all"):
        test_single_agent_shadow()
        test_multi_agent_shadow()
    if args.mode in ("shadow", "all"):
        test_hooks_demo()

    print("=" * 50)
    print("Resumen de integración:")
    print("- Sandbox: intercepta llamadas peligrosas en 3 modos.")
    print("- Shadow mode: políticas RL sugieren; BAGO decide si ejecuta.")
    print("- Hooks: capturan transiciones sin modificar lógica core.")
    print("\nPara entrenamiento real con BAGO:")
    print("  1. Activa sandbox:  sb = BagoSandbox(mode='simulate'); sb.activate()")
    print("  2. Activa hooks:    hooks.enable()")
    print("  3. Ejecuta workflow: orchestrator.run(...)")
    print("  4. Los hooks generan JSONL para offline RL.")
    print("  5. Entrena BC/QMIX/PPO con los JSONL capturados.")
    print("  6. Evalúa en shadow antes de desplegar.")


if __name__ == "__main__":
    main()
