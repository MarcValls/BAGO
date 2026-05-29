# Contrato de Fase 0 — Instrumentación y Logging de Transiciones RL

> **Fase:** 0  
> **Nombre:** Instrumentación y Logging  
> **Estado:** ✅ CERRADA  
> **Fecha de cierre:** 2026-05-29  
> **Responsable:** BAGO Audit Agent  
> **Revisor:** Framework Owner  

---

## 1. Alcance

Implantar la capacidad de capturar transiciones del tipo `(observation, action, reward, next_observation, done, info)` desde los componentes core de BAGO **sin modificar su comportamiento operativo**. La instrumentación debe ser:

- **No-invasiva:** los componentes funcionan exactamente igual sin la instrumentación.
- **Opt-in:** se activa explícitamente (`BAGO_RL_INSTRUMENTATION=1` o config JSON).
- **Performante:** zero-cost cuando está desactivada.

## 2. Entregables

| ID | Entregable | Ubicación | Estado |
|---|---|---|---|
| F0-E1 | `BagoRLLogger` — Logger de transiciones JSONL | `.bago/tools/bago_rl_logger.py` | ✅ |
| F0-E2 | `BagoRLHooks` — Hooks no-invasivos | `.bago/tools/bago_rl_hooks.py` | ✅ |
| F0-E3 | Estructura de directorios RL | `.bago/rl/` | ✅ |
| F0-E4 | Tests de auto-verificación | Self-tests embebidos en cada script | ✅ |

## 3. Criterios de Aceptación (Checklist de Cierre)

- [x] `bago_rl_logger.py --test` pasa 8/8 checks (buffer, flush, rotación, stats).
- [x] `bago_rl_hooks.py` carga sin errores en Python y reporta componentes instrumentados.
- [x] Logger produce JSONL válido con esquema de transición completo.
- [x] Hooks no invocan logger si `BAGO_RL_INSTRUMENTATION` no está activado.
- [x] `py_compile` limpio en todos los archivos nuevos.
- [x] Sin modificaciones funcionales en `orchestrator.py`, `neural_toolbox.py`, `agent_router.py`.

## 4. Dependencias

| Dependencia | Estado | Justificación |
|---|---|---|
| Arquitectura BAGO documentada | ✅ | Se conoce orchestrator, toolbox, router |
| Py 3.10+ con stdlib | ✅ | No requiere librerías externas |

## 5. Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación aplicada |
|---|---|---|---|
| Overhead en producción | Baja | Medio | Diseño opt-in; sin activación, coste cero |
| Logs corruptos por crash | Media | Bajo | Buffer periódico + rotación automática |
| Dependencia circular con logger | Baja | Medio | Lazy import en hooks |

## 6. Métricas de Fase

| Métrica | Valor observado | Umbral de aceptación |
|---|---|---|
| Tests pasados | 8/8 | ≥ 8/8 |
| Tiempo de carga hooks | < 50 ms | < 100 ms |
| Archivos nuevos con syntax OK | 4/4 | 4/4 |

## 7. Lecciones Aprendidas

- Los componentes core de BAGO tienen métodos que pueden envolverse dinámicamente (`_wrap_method`), evitando forks del código fuente.
- `neural_toolbox.py` ya tiene `feedback()`, lo que simplificará la integración con bandits en Fase 1.

## 8. Próxima Fase

**Fase 1 — Contextual Bandits para Tool Routing**
- Depende de: F0-E1 (logger) para evaluación off-policy, pero puede ejecutarse en sandbox sin logs reales.
- Entrada: mecanismo de instrumentación validado y estable.

---

**Firma de cierre:**
- [x] Implementador
- [x] Revisor (framework owner)
- [x] QA (tests automáticos)
