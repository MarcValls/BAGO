# Stress de agentes BAGO (2.5-stable)

## 1) Ejecución de estrés

```bash
python3 .bago/tools/perf/stress_bago_agents.py \
  --bago-root . \
  --provider openai \
  --agents 10 \
  --iterations 30 \
  --model gpt-5.4-mini
```

Notas:

- `--bago-root` acepta tanto la raíz del repo (`.`) como la carpeta `.bago`.
- `--provider openai` usa `OPENAI_API_KEY`.
- `--provider github_models` usa `GITHUB_MODELS_TOKEN` o `GITHUB_TOKEN`.
- `--global-rate-limit-rps` aplica un límite global de ritmo compartido entre procesos.
- En `github_models` hay backoff con reintentos sobre `429` y `5xx`.
- Ajustes útiles: `--github-max-retries`, `--github-backoff-base-ms`, `--github-backoff-max-ms`.
- Si no existe la credencial del provider elegido, entra en modo simulación automáticamente.
- Para forzar simulación: `--simulate`.
- Salida en `.bago/state/metrics/runs/stress_YYYYMMDD_HHMMSS/` (directorio creado automáticamente en primer uso).

## 2) Generar gráficas

```bash
python3 .bago/tools/perf/render_perf_charts.py \
  --run-dir .bago/state/metrics/runs/stress_YYYYMMDD_HHMMSS
```

## Archivos generados

- `results.csv`: resultado por request y agente.
- `agent_timeline.csv`: estado vivo de agentes y consumo de proceso.
- `summary.json`: KPIs globales y por agente.
- `charts/*.svg`: throughput, throughput por 10s, p95, errores, reintentos y CPU.

## Resultados recientes importantes

### 1) GitHub Models sin limitador global

Run:

- `stress_20260413_234440`

Configuración:

- `provider=github_models`
- `model=openai/gpt-4.1`
- `agents=10`
- `iterations=30`
- sin `global_rate_limit_rps`

Resultado:

- `300` requests totales
- `130` OK
- `170` errores
- `error_rate=0.5667`
- `throughput_rps=1.567`
- patrón dominante: `429 Too many requests`

Conclusión:

- el backend real funcionó
- el cuello de botella dejó de ser TLS/autenticación y pasó a ser rate limiting
- esta configuración no es estable para uso comparativo

### 2) GitHub Models con backoff y limitador global

Runs comparativos:

- `stress_20260414_001308` con `global_rate_limit_rps=0.5`
- `stress_20260414_001651` con `global_rate_limit_rps=0.8`
- `stress_20260414_002037` con `global_rate_limit_rps=1.0`

Configuración común:

- `provider=github_models`
- `model=openai/gpt-4.1`
- `agents=3`
- `iterations=20`
- `github_max_retries=3`
- `github_backoff_base_ms=750`
- `github_backoff_max_ms=8000`

Resultados:

- `rps=0.5`: `60/60 OK`, `error_rate=0.0`, `throughput_rps=0.277`, `p95=11970.15 ms`
- `rps=0.8`: `60/60 OK`, `error_rate=0.0`, `throughput_rps=0.279`, `p95=13102.25 ms`
- `rps=1.0`: `60/60 OK`, `error_rate=0.0`, `throughput_rps=0.273`, `p95=11364.6 ms`

Conclusión:

- el limitador global elimina los `429` en esta banda
- subir de `0.5` a `1.0` no mejora throughput de forma material
- `0.8` no aporta una ventaja operativa clara

### 3) Recomendación operativa actual

Presets recomendados para `github_models`:

- `safe`: `--global-rate-limit-rps=0.5`
- `balanced`: `--global-rate-limit-rps=1.0`

Comando base recomendado:

```bash
GITHUB_TOKEN="..." python3 .bago/tools/perf/stress_bago_agents.py \
  --provider=github_models \
  --model='openai/gpt-4.1' \
  --agents=3 \
  --iterations=20 \
  --global-rate-limit-rps=1.0 \
  --github-max-retries=3 \
  --github-backoff-base-ms=750 \
  --github-backoff-max-ms=8000 \
  --bago-root=.
```
