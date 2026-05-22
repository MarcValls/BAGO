# BAGO v3.0 — Modelo PADRE / SIEMBRA

**Estado:** SPEC APROBADO (pendiente implementación)  
**Idea:** `fw-padre-siembra` (bago.db)  
**Autor:** BAGO + Marc  
**Versión objetivo:** 3.0  

---

## Problema actual

El framework BAGO vive íntegramente en `bago_core`. Cuando se trabaja en un proyecto externo (e.g., DERIVA, un repo de cliente), no existe un mecanismo formal para "plantar" BAGO en ese repo. Las opciones actuales son malas:

- **Copiar todo** → el proyecto hereda 177 herramientas, 80 comandos y el estado global de BAGO. Imposible de mantener sincronizado.
- **No plantar** → el proyecto trabaja sin BAGO, pierde trazabilidad, ideas, W2, etc.
- **Alias global** → apunta a `bago_core`, mezcla el estado del framework con el estado del proyecto.

---

## Solución: PADRE y SIEMBRA

### PADRE (= `bago_core`)

El **framework padre** es el único repositorio que contiene el BAGO completo:

- Todos los comandos (scope `framework`, `project`, `both`)
- El estado global (`global_state.json`, `bago.db`)
- Las herramientas de mantenimiento del propio BAGO (health, validate, auto, heal…)
- El historial de sesiones, sprints, ideas y versiones
- El guardián de herramientas, los tests de integración, el CI

**El PADRE nunca se copia en proyectos externos.**  
**El PADRE es único por entorno** (pendrive, máquina de trabajo, etc.).

### SIEMBRA (= `.bago/` en un proyecto externo)

Una **siembra** es la huella mínima de BAGO en un proyecto externo. Contiene únicamente lo que ese proyecto necesita para:

1. Abrir sesiones de trabajo (W2)
2. Registrar ideas y decisiones
3. Ejecutar herramientas de calidad sobre el código del proyecto
4. Delegar al PADRE cuando necesita algo del framework

---

## Estructura de una SIEMBRA

```
proyecto-externo/
├── .bago/
│   ├── pack.json              # Metadata del proyecto (nombre, versión, PADRE_PATH)
│   ├── state/
│   │   ├── repo_context.json  # Contexto del repo (branch, último commit, etc.)
│   │   └── bago.db            # Ideas y sesiones del proyecto (local, no global)
│   └── tools/                 # Solo herramientas scope=project y scope=both
│       ├── emit_ideas.py
│       ├── bago_start.py
│       ├── bago_session_router.py
│       ├── auto_mode.py          # Modo proyecto (sin loop de framework)
│       ├── scan.py               # Auditoría de código del proyecto
│       ├── pre_push_check.py
│       ├── debt_ledger.py
│       ├── naming.py
│       └── ... (~25 tools)
└── bago                       # Launcher mínimo → delega al PADRE si es necesario
```

### `pack.json` de una siembra

```json
{
  "name": "mi-proyecto",
  "type": "siembra",
  "padre_path": "/Volumes/bago_core",
  "bago_version": "3.0",
  "seeded_at": "2026-05-06",
  "seeded_from": "2.6-taxonomy",
  "tools_included": ["start", "ideas", "scan", "pre-push", "session", "task"]
}
```

---

## Qué herramientas van en la siembra

Basado en la taxonomía de `scope_detector.py` (v2.6):

### ✅ Incluidas en siembra (scope = `project`)

| Comando        | Descripción                                      |
|---------------|--------------------------------------------------|
| `scan`         | Auditoría estática del código del proyecto       |
| `review`       | Revisión de cambios pendientes                   |
| `commit`       | Workflow de commit controlado                    |
| `pre-push`     | Pre-push guard del proyecto                      |
| `secrets`      | Detección de secretos en el repo                 |
| `debt`         | Registro de deuda técnica                        |
| `risk`         | Evaluación de riesgo de cambios                  |
| `naming`       | Verificación de convenciones de nombres          |
| `types`        | Auditoría de tipos                               |
| `deps`         | Auditoría de dependencias (requirements/pyproject)|
| `code-quality` | Orquestador de calidad de código                 |

