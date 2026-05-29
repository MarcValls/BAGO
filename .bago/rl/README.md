# BAGO Reinforcement Learning Integration

> Estado: Fase 0 y Fase 1 implementadas. Fase 2-4 planificadas.

## Estructura

```
.bago/rl/
├── envs/
│   ├── bago_bandit_env.py      # Entorno contextual bandit (Fase 1) ✅
│   ├── bago_tool_env.py         # Entorno RL para tool orchestrator (Fase 5) ✅
│   └── bago_workflow_env.py    # Entorno MDP para workflows (Fase 3) 🔄
├── safety/
│   ├── action_masker.py         # Máscara de acciones inválidas (Fase 3)
│   └── validator.py             # Validador de seguridad (Fase 3)
├── training/
│   ├── policies.py              # LinUCB + BC Policy classes ✅
│   ├── training.py              # train_bandit / train_bc / evaluate ✅
│   ├── train_tool_orchestrator.py  # CLI entry point (Fase 5) ✅
│   ├── train_offline.py         # BCQ/CQL offline RL (Fase 2)
│   └── train_online.py          # MaskablePPO online (Fase 3)
├── evaluation/
│   ├── eval_policy.py           # Evaluación de políticas
│   └── ab_test.py               # A/B testing contra baseline
├── adapters/
│   ├── orchestrator/            # Paquete modular del tool orchestrator ✅
│   │   ├── __init__.py
│   │   ├── tool_schemas.py      # Esquemas JSON de las 5 herramientas
│   │   ├── tool_runner.py       # Ejecución de herramientas vía subprocess
│   │   ├── ollama_client.py     # Wrapper de la API /api/chat de Ollama
│   │   ├── rl_logger.py         # Logger de transiciones + recompensa
│   │   └── core.py              # Loop principal de orquestación
│   └── bago_tool_orchestrator.py  # CLI entry point (Fase 5) ✅
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

## Fase 5 — Tool Orchestrator (LLM local aprende a usar herramientas BAGO) ✅

### Estructura modular

```
adapters/orchestrator/
├── __init__.py           # Exports públicos
├── tool_schemas.py       # 5 esquemas JSON para Ollama tool-calling
├── tool_runner.py        # Ejecuta herramientas vía subprocess (list, read, search...)
├── ollama_client.py      # Wrapper de /api/chat con soporte tool_calls
├── rl_logger.py          # Loggea transiciones y calcula recompensa
└── core.py               # Loop principal: prompt → LLM → tool → resultado → log

training/
├── policies.py           # LinUCBPolicy + BCPolicy (numpy puro, ~5B friendly)
├── training.py           # train_bandit, train_bc, evaluate_policy
└── train_tool_orchestrator.py  # CLI entry point (~40 líneas)
```

### Flujo

```
Usuario describe tarea → LLM elige herramienta → Orquestador ejecuta →
Resultado vuelve al LLM → Loggea transición → Entrena política RL
```

### Uso rápido

```powershell
# 1. Ejecutar orquestador interactivo con modelo ligero
python .bago\rl\adapters\bago_tool_orchestrator.py --model qwen2.5:1.5b --interactive

# 2. Entrenar política desde transiciones loggeadas
python .bago\rl\training\train_tool_orchestrator.py --mode bc --epochs 30

# 3. Evaluar
python .bago\rl\training\train_tool_orchestrator.py --eval --checkpoint .bago\rl\checkpoints\tool_policy_bc.json
```

## Seguridad

- Action masking en todo entrenamiento online.
- Validadores independientes antes de canary.
- Reward channels separados para detectar hacking.
- Modelo local ≤5B ejecuta 100% offline; cero datos salen del equipo.

## Referencias

- Plan completo: `.bago/docs/RL_INTEGRATION_PLAN.md`
- Base técnica: `F:\RL BAGO\IMPLEMENTAR RL BAGO.md`
