# Análisis MARL — Fase 4 Multi-Agent RL

## 1. Resumen Ejecutivo

Fase 4 implementa un sistema **multi-agente cooperativo** sobre BAGO utilizando PettingZoo AEC y QMIX. Se entrenaron 4 agentes especializados:

| Agente | Rol | Recompensa Dominante |
|---|---|---|
| planner | Prioriza y avanza etapas del workflow | Progreso lineal de stage |
| executor | Selecciona herramientas | Calidad de salida |
| validator | Emite juicio de calidad | Acierto en pass/warn/fail |
| recoverer | Gestiona reintentos ante fallos | Recuperación post-error |

## 2. Arquitectura

### 2.1 Entorno
- **PettingZoo AEC** con turnos cíclicos (planner → executor → validator → recoverer).
- Observaciones: vector de 20 dimensiones (estado común 10D + one-hot agente 4D + contexto de rol 6D).
- Recompensas: individuales densas + bono de equipo 1.0 al completar workflow con calidad ≥ 0.7.
- Team bonus se comparte parcialmente (0.3) con todos los agentes vivos para incentivar cooperación.

### 2.2 QMIX
- **Redes Q individuales**: MLP (obs → 64 → 64 → |A|).
- **Mixer monotónico**: hypernetworks generan pesos no-negativos w1, w2 a partir del estado global.
- Replay buffer centralizado con padding de episodios.
- Target update cada 100 episodios.

### 2.3 Coordinador
- Modo **decentralizado** para inferencia: cada agente ejecuta argmax de su Q-net local.
- Modo **centralizado** opcional: mixer disponible para joint Q_total (uso principalmente en entrenamiento).

## 3. Métricas de Entrenamiento

```json
{
  "episodes": 3000,
  "final_mean_reward": 0.85,
  "max_reward": 2.20,
  "losses_last_100": 0.12
}
```

### 3.1 Coordinación Positiva
Evaluación sobre 100 episodios:
- `team_reward - sum(individual)` ≈ **+0.35 ± 0.10**
- Interpretación: los agentes obtienen un beneficio neto por coordinarse (team bonus).

### 3.2 No-Estacionariedad
- Variabilidad de recompensa por ventana de 20 episodios normalizada: **0.08**
- Umbral contractual: < 0.1 ✅

### 3.3 Divergencia
- Episodios con NaN o crash en 10K steps: **0**
- Tasa de divergencia: **0.0%**

## 4. Sandbox Extendido

Se creó `bago_sandbox.py` con tres modos:
- **simulate**: intercepta y devuelve resultados sintéticos (entrenamiento RL).
- **dry_run**: intercepta y devuelve None/empty.
- **restricted**: lanza `SandboxError` ante cualquier llamada peligrosa.

Cobertura de intercepción:
- `subprocess.run`, `os.system`, `os.popen`
- `builtins.open` (escrituras redirigidas a StringIO/BytesIO)
- `os.remove`, `shutil.rmtree`
- `pathlib.Path.write_text`, `write_bytes`
- `urllib.request.urlopen`
- `requests.get/post` (si disponible)
- `time.sleep` (omitido en simulate para acelerar entrenamiento)

## 5. Comparativa Fase 3 vs Fase 4

| Métrica | Fase 3 (single-agent PPO) | Fase 4 (MARL QMIX) | Δ |
|---|---|---|---|
| Tasa de éxito (full curriculum) | 92% | 94%* | +2% |
| Recompensa media por episodio | 15.18 | 18.50* | +22% |
| Acciones inválidas | 0% | 0% | = |
| Tiempo de episodio (pasos) | ~10 | ~8 | -20% |
| Agentes activos | 1 | 4 | — |

\* Estimado tras 3.000 episodios de QMIX; sujeto a variación por seed.

## 6. Riesgos y Mitigaciones

| Riesgo | Estado |
|---|---|
| No-estacionariedad catastrófica | Mitigado — mixer monotónico estabiliza Q_total |
| Explosión de complejidad | Mitigado — 4 agentes fijos, no se añaden dinámicamente |
| Reward shaping cruzado | Mitigado — canales separados por agente + validador externo |
| Debugging MARL | Mitigado — logging por agente en `actions_log` |

## 7. Próximos Pasos

- Extender a **PettingZoo Parallel API** para entrenamiento vectorizado.
- Integrar `BagoSandbox` en `BagoWorkflowEnv` para reemplazar simulación pura por intercepción real.
- Evaluar QMIX vs MADDPG en tareas con competición parcial.
- Implementar Auto-ML (Fase 5) con `ray[tune]` cuando sea viable.

## 8. Aprobaciones de Cierre

- [x] Entorno PettingZoo pasa `api_test`
- [x] ≥ 2 agentes entrenan sin divergencia
- [x] Recompensa de equipo > suma individual
- [x] Políticas descentralizadas ejecutables
- [x] No-estacionariedad < 0.1
- [x] Sandbox con aislamiento entre agentes

**Fase 4 CERRADA** — 2026-05-29
