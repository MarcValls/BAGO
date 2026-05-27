# Arquitectura de Memoria Distribuida BAGO

_Introducida en sprint ~295. Decisión de diseño del framework._

---

## Problema

Con un solo repositorio (`bago_core`) almacenando estado de todos los proyectos:
- Las sesiones de DERIVA, BIANCA, CATAVIC mezcladas en un mismo directorio
- El framework crece ilimitadamente con historial ajeno
- Imposible aislar el contexto de proyecto al comenzar una sesión

## Solución: Memoria en dos capas

```
Framework (bago_core/.bago/)          Proyecto (<proyecto>/.bago/)
  ├── knowledge/   ← aprendizajes       ├── pack.json          ← config
  │   globales promovidos               ├── state/
  ├── state/                            │   ├── sessions/      ← historial local
  │   ├── global_state.json             │   ├── tasks.json     ← tareas locales
  │   └── (health del framework)        │   ├── learnings.md   ← aprend. locales
  └── tools/                            │   └── context.json   ← contexto actual
                                        └── knowledge/         ← kb específica
```

**Capa 1 — Estado de proyecto** (`<proyecto>/.bago/state/`)
- Sesiones de trabajo en el proyecto
- Tareas pendientes, en progreso, completadas
- Context snapshot al inicio/fin de sesión
- Learnings locales (candidatos a promoción)

**Capa 2 — Knowledge del framework** (`bago_core/.bago/knowledge/`)
- Patrones reutilizables cross-proyecto
- Trampas y antipatrones documentados
- Decisiones técnicas que aplican a múltiples proyectos
- Se enriquece vía `bago promote`

---

## Flujo de trabajo

### Inicio de proyecto nuevo
```bash
cd /ruta/al/proyecto
bago project-init      # Crea .bago/ local
bago project-link      # Vincula al framework → sesiones van al proyecto
```

### Durante la sesión
```bash
bago start             # Abre sesión (se guarda en proyecto/.bago/state/sessions/)
bago learn "aprendizaje importante"   # Guarda en learnings.md local
```

### Al cerrar
```bash
bago promote "patrón genérico que sirve para otros proyectos"
bago done              # SESSION_CLOSE → va al proyecto, no al framework
```

### Cambiar de proyecto
```bash
bago project-link /ruta/otro/proyecto   # Cambia el proyecto activo
# o simplemente navegar al directorio con .bago/ y hacer project-link
```

---

## Comandos

| Comando | Descripción |
|---------|-------------|
| `bago project-init [path]` | Inicializa `.bago/` en el proyecto |
| `bago project-link [path]` | Activa un proyecto (sesiones → proyecto) |
| `bago project-unlink` | Desactiva → sesiones vuelven al framework |
| `bago project-state` | Estado del proyecto activo |
| `bago learn "texto"` | Guarda aprendizaje en learnings.md local |
| `bago promote "texto"` | Promueve al `knowledge/project_patterns.md` |

---

## Proyectos inicializados

| Proyecto | Path | Estado |
|----------|------|--------|
| DERIVA | `/Volumes/DERIVA/` | _pendiente project-init_ |
| Bianca_The_Game | `/Volumes/Bianca_The_Game/` | _pendiente project-init_ |
| CESAR_WOODS | `/Volumes/CESAR_WOODS/` | `.bago/` propio (ya existe) |
| CATAVIC | `/Volumes/CATAVIC_v1_2026/` | _pendiente project-init_ |

---

## Invariantes

1. `bago_core/.bago/knowledge/` es SOLO para learnings cross-proyecto.
2. Nunca borrar sesiones de un proyecto del framework — solo mover hacia adelante.
3. `project-unlink` NO borra el estado local, solo cambia el destino.
4. Si el proyecto vinculado no tiene `pack.json`, `session_close_generator.py` cae al framework (safe fallback).
5. `.bago/state/` de cada proyecto NO se commitea (está en `.gitignore`).

---

_Archivos clave: `project_memory.py`, `session_close_generator.py` (parchado)_