### ✅ Incluidas en siembra (scope = `both`)

| Comando          | Descripción                                    |
|-----------------|------------------------------------------------|
| `start`          | Entrada rápida (health + ideas del proyecto)   |
| `next`           | Acepta idea y abre W2 en un paso               |
| `ideas`          | Ideas del proyecto (bago.db local)             |
| `select`         | Selector de ideas                              |
| `session`        | Opener de sesión W2                            |
| `task`           | Tarea W2 activa                                |
| `done`           | Marca tarea como completada                    |
| `flow`           | Estado del flujo de trabajo                    |
| `sprint`         | Gestión de sprints del proyecto                |
| `goals`          | Objetivos del proyecto                         |
| `cosecha`        | Cierre de sesión / harvest                     |
| `audit`          | Auditoría del estado del proyecto              |
| `context`        | Contexto del repo (branch, commits, etc.)      |
| `insights`       | Análisis de métricas del proyecto              |
| `habit`          | Seguimiento de hábitos                         |
| `chronicle`      | Registro cronológico de trabajo                |
| `diff`           | Diff inteligente                               |
| `status`         | Estado rápido del proyecto                     |
| `stale`          | Detecta elementos obsoletos                    |

### ❌ Solo en PADRE (scope = `framework`)

| Comando          | Motivo                                          |
|-----------------|------------------------------------------------|
| `health`         | Estado del framework BAGO, no del proyecto     |
| `validate`       | Valida el pack.json del PADRE                  |
| `sync`           | Sincroniza metadata del PADRE                  |
| `check`          | Pureza del PADRE                               |
| `consistency`    | Consistencia del inventario del PADRE          |
| `stability`      | Estabilidad del framework                      |
| `efficiency`     | Eficiencia del framework                       |
| `auto`           | Loop de evolución del PADRE                    |
| `heal`           | Auto-reparación del PADRE                      |
| `doctor`         | Diagnóstico del PADRE                          |
| `scope`          | Análisis estático del PADRE                    |
| `cabinet`        | Orquestación de agentes del PADRE              |
| `install`        | Instalación de extensiones del PADRE           |
| `rules`          | Catálogo de reglas del PADRE                   |
| `report`         | Informe HTML del PADRE                         |
| `banner`         | Banner del PADRE                               |
| `db`             | Base de datos global del PADRE                 |
| `hello`          | Test del PADRE                                 |

---

## El launcher de la siembra (`bago`)

El `bago` de una siembra es un script mínimo (~50 líneas) que:

1. **Si el comando es de tipo `project`/`both`** → carga la herramienta local en `.bago/tools/`
2. **Si el comando es de tipo `framework`** → delega al PADRE vía `BAGO_PADRE_PATH`
3. **Si `BAGO_PADRE_PATH` no está configurado** → avisa que se necesita conectar un PADRE

```python
#!/usr/bin/env python3
"""bago — launcher de siembra. Delega al PADRE para comandos de framework."""
import os, sys, subprocess
from pathlib import Path

LOCAL_BAGO  = Path(__file__).resolve().parent / ".bago"
PADRE_PATH  = os.environ.get("BAGO_PADRE_PATH") or _read_pack_padre()
PADRE_BAGO  = Path(PADRE_PATH) / "bago" if PADRE_PATH else None

FRAMEWORK_CMDS = {"health", "validate", "sync", "auto", "heal", "doctor",
                  "scope", "cabinet", "install", "rules", "report", "banner",
                  "db", "hello", "check", "consistency", "stability", "efficiency"}

cmd = sys.argv[1] if len(sys.argv) > 1 else "start"

if cmd in FRAMEWORK_CMDS:
    if not PADRE_BAGO or not PADRE_BAGO.exists():
        print("⚠️  Comando de framework. Configura BAGO_PADRE_PATH o usa bago connect.")
        sys.exit(1)
    sys.exit(subprocess.run([sys.executable, str(PADRE_BAGO)] + sys.argv[1:]).returncode)
else:
    # Ejecutar herramienta local
    ...
```

