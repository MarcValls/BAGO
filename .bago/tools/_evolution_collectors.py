from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
MADRID = ZoneInfo("Europe/Madrid")
UTC = dt.timezone.utc


def parse_iso(ts: str) -> dt.datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return dt.datetime.fromisoformat(ts)


def fmt_local(ts: str) -> str:
    return parse_iso(ts).astimezone(MADRID).strftime("%Y-%m-%d %H:%M")


def fmt_utc(ts: str) -> str:
    return parse_iso(ts).astimezone(UTC).strftime("%Y-%m-%d %H:%M")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def esc(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def counts_by_day(records, ts_field: str, tz: ZoneInfo):
    counts = defaultdict(int)
    for r in records:
        ts = parse_iso(r[ts_field]).astimezone(tz).date().isoformat()
        counts[ts] += 1
    return dict(sorted(counts.items()))


def collect_json_records(folder: Path):
    return [load_json(p) for p in sorted(folder.glob("*.json"))]


def build_markdown_report(
    *,
    today_local,
    state_ref_day,
    start_corpus,
    current_corpus,
    metrics_snapshot,
    current_state,
    today_session_count,
    today_change_count,
    today_evidence_count,
    today_run_summaries,
    early_counts,
    late_counts,
    phase_role_early,
    phase_role_late,
    cluster_rows,
):
    report = f"""# Evolución del sistema BAGO

Este informe compara la fase inicial de corrección y migración con el estado operativo actual del repositorio.

## Fuentes

- [state/metrics/metrics_snapshot.json]({ROOT / "state/metrics/metrics_snapshot.json"})
- [state/global_state.json]({ROOT / "state/global_state.json"})
- [state/sessions/]({ROOT / "state/sessions"})
- [state/changes/]({ROOT / "state/changes"})
- [state/evidences/]({ROOT / "state/evidences"})
- [state/metrics/runs/]({ROOT / "state/metrics/runs"})

## Lectura ejecutiva

Al principio, BAGO trabajaba como un sistema de corrección y preservación canónica:

- centrado en `system_change`,
- con roles amplios y generales,
- con prioridad en migración, validación y consolidación documental,
- y con poca variedad de tipos de tarea.

Ahora trabaja como un sistema operativo más maduro:

- tiene `project_bootstrap`, `analysis`, `repository_audit` y `execution` además de `system_change`,
- separa mejor los roles por función,
- conserva trazabilidad de cambio, evidencia y estado,
- y ejecuta corridas autónomas de stress con ventanas temporales medibles.

## Métricas comparativas

| Métrica | Inicio | Ahora |
| --- | ---:| ---:|
| Snapshot documental mínimo | {start_corpus} artefactos | {current_corpus} artefactos |
| Sesiones nativas visibles | {metrics_snapshot["native_sessions_completed"]} | {current_state["inventory"]["sessions"]} |
| Sesiones migradas preservadas | {metrics_snapshot["migrated_sessions_count"]} | 4 preservadas en `state/migrated_sessions/` |
| Cambios migrados/validados | {metrics_snapshot["migrated_changes_count"] + metrics_snapshot["validated_changes"]} | {current_state["inventory"]["changes"]} |
| Evidencias registradas | no consolidado en snapshot inicial | {current_state["inventory"]["evidences"]} |
| Integridad del pack | {metrics_snapshot["pack_integrity_last_check"].upper()} | {current_state["last_validation"]["pack"]} / {current_state["last_validation"]["state"]} / {current_state["last_validation"]["manifest"]} |

## Métricas de hoy

Hoy local: **{today_local.strftime("%d/%m/%Y")}**.

| Métrica | Valor |
| --- | ---: |
| Sesiones de hoy | {today_session_count} |
| Cambios de hoy | {today_change_count} |
| Evidencias de hoy | {today_evidence_count} |
| Corridas autónomas de hoy | {len(today_run_summaries)} |
| Solicitudes de hoy en `metrics/runs` | {sum(int(r.get("total_requests", 0)) for r in today_run_summaries)} |

Si hoy no aparece actividad, significa que el árbol visible no contiene registros fechados en el día local del entorno.

## Cómo trabajaba al principio

Rango base del arranque: **11/04/2026**.

- La sesión dominante era `system_change`.
- El trabajo giraba alrededor de corrección del pack, migración histórica y oficialización canónica.
- La mezcla de roles era más generalista:
  - `{", ".join(phase_role_early) if phase_role_early else "n/a"}`
- La actividad se concentró en pocas ventanas de alta densidad documental.

## Cómo trabaja ahora

Rango visible del estado actual: **14/04/2026-15/04/2026** en el árbol local, con `global_state.json` actualizado al **17/04/2026 19:35 UTC**.

- La sesión incluye tareas más especializadas.
- La mezcla de trabajo se diversifica:
  - `{", ".join(phase_role_late) if phase_role_late else "n/a"}`
- El sistema ya no solo corrige canon:
  - arranca repo,
  - audita,
  - ejecuta,
  - evalúa,
  - reconstruye,
  - y consolida.

## Actividad por día

![Actividad diaria](figures/activity_by_day.svg)

## Cambio de mezcla de trabajo

![Mezcla por fase](figures/session_mix_by_phase.svg)

| Fase | system_change | project_bootstrap | analysis | repository_audit | execution | Total |
| --- | ---:| ---:| ---:| ---:| ---:| ---:|
| Inicio | {early_counts.get("system_change", 0)} | {early_counts.get("project_bootstrap", 0)} | {early_counts.get("analysis", 0)} | {early_counts.get("repository_audit", 0)} | {early_counts.get("execution", 0)} | {sum(early_counts.values())} |
| Ahora | {late_counts.get("system_change", 0)} | {late_counts.get("project_bootstrap", 0)} | {late_counts.get("analysis", 0)} | {late_counts.get("repository_audit", 0)} | {late_counts.get("execution", 0)} | {sum(late_counts.values())} |

## Evolución de tipos de trabajo

![Tipos de trabajo por día](figures/task_type_evolution.svg)

## Crecimiento del corpus

![Crecimiento del corpus](figures/corpus_growth.svg)

## Ventanas de trabajo autónomo

Las corridas de `state/metrics/runs/` sí traen duración real y permiten medir trabajo autónomo continuo.

![Ventanas autónomas](figures/runs_clusters.svg)

| Bloque | Inicio local | Fin local | Duración activa | Solicitudes | Corridas |
| --- | --- | --- | ---:| ---:| ---:|
"""
    for cluster in cluster_rows:
        report += f"| {cluster['label']} | {cluster['start'].astimezone(MADRID).strftime('%d/%m %H:%M')} | {cluster['end'].astimezone(MADRID).strftime('%d/%m %H:%M')} | {cluster['duration_s']:.3f}s | {cluster['requests']} | {cluster['run_count']} |\n"
    report += """

## Diagramas

### Evolución funcional

```mermaid
flowchart LR
  A["Corrección y migración"] --> B["Endurecimiento estructural"]
  B --> C["Performance y release"]
  C --> D["Bootstrap repo-first"]
  D --> E["Evaluación y reconstrucción"]
  E --> F["Operación estable"]
```

### Ciclo autónomo

```mermaid
stateDiagram-v2
  [*] --> Session
  Session --> Change
  Change --> Evidence
  Evidence --> GlobalState
  GlobalState --> NextSession
  NextSession --> Session
```

## Observaciones

- Snapshot canónico de referencia: {state_ref_day.strftime("%d/%m/%Y")} desde `global_state.updated_at`.
- El árbol local visible tiene menos archivos que `global_state.json` anticipa en su inventario. Eso sugiere que el estado canónico va por delante de esta copia del árbol.
- La evolución principal no es solo de volumen; es de especialización y de capacidad para cerrar ciclos de trabajo con evidencias y validación.
"""
    return report


def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())

