# STATE_LIFECYCLE_POLICY — BAGO v3.4.0
## Estado: CERRADO ✅ (resuelto en v3.4.0 — Contrato §2)

## Tipos de state y su política

### Evidencia inmutable (NO MODIFICAR)
- `.bago/state/agents/*/episodic.json` — historial episódico de agentes
- `.bago/state/agents/*/gradient.json` — gradiente de aprendizaje
- `.bago/state/agents/*/state.json` — estado persistente
- `.bago/state/snapshots/` — snapshots de sesiones

**Política:** conservar como registro de ejecución real. No migrar, no limpiar, no tocar a mano.
Solo los propios agentes pueden escribir en sus propios directorios de estado.

### State vivo (PUEDE ACTUALIZARSE)
- `.bago/state/contracts/` — artefactos de contratos (escrito por guardianes)
- `.bago/state/global_state.json` — estado global (escrito por bago_version + bago_boot)
- `.bago/state/config/` — configuración de usuario

**Política:** se actualiza mediante herramientas BAGO, nunca manualmente salvo migración explícita.

### State de supervision (ESCRITO POR GUARDIANES)
- `.bago/supervision/artifacts/` — artefactos vivientes de los guardianes
- `.bago/state/contracts/supervision_*.json` — reports de gates pre-release

**Política:** actualizado exclusivamente por `supervisor.py` y sus agentes guardianes.

## Retención
- Snapshots históricos: se conservan indefinidamente (inmutables)
- Reports de supervisión: últimos 50 por guardián
- Logs de loops: últimos 10 por loop

## Historial
- `3.4.0` — Política definida, deuda §2 cerrada
