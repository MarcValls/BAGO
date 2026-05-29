# Workflow de Usuario: BAGO + RL en Producción

> Guía paso a paso para **ti** (usuario de BAGO) para aprovechar el sistema RL que acabamos de construir.

---

## Resumen del flujo

```
[1] Instrumentar → [2] Colectar datos reales → [3] Entrenar offline
        ↓
[4] Evaluar en shadow → [5] Canary 5% → [6] Despliegue 100%
        ↓
[7] Activar MARL (4 agentes cooperativos)
```

---

## FASE 1: Instrumentar tu BAGO real (5 min)

Activa los hooks para que BAGO capture transiciones automáticamente.

```powershell
# Windows
$env:BAGO_RL_INSTRUMENTATION = "1"

# O permanente: crea el archivo de estado
python -c "import json; json.dump({'enabled':True}, open('.bago/state/rl_instrumentation.json','w'))"
```

A partir de ahora, **cada vez que ejecutes BAGO**, se generan logs en:
```
.bago/logs/rl_transitions.jsonl
```

---

## FASE 2: Ejecutar BAGO normalmente (1-3 días)

Usa BAGO como siempre. Ejemplos de tareas que generan datos valiosos:

```powershell
# Pipeline multi-modelo (gran fuente de datos RL)
bago pipeline "refactorizar módulo de autenticación"

# Ciclo de build/test (secuencias de herramientas)
bago build
bago test
bago lint

# Tareas complejas con recuperación de errores
bago deploy
bago knowledge sync
```

> **Tip**: Mientras más variedad de tareas ejecutes, mejor aprenderá el modelo.

---

## FASE 3: Entrenar con tus datos reales (30 min)

Cuando tengas al menos **200 transiciones** (compruébalo):

```powershell
cd C:\bago_true
python .bago\rl\training\train_bc.py --input .bago\logs\rl_transitions.jsonl --epochs 20
```

Si quieres entrenar PPO online (más potente):
```powershell
python .bago\rl\training\train_online.py --checkpoint-dir .bago\rl\checkpoints\ppo_user
```

---

## FASE 4: Evaluar en modo Sombra (Shadow) (10 min)

La política sugiere acciones pero **BAGO decide si ejecutarlas**. Cero riesgo.

```powershell
python .bago\rl\adapters\integration_test.py --mode shadow
```

Si las métricas son ≥ 85%, avanza a canary.

---

## FASE 5: Canary — 5% de tráfico real (1 día)

Activa el modo canary para que el RL ejecute el 5% de las acciones:

```powershell
# En tu script de arranque de BAGO, o antes de ejecutar
$env:BAGO_RL_MODE = "canary"
$env:BAGO_RL_CANARY_RATIO = "0.05"
```

O modifica tu script de pipeline:
```python
from bago_rl_hooks import BagoRLHooks
hooks = BagoRLHooks()
hooks.enable_canary(ratio=0.05)  # 5% de acciones ejecutadas por RL
```

Monitorea:
```powershell
python .bago\rl\evaluation\evaluate_online.py --checkpoint .bago\rl\checkpoints\ppo_user\final_model.zip
```

---

## FASE 6: Despliegue 100% — Single Agent (cuando estés listo)

Cuando el canary muestre ≥ 90% de mejora:

```powershell
$env:BAGO_RL_MODE = "full"
```

El agente PPO ahora sugiere/optimiza el orden de herramientas y parámetros.

---

## FASE 7: Multi-Agent (MARL) — 4 agentes cooperativos (avanzado)

Para tareas complejas donde múltiples decisiones ocurren en paralelo:

```powershell
# Cargar el coordinador QMIX entrenado
python .bago\rl\training\multi_agent_coordinator.py --checkpoint-dir .bago\rl\checkpoints\qmix --mode centralised
```

Agentes:
- **planner**: decide qué herramientas activar
- **executor**: ajusta parámetros y timeouts
- **validator**: comprueba resultados intermedios
- **recoverer**: gestiona errores y retries

Ejecuta evaluación:
```powershell
python .bago\rl\evaluation\multi_agent_metrics.py --checkpoint-dir .bago\rl\checkpoints\qmix --episodes 50
```

---

## Cheat sheet rápido

| Quiero... | Comando |
|---|---|
| Verificar que todo funciona | `python .bago\rl\adapters\integration_test.py --mode all` |
| Ver cuántos datos he recolectado | `(Get-Content .bago\logs\rl_transitions.jsonl).Count` |
| Entrenar BC con mis datos | `python .bago\rl\training\train_bc.py --input .bago\logs\rl_transitions.jsonl` |
| Entrenar PPO online | `python .bago\rl\training\train_online.py` |
| Evaluar política entrenada | `python .bago\rl\evaluation\evaluate_online.py --checkpoint ...` |
| Activar sandbox seguro | `python -c "from bago_sandbox import BagoSandbox; BagoSandbox('simulate').activate()"` |
| Ver métricas MARL | `python .bago\rl\evaluation\multi_agent_metrics.py` |

---

## Flujo recomendado para tu primer semana

**Día 1**: Instrumentar + ejecutar 10-15 tareas variadas.  
**Día 2**: Seguir usando BAGO normalmente.  
**Día 3**: Entrenar BC. Evaluar shadow.  
**Día 4**: Si shadow ≥ 80%, entrenar PPO online.  
**Día 5**: Evaluar PPO. Si ≥ 85%, activar canary 5%.  
**Día 6-7**: Monitorear canary. Si estable, subir a 20% → 50% → 100%.

> **Regla de oro**: Nunca despliegues RL al 100% sin pasar por shadow + canary.

---

## Dónde están tus checkpoints

```
.bago\rl\checkpoints\bc\              ← BC entrenado con tus datos
.bago\rl\checkpoints\ppo_full_v3\     ← PPO single-agent pre-entrenado
.bago\rl\checkpoints\qmix\            ← QMIX multi-agent (4 agentes)
```

---

*Documento generado tras cierre de Fases 0-4 del plan RL.*
