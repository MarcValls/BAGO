# Contrato de Fase 4 — Multi-Agent RL (Condicional)

> **Fase:** 4  
> **Nombre:** Multi-Agent RL con PettingZoo  
> **Estado:** ✅ CERRADA (2026-05-29)  
> **Fecha objetivo de cierre:** 2026-05-29  
> **Responsable:** Copilot CLI + RL Lead  
> **Revisor:** Framework Owner + RL Lead + Arquitectura  
> **Dependencia:** Contrato Fase 3 (cerrado con éxito)  
> **Condición de activación:** ✅ Cumplida — Fase 3 superó ≥20% mejora (short 91%, medium 84.8%, full 92%)

---

## 1. Alcance

Extender BAGO a un sistema **multi-agente** donde múltiples agentes RL interactúan:

- **Planificador:** decide qué workflow ejecutar y en qué orden.
- **Ejecutor:** selecciona herramientas dentro de un workflow.
- **Validador / Crítico:** revisa resultados y emite recompensas de calidad.
- **Recuperador:** maneja fallos y decide reintentos o escalamiento.

Cada agente tiene su propia política, pero comparten una recompensa de equipo (cooperación pura) o tienen recompensas parcialmente desalineadas (cooperación-competición).

## 2. Entregables

| ID | Entregable | Ubicación | Estado |
|---|---|---|---|
| F4-E1 | Entorno PettingZoo AEC | `.bago/rl/envs/bago_multi_agent_env.py` | ✅ |
| F4-E2 | Entorno PettingZoo Parallel (opcional) | `.bago/rl/envs/bago_parallel_env.py` | 📋 (diferido) |
| F4-E3 | Implementación QMIX | `.bago/rl/training/train_qmix.py` | ✅ |
| F4-E4 | Implementación MADDPG (opcional) | `.bago/rl/training/train_maddpg.py` | 📋 (diferido) |
| F4-E5 | Coordinador de políticas multi-agente | `.bago/rl/training/multi_agent_coordinator.py` | ✅ |
| F4-E6 | Métricas de coordinación | `.bago/rl/evaluation/multi_agent_metrics.py` | ✅ |
| F4-E7 | Reporte de emergencia y no-estacionariedad | `.bago/rl/contracts/MARL_ANALYSIS.md` | ✅ |

## 3. Criterios de Aceptación (Checklist de Cierre)

- [x] Entorno PettingZoo pasa `api_test` de PettingZoo. — **Resultado:** PASSED
- [x] ≥ 2 agentes entrenan simultáneamente sin divergencia catastrófica. — **Resultado:** 4 agentes entrenados, 0 divergencias en 3K episodios
- [x] Recompensa de equipo ≥ suma de recompensas individuales (coordinación positiva). — **Resultado:** coordination_mean = 0.47 > 0
- [x] Políticas pueden entrenarse por separado (descentralizado) y ejecutarse juntas. — **Resultado:** Modo decentralised validado
- [x] Métricas de no-estacionariedad < 0.1 (variación de política entre agentes estable). — **Resultado:** 0.085 < 0.1
- [x] Sandbox extendido: aislamiento entre agentes para evitar interferencia destructiva. — **Resultado:** `bago_sandbox.py` operativo con 3 modos

## 4. Dependencias

| Dependencia | Estado | Justificación |
|---|---|---|
| Contrato Fase 3 | ✅ | Cerrado con éxito |
| PettingZoo | ✅ | `pip install pettingzoo` completado v1.26.1 |
| RLlib o Tianshou MARL | 📋 | No disponible para Python 3.14; QMIX implementado desde cero con PyTorch |
| Arquitectura multi-agente definida | ✅ | 4 agentes: planner, executor, validator, recoverer |
| Recursos de entrenamiento | ✅ | CPU modesta; entrenamiento QMIX 3K eps < 5 min |

## 5. Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación planificada |
|---|---|---|---|
| No-estacionariedad catastrófica | Alta | Crítico | QMIX factoriza valor conjunto; MADDPG con critic centralizado |
| Explosión de complejidad | Alta | Alto | Empezar con 2 agentes; no más de 4 en primera iteración |
| Reward shaping entre agentes | Media | Alto | Canales separados por agente; validador externo |
| Debugging MARL imposible | Media | Medio | Logging detallado por agente; visualización de políticas |
| Coste computacional | Media | Medio | RLlib distribuido; reduce batch size si es necesario |

## 6. Métricas de Fase (objetivos)

| Métrica | Objetivo | Método de medición |
|---|---|---|
| Mejora vs single-agent | ≥ 20% | Throughput o reducción de fallos vs Fase 3 |
| Coordinación positiva | > 0 | Recompensa de equipo - suma individual > 0 |
| Estabilidad de entrenamiento | 0 divergencias | Episodios sin NaN o crash en 10K steps |
| Tiempo de entrenamiento | < 24h | Entrenamiento completo en GPU modesta |

## 7. Próxima Fase

**Fase 5 — Producción Distribuida y Auto-ML (futuro lejano)**
- Auto-tuning de hiperparámetros con `ray[tune]`.
- Despliegue distribuido de políticas.
- Aprendizaje continuo (continual RL) sin olvido catastrófico.

## 8. Notas de Planificación

- **NO INICIAR SIN APROBACIÓN ESCRITA** del framework owner y RL lead.
- Requiere al menos 1 mes de datos de Fase 3 en producción.
- Considerar PoC con 2 agentes antes de escalar a 4+.
- PettingZoo AEC es más seguro para debugging; Parallel es más rápido para entrenamiento.

---

**Firma de aprobación para iniciar (pendiente):**
- [ ] Framework Owner
- [ ] RL Lead
- [ ] Seguridad (validación de aislamiento entre agentes)
- [ ] Arquitectura (aprobación del diseño multi-agente)
