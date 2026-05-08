# BAGO — Hoja de Ruta

> Estado actual: **v3.3.0** (Structural) · Mayo 2026  
> Próximo hito: **v4.0** (Distribución)

---

## Visión

BAGO aspira a ser la capa estándar de gobernanza operacional para cualquier flujo de trabajo técnico asistido por IA: la infraestructura que convierte un agente potente pero amnésico en un colaborador estructurado, auditable y escalable.

---

## Principios de evolución

1. **BAGO se construye con BAGO.** Toda feature pasa por los mismos workflows que proporciona.
2. **El contrato público se mantiene estable.** Los 12 comandos core no cambian su interfaz en patches.
3. **Sin dependencias externas.** La instalación base es Python stdlib. Los extras (Ollama, cloud) son opt-in.
4. **La sinceridad es un gate.** `bago health sincerity` se ejecuta antes de cualquier release.

---

## Fase actual — v3.x · Estabilización y estructura

**Estado: activo**

### Completado en v3.3.0

- ✅ 8 CI gates activos (ninguno con `continue-on-error`)
- ✅ `COMMANDS.md` auto-generado desde `tool_registry.py` (stale guard en CI)
- ✅ Gate `gate-wheel`: `pip install -e .` verificado en CI
- ✅ Taxonomía de 6 capas para todos los comandos (EJECUCIÓN · CALIDAD · SALUD · ANALÍTICA · VISUAL · AVANZADO)
- ✅ 3 routers activados: `bago health`, `bago audit`, `bago session`
- ✅ 58 sesiones históricas migradas a `bago.db` · 60 commits
- ✅ Scope detector: análisis estático framework/project/both
- ✅ **CHG-002 resuelto**: Guardian 0% → 100% (33 tools con `--test` real, no `print("OK")`)
- ✅ **W2 completado**: TON wallet connect en BAGO app (2026-05-07 22:13–23:15)
- ✅ **Pendrive SanDisk operativo**: `/Volumes/BAGO` (launcher FAT32) + `/Volumes/bago_core` (workspace 30GB ExFAT) · 47 ideas activas · health 100/100

### En curso en v3.x

- 🔄 PADRE/SIEMBRA: clasificación de comandos por scope completa (base lista). Implementación deferred a v4.0+
- 🔄 Cobertura de `--dry-run` en todos los comandos mutantes
- 🔄 Argumentos validados en comandos legacy antes de redirigir

---

## Próxima fase — v4.0 · Distribución

**Objetivo:** `pip install bago` funciona sin instalación editable.

### Issues planificados

| Prioridad | Issue | Descripción |
|-----------|-------|-------------|
| P1 | `fw-dist-wheel` | Bundle del launcher en el wheel. `pip install bago` instala el script correctamente sin `pip install -e .` |
| P1 | `fw-dry-run-all` | Implementar `--dry-run` en todos los comandos de riesgo `mutating` y `dangerous` |
| P2 | `fw-padre-siembra` | PADRE/SIEMBRA: framework replica en exceso en proyectos hijo. `scope=project` commands forman el seed mínimo |
| P2 | `fw-legacy-args` | Comandos legacy validan argumentos antes de redirigir |
| P3 | `fw-windows-full` | Soporte completo Windows (actualmente parcial) |

### Contrato de v4.0

- `pip install bago` funciona en entorno limpio sin flags adicionales
- Todos los comandos core tienen `--dry-run` donde aplica
- 0 comandos legacy sin migración documentada

---

## Horizonte — v5.0 y más allá

Estas iniciativas están en el backlog pero **no tienen fecha comprometida**:

### PADRE/SIEMBRA (v5.0)

El framework tiende a replicarse en exceso en cada proyecto. El modelo PADRE/SIEMBRA propone:
- **PADRE:** El framework BAGO como instalación central
- **SIEMBRA:** Un subset mínimo (`scope=project` commands) que se "siembra" en cada proyecto

Beneficio: proyectos más ligeros, actualizaciones centralizadas.

### Sincronización cloud (v5.x)

Estado compartido entre desarrolladores de un mismo equipo sin servidor propio:
- Sincronización de `global_state.json` vía S3 / GitHub Gist / servidor propio
- Opt-in, no reemplaza el estado local
- Respeta la separación código/estado ya establecida

### Marketplace de workflows (v6.x)

Biblioteca pública de workflows BAGO para dominios específicos:
- `bago workflow install game-dev`
- `bago workflow install web-api`
- `bago workflow install ml-pipeline`

Cada workflow tiene su propio versionado y contrato.

### Integración nativa con IDEs (v6.x)

Extension para VS Code / Cursor que muestra el estado BAGO en el panel lateral y permite disparar comandos sin salir del editor.

---

## Ideas registradas en backlog (bago.db)

Las siguientes ideas están registradas y puntuadas, pendientes de implementación:

| ID | Idea | Score | Scope |
|----|------|-------|-------|
| `fw-padre-siembra` | PADRE/SIEMBRA model | Alto | framework |
| `fw-standalone-install` | `pip install bago` sin `-e` | Alto | framework |
| `fw-workflow-marketplace` | Marketplace de workflows | Medio | framework |
| `fw-cloud-sync` | Sincronización cloud del estado | Medio | framework |
| `fw-ide-extension` | Extension VS Code / Cursor | Medio | framework |

Para ver el backlog completo: `bago ideas`

---

## Métricas de evolución (históricas)

| Versión | Comandos | Tools | Índice de Eficiencia | Fecha |
|---------|:---:|:---:|:---:|-------|
| 2.3-clean *(baseline)* | 10 | 19 | 78.6 | Abr 2026 |
| 2.4-v2rc | 10 | 27 | 89.3 | Abr 2026 |
| 2.5-stable | 35 | 111 | 100.0 | Abr 2026 |
| 2.6-taxonomy | 51 | 177 | 100.0 | May 2026 |
| **3.3.0** *(actual)* | **54** | **218** | **100.0** | May 2026 |

> Las métricas son snapshots en el momento de la release, capturadas con `bago efficiency`. No son valores en tiempo real.

---

## Contribuir

BAGO sigue el modelo de contribución estándar:

1. Abre un issue describiendo la feature o el bug
2. Espera a que se confirme el scope y la prioridad
3. Implementa usando el workflow W2 (Controlled Implementation)
4. El PR debe pasar los 8 gates de CI
5. `bago health sincerity` debe ser GREEN

Ver [`CONTRIBUTING.md`](../CONTRIBUTING.md) para el detalle completo.

---

*BAGO v3.3.0 · Mayo 2026 · github.com/MarcValls/BAGO*