---

## Gestión de siembras desde el PADRE

El PADRE gestiona las siembras con un nuevo comando `bago siembra`:

```
bago siembra create <ruta-repo>   → planta una siembra en el repo
bago siembra list                 → lista todas las siembras conocidas
bago siembra update <ruta-repo>   → actualiza las herramientas de una siembra
bago siembra diff <ruta-repo>     → diferencias entre la siembra y el PADRE actual
bago siembra sync --all           → actualiza todas las siembras registradas
```

Las siembras se registran en `.bago/state/siembras.json` del PADRE:

```json
{
  "siembras": [
    {
      "name": "DERIVA",
      "path": "/Users/Marc/projects/deriva",
      "seeded_at": "2026-05-06",
      "seeded_from": "2.6-taxonomy",
      "last_sync": "2026-05-06"
    }
  ]
}
```

---

## Migración desde el modelo actual

El modelo actual (`bago_core` con todo) pasa a ser el PADRE definitivo. No hay cambio en `bago_core` excepto:

1. **Añadir** `bago siembra` como nuevo comando
2. **Añadir** `siembras.json` en `.bago/state/`
3. **Implementar** la lógica de `create` (copia selectiva de tools + pack.json mínimo)

Los proyectos que actualmente usan BAGO vía alias global deben migrar a siembra:

```
# En bago_core (PADRE):
bago siembra create /path/a/mi-proyecto
```

Esto genera `.bago/` mínimo en el proyecto y configura `BAGO_PADRE_PATH` en `.bago/pack.json`.

---

## Qué NO cambia en v3.0

- El PADRE (`bago_core`) sigue funcionando exactamente igual
- Todos los comandos actuales siguen funcionando
- No hay breaking changes para el flujo de trabajo actual
- El PADRE puede usarse sin ninguna siembra

---

## Plan de implementación (v3.0)

> **Prerrequisito:** v2.6.x estable (health 100/100, 7/7 tool_guardian tests) y bugs cross-platform corregidos (commit 80ebd27)

### Fase 1 — Infraestructura (1 sesión)
- [ ] Crear `.bago/state/siembras.json`
- [ ] Crear `siembra_manager.py` (lógica create/list/update/diff/sync)
- [ ] Registrar `bago siembra` en `tool_registry.py`

### Fase 2 — Launcher de siembra (1 sesión)
- [ ] Crear template `bago_siembra_launcher.py`
- [ ] Implementar delegación PADRE/local en el launcher
- [ ] Crear `BAGO_PADRE_PATH` resolver (env var → pack.json → autodiscovery)

### Fase 3 — Primera siembra real (1 sesión)
- [ ] `bago siembra create /path/DERIVA` (proyecto DERIVA como primer caso real)
- [ ] Verificar que herramientas project/both funcionan en la siembra
- [ ] Verificar que comandos framework delegan al PADRE correctamente

### Fase 4 — Validación y release (1 sesión)
- [ ] Tests de integración para siembra
- [ ] Documentación de usuario (README siembras)
- [ ] `bago health` en PADRE verifica integridad de siembras registradas
- [ ] Release v3.0

---

## Decisiones de diseño (frozen)

| # | Decisión | Razón |
|---|----------|-------|
| D1 | Un solo PADRE por entorno (no múltiples frameworks) | Evita conflictos de versión y estado |
| D2 | La siembra usa `bago.db` local (no la del PADRE) | Cada proyecto tiene sus propias ideas y sesiones |
| D3 | `BAGO_PADRE_PATH` via env var + pack.json (no hardcode) | Portabilidad entre máquinas |
| D4 | La siembra NO puede modificar herramientas del PADRE | Evita corrupción del framework |
| D5 | `bago siembra update` solo actualiza tools, no state | El state del proyecto es intocable por el PADRE |
| D6 | Siembras registradas en PADRE (siembras.json) | El PADRE puede auditar y sincronizar |

---

*Spec creado el 2026-05-06. No implementar hasta aprobación explícita de Marc.*
