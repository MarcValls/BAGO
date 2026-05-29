# BAGO Reinforcement Learning Integration

> Estado: Fase 0 y Fase 1 implementadas. Fase 2-4 planificadas.

## Estructura

```
.bago/rl/
├── envs/
│   ├── bago_bandit_env.py      # Entorno contextual bandit (Fase 1) ✅
│   └── bago_workflow_env.py    # Entorno MDP para workflows (Fase 3) 🔄
├── safety/
│   ├── action_masker.py         # Máscara de acciones inválidas (Fase 3)
│   └── validator.py             # Validador de seguridad (Fase 3)
├── training/
│   ├── train_bandit.py          # LinUCB training (Fase 1) ✅
│   ├── train_offline.py         # BCQ/CQL offline RL (Fase 2)
│   └── train_online.py          # MaskablePPO online (Fase 3)
├── evaluation/
│   ├── eval_policy.py           # Evaluación de políticas
│   └── ab_test.py               # A/B testing contra baseline
└── adapters/
    └── bago_client.py           # Cliente sandbox para entornos
```

## Fase 0 — Instrumentación ✅

- `bago_rl_logger.py`: Logger de transiciones en JSONL.
- `bago_rl_hooks.py`: Hooks no-invasivos para orchestrator, neural_toolbox, agent_router.

## Fase 1 — Contextual Bandits ✅

- `envs/bago_bandit_env.py`: Entorno Gymnasium para selección de herramienta.
- `training/train_bandit.py`: Implementación de LinUCB con save/load/eval.

### Uso rápido

```powershell
cd .bago/rl/training
python train_bandit.py --episodes 5000 --save policy_bandit.json
python train_bandit.py --eval policy_bandit.json --episodes 1000
```

### Métricas esperadas (demo, no real)

| Métrica | Valor |
|---|---|
| avg_reward | ~0.65-0.75 |
| success_rate | ~65-75% |

## Fase 2 — Offline RL 🔄

- Dataset: logs de Fase 0 en `.bago/logs/rl_transitions.jsonl`.
- Algoritmos: BCQ / CQL / Behavioral Cloning.
- Librería: Tianshou.

## Fase 3 — Sandbox MDP 🔄

- Entorno: `BagoWorkflowEnv` con curriculum learning.
- Algoritmo: MaskablePPO (SB3 Contrib).
- Sandbox: `BAGO_RL_SANDBOX=1` obligatorio.

## Fase 4 — Multi-Agent 🔄

- Condición: Fase 3 demuestra >20% mejora.
- Entorno: PettingZoo (AEC/Parallel).
- Algoritmos: QMIX / MADDPG.

## Seguridad

- Action masking en todo entrenamiento online.
- Validadores independientes antes de canary.
- Reward channels separados para detectar hacking.

## Referencias

- Plan completo: `.bago/docs/RL_INTEGRATION_PLAN.md`
- Base técnica: `F:\RL BAGO\IMPLEMENTAR RL BAGO.md`
