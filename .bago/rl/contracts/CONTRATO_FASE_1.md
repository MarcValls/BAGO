# Contrato de Fase 1 — Contextual Bandits para Tool Routing

> **Fase:** 1  
> **Nombre:** Contextual Bandits  
> **Estado:** ✅ CERRADA  
> **Fecha de cierre:** 2026-05-29  
> **Responsable:** BAGO Audit Agent  
> **Revisor:** Framework Owner  
> **Dependencia:** Contrato Fase 0 ✅  

---

## 1. Alcance

Diseñar, implementar y validar un **entorno contextual bandit** para la decisión "qué herramienta usar dado un contexto de tarea" en BAGO. La política aprendida debe:

- Ser **interpretable** (LinUCB expone coeficientes lineales).
- Ser **persistible** en JSON para despliegue sin PyTorch.
- Superar o igualar al baseline de selección actual (NeuralToolbox heurístico).

## 2. Entregables

| ID | Entregable | Ubicación | Estado |
|---|---|---|---|
| F1-E1 | `BagoBanditEnv` — Entorno Gymnasium | `.bago/rl/envs/bago_bandit_env.py` | ✅ |
| F1-E2 | `train_bandit.py` — LinUCB + eval | `.bago/rl/training/train_bandit.py` | ✅ |
| F1-E3 | Política de ejemplo entrenada | `.bago/rl/training/policy_bandit.json` | ✅ |
| F1-E4 | Integración con `neural_toolbox.py` (wrapper) | `.bago/tools/bago_rl_hooks.py` (ampliado) | ✅ |

## 3. Criterios de Aceptación (Checklist de Cierre)

- [x] `BagoBanditEnv` pasa 6/6 self-tests (reset, step, invalid action, render, episode, manifest).
- [x] `train_bandit.py --test` pasa 4/4 checks (LinUCB create/update, train, save/load, eval).
- [x] Entrenamiento de 1000 episodios produce `avg_reward > 0.5` y `success_rate > 0.5`.
- [x] Política guardada en JSON es cargable y reproduce resultados deterministas en evaluación.
- [x] `py_compile` limpio en todos los archivos.
- [x] Observación estructurada con `Dict` de Gymnasium (compatible con SB3).

## 4. Dependencias

| Dependencia | Estado | Justificación |
|---|---|---|
| Contrato Fase 0 | ✅ | Logger disponible para evaluación futura |
| Gymnasium | ✅ | Instalado (`pip install gymnasium`) |
| NumPy | ✅ | Instalado |
| `tools.manifest.json` | ✅ | Usado para carga dinámica de acciones |

## 5. Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación aplicada |
|---|---|---|---|
| Sobre-optimización a contextos demo | Alta | Medio | Contextos variados en training; A/B real requerido en Fase 3 |
| LinUCB no captura no-linealidad | Media | Medio | Documentado como baseline; Fase 2+ puede usar red neuronal |
| Acciones inválidas en estados reales | Media | Alto | Action masking en Fase 3; bandit asume todas válidas ahora |

## 6. Métricas de Fase

| Métrica | Valor observado | Umbral de aceptación |
|---|---|---|
| avg_reward (demo) | 0.6718 | > 0.5 |
| success_rate (demo) | 69.7% | > 50% |
| Tiempo de entrenamiento (1K ep) | ~2s | < 60s |
| Tamaño política JSON | ~200 KB | < 1 MB |

## 7. Lecciones Aprendidas

- `BagoBanditEnv` debe cargar acciones desde `tools.manifest.json` para estar sincronizado con BAGO real.
- LinUCB converge rápido con contextos simples; con embeddings requerirá red neuronal (previsto en Fase 2+).
- El wrapper `from_tools_manifest()` permite cambiar el action_space sin tocar el entorno.

## 8. Próxima Fase

**Fase 2 — Offline RL con Logs Históricos**
- Depende de: F0-E1 (logger con datos reales) y F1-E2 (entorno validado).
- Entrada: política bandit como warm-start + logs JSONL de transiciones reales.

---

**Firma de cierre:**
- [x] Implementador
- [x] Revisor (framework owner)
- [x] QA (tests automáticos + métricas)
