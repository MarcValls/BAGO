# Learned Lessons — BAGO Framework

> Lecciones extraídas de iteraciones reales. Cada entrada tiene contexto, patrón y
> qué hace que funcione. Son guías para futuros agentes y sesiones.

---

## LL-001 — Orquestación en Espiral con Agentes Paralelos

> CONTENIDO FUSIONADO DESDE RAÍZ.

> **Fecha:** 2026-05-13
> **Sesión:** Anti-orphan shield + Shepard Loop + Modularización 9 CRIT
> **Trigger:** `file_size_guard` detectó 9 archivos >800 líneas en `.bago/tools/`
> **Resultado:** 3 agentes paralelos procesando 9 monolitos simultáneamente

### El patrón observado

```
DETECTAR (automático) → CLASIFICAR (por prioridad/tamaño) → AGRUPAR (en batches)
       → DELEGAR (agentes paralelos) → VERIFICAR (validate GO + tests)
              → COMMIT (por archivo) → CICLO SIGUIENTE
```

Esto **es** el Bucle de Shepard aplicado a sí mismo:
- **SCAN**: `bago health monolith` / `file_size_guard --json` detecta los CRITs
- **ALERT**: `health check` los muestra como `✗` con nombre y líneas
- **REMEDIATE**: agentes paralelos modularizan — cada uno con 3 archivos, splits claros
- **VERIFY**: cada agente corre `python3 bago validate` antes de commit
- **EVOLVE**: el propio conocimiento de "cómo partir" queda en el código nuevo

### Por qué funcionó

1. **Detección automática** — no fue un humano quien listó los 9 archivos, fue `file_size_guard`
2. **Criterio objetivo** — CRIT >800L / WARN >600L — no ambigüedad sobre qué actuar
3. **Batches balanceados** — 3×3 archivos, ordenados por líneas descendente dentro de cada batch
4. **Split pattern consistente** — siempre: `_<dominio>_<capa>.py` privado + orquestador delgado
5. **Verificación integrada** — cada agente verifica antes de commit, no al final
6. **Commits atómicos** — un commit por archivo procesado, mensaje canónico

### Estructura del split sugerida (plantilla)

```
archivo_grande.py (>800L)
    ├── _archivo_model.py     — dataclasses, tipos, constantes, schema
    ├── _archivo_collectors.py — recoge datos de fuentes externas
    └── _archivo_renderers.py  — formatea output (markdown, json, console)

archivo_grande.py (resultado) — ≤150L — importa de los privados, CLI, main()
```

### Cuándo aplicar este patrón

- Cualquier `.py` que supere CRIT_LIMIT (actualmente 800L)
- Cuando un archivo mezcla >2 responsabilidades identificables
- Cuando un archivo tarda >1s en importar (señal de demasiada lógica en top-level)

### Cuándo NO aplicar

- Archivos de datos puros (registries, configs grandes) → usar `_EXCLUDE`
- Tests de integración (monolítico por diseño) → usar `_EXCLUDE`
- Archivos con estado global compartido difícil de partir → marcar como WARN, documentar razón

### Qué evitar

- ❌ Crear módulos privados sin que el original los importe → genera huérfanos
- ❌ Mover código sin verificar que el entrypoint público sigue funcionando
- ❌ Commits masivos de todos los archivos juntos → dificulta bisect y rollback
- ❌ Partir por tamaño sin identificar responsabilidades reales primero

---

## LL-002 — El Agente que Sobreescribe su Propia Herramienta

> **Fecha:** 2026-05-13
> **Contexto:** Agente `orphan-shield` creó `orphan_shield.py` y `doc_index.py` correctamente,
> pero sobreescribió `file_size_guard.py` con una versión simplificada que perdió la API pública
> **Impacto:** `health check` falló con `module has no attribute 'scan'`
> **Fix:** 10 minutos de restauración manual

### Lección

Cuando un agente trabaja en un módulo que **ya tiene API pública usada por otros módulos**,
debe:
1. Leer el módulo existente antes de cualquier modificación
2. Verificar qué funciones son llamadas externamente (`grep -r "file_size_guard"`)
3. Si modifica, mantener retrocompatibilidad de la API pública
4. Nunca sobreescribir con una versión "más simple" sin verificar los contratos

### Señal de alerta

Si un agente crea un archivo con el mismo nombre que uno existente → **STOP, leer el existente primero**.

---

## LL-003 — Documentar Para No Huerfanar

> **Fecha:** 2026-05-13
> **Contexto:** `doc_index.py` detectó 109 tools sin cobertura documental
> **Causa:** Herramientas creadas sin añadir `<!-- @covers: ... -->` en ningún `.md`

### Lección

Cada tool creada debe mencionarse en al menos un `.md` de `.bago/docs/` o `README.md`.
El patrón mínimo:

```markdown
<!-- @covers: nombre_herramienta.py, otra_herramienta -->
```

O mencionarla en una tabla de comandos con backticks:

```markdown
| `bago orphan-shield` | Detecta archivos huérfanos |
```

Ambas formas son detectadas por `doc_index.py`. No hace falta una sección dedicada.

---

*Este archivo crece con cada sesión. Formato: LL-NNN — Título corto.*
*Citar al inicio de sesión si el problema encaja con una lección anterior.*
