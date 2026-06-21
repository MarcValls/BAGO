# CANON · BAGO AMTEC línea canónica previa CORREGIDO

## Naturaleza

El canon es la capa normativa del sistema. En esta edición corregida tiene además una responsabilidad explícita: impedir que la mejora formal destruya la continuidad histórica o que la migración histórica degrade la claridad estructural.

## Principios canónicos

### 1. Manifiesto único y resoluble

`pack.json` es la única fuente de manifiesto operativo y sus rutas deben poder resolverse desde el directorio en que vive el propio archivo.

### 2. Separación de capas

Se distinguen sin mezcla estable:

- interfaz,
- orquestación,
- gobierno,
- producción,
- supervisión,
- persistencia,
- legado preservado,
- herramientas de validación.

### 3. Persistencia dual controlada

La operación actual vive en JSON estructurado; la memoria histórica preservada puede vivir en markdown legado, siempre identificada como legado y nunca como estado vivo dominante.

### 4. Activación mínima suficiente

Ningún rol se activa por costumbre. Se activa por necesidad y por frontera funcional.

### 5. Supervisión no ejecutiva

Auditor Canónico y Vértice observan, recomiendan y endurecen la coherencia, pero no colonizan la ejecución productiva.

### 6. Migración sin pérdida

Cuando una instalación evoluciona, la historia real no se sustituye por ejemplos. Se preserva, se traduce y se referencia.

### 7. Verificabilidad

Todo paquete serio debe poder auditar:

- su manifiesto,
- su estado,
- su árbol,
- su trazabilidad,
- su coherencia documental mínima.

## Fuentes de verdad por ámbito

| Ámbito             | Fuente                                                         |
| ------------------ | -------------------------------------------------------------- |
| manifiesto         | `pack.json`                                                    |
| norma del sistema  | `core/canon/*`                                                 |
| ruta de ejecución  | `core/workflows/*`                                             |
| estado vivo actual | `state/global_state.json` y sesiones JSON activas              |
| historia migrada   | `state/migrated_*` + `docs/migration/legacy/original_bago_v1/` |
| verificaciones     | `tools/*`                                                      |

## Regla de precedencia

1. `pack.json`
2. `CANON.md`
3. contratos
4. workflows
5. roles
6. estado estructurado actual
7. mapeos de migración
8. material legado preservado

## Invalidez canónica

Una propuesta es inválida si:

- introduce una segunda fuente de manifiesto,
- rompe resolubilidad de rutas,
- elimina o simula historia real sin declararlo,
- mezcla estado actual con legado sin distinguirlos,
- infla el sistema con archivos huecos declarados como operativos.

## Criterio de sistema sano

BAGO está sano si puede responder con precisión:

- qué archivo manda,
- qué tarea está abierta,
- qué historial es actual y cuál legado,
- qué roles se activaron y por qué,
- qué cambió y con qué validación.

---

## Reglas aprendidas en producción (2026-05-05)

Origen: sesión cross-learning BIANCA↔DERIVA — sprints previos del bloque BIANCA.

### R-PROD-01 · Frozen decisions deben auditarse contra código real

Una decisión congelada no es verdad hasta que se verifica contra el código del repositorio en el momento de usarla. El estado de `.bago/` puede desfasarse respecto a la realidad del repo.

```
ANTES de confiar en una FD: grep -n "nombre_propiedad" src/
# Si el código contradice la FD → auditar antes de proceder
```

### R-PROD-02 · Build de verificación tras todo edit estructural

Todo edit que modifique la firma de una clase (propiedades, apertura/cierre de método) debe ir seguido de build inmediato. Un build roto en cascada (20+ errores) indica casi siempre un `}` consumido por el edit.

```
PATRÓN PELIGROSO en old_str: terminar justo en el "}" de cierre de método
SOLUCIÓN: incluir siempre ≥1 línea de contexto DESPUÉS del "}"
```

### R-PROD-03 · Cross-learning entre proyectos debe codificarse en knowledge/

Cuando un problema de infraestructura (canvas, audio, routing) se resuelve en un proyecto, la solución debe quedar en `knowledge/` antes de cerrar la sesión, no solo en la memoria del agente. Si no está escrito, no existe para la próxima sesión.

```
Señal de que aplica: mismo síntoma en dos proyectos → verificar knowledge/ antes de resolver
Señal de riesgo: solución copiada sin verificar compatibilidad arquitectónica
```

### R-PROD-04 · knowledge/ es módulo core del sistema

El directorio `knowledge/` tiene el mismo rango que `workflows/`, `canon/` y `agents/`. No es documentación auxiliar — es aprendizaje operativo acumulado del sistema.

| Módulo | Propósito |
|--------|-----------|
| `canon/` | Normas del sistema |
| `workflows/` | Protocolos de ejecución |
| `agents/` | Roles activables |
| `knowledge/` | Aprendizaje producido en proyectos reales |

### R-PROD-05 · Señales de modularización — cuándo revisar y cuándo actuar

**Definición:** Un archivo o clase da "señales de modularización" cuando su crecimiento acumulativo supera umbrales que indican que la cohesión está degradándose. BAGO debe detectarlas y registrarlas, pero NO modularizar automáticamente.

#### Umbrales de señal (cualquiera activa revisión)

| Métrica | Señal moderada | Señal fuerte |
|---------|----------------|--------------|
| Líneas de archivo | > 800 | > 1500 |
| Arrays de estado privados | > 8 | > 12 |
| Timers privados | > 6 | > 10 |
| Capas FX / responsabilidades acumuladas | > 8 | > 14 |
| Responsabilidades distintas en update() | > 3 | > 5 |

#### Checklist de viabilidad (antes de modularizar)

```
□ ¿Cada capa es autocontenida? (no muta estado de otras capas)
□ ¿Existe una interfaz natural? (ej: update(dt, state) + render(ctx, W, H, state))
□ ¿El acoplamiento al estado del padre es uniforme entre capas?
□ ¿El refactor no requiere tocar >30% del archivo?
□ ¿El build puede verificarse inmediatamente después de cada paso?
□ ¿El sprint es DEDICADO al refactor? (no mezclar con sprints de contenido)
```

Si ≥4 cajas son ✅ → modularización viable.
Si <4 → no modularizar todavía; registrar señal en `pending_review` y continuar.

#### Señal ≠ Acción inmediata

```
SEÑAL detectada → revisar checklist → viable → sprint dedicado de refactor
SEÑAL detectada → revisar checklist → no viable → pending_review + continuar
```

**Anti-patrón:** modularizar en medio de un sprint de contenido.
**Anti-patrón:** modularizar por tamaño cuando el patrón de crecimiento es homogéneo y estable.

#### Protocolo de sprint de refactor (cuando se decide actuar)

```
1. Definir la interfaz nueva SIN tocar el código existente
2. Implementar la interfaz en un archivo nuevo → build
3. Migrar UNA unidad primero → build → si verde, continuar
4. Migrar unidad a unidad, build tras cada migración
5. Solo eliminar código antiguo cuando TODAS las unidades estén migradas y build verde
```

---

### R-PROD-06 · Superficie Activa por Condición (SAC)

**Origen:** Sesión 2026-05-07 — integración de `bago audit ast` en BAGO.

**Principio base:** "Pit of Success" (Brad Abrams, Microsoft) — el sistema no espera a ser invocado. Cuando el entorno ya cumple las precondiciones naturales de una herramienta, BAGO reduce la fricción sugiriéndola proactivamente.

**Definición:**

> Cuando el estado del entorno activa las precondiciones de una herramienta de forma natural (sin que el usuario lo haya pedido), BAGO debe sugerirla con el comando exacto, no esperar a que el usuario recuerde que existe.

**Diferencia con R-PROD-04 (knowledge/ como módulo core):**
- R-PROD-04: guardar aprendizajes para que estén disponibles.
- R-PROD-06: detectar cuándo aplicarlos y sugerirlos activamente.

**Condiciones de activación (ejemplos canónicos):**

| Condición detectada | Herramienta sugerida | Señal |
|---|---|---|
| Archivos `.py` modificados en commit | `bago audit ast` | `git diff --name-only` contiene `.py` |
| Health score < 70 al arrancar | `bago audit full` | `bago start` → score bajo |
| Tareas del sprint sin evidencia de test | `bago audit commit` | sprint activo + sin test files en diff |
| Archivo > 800 líneas editado | revisar R-PROD-05 | `wc -l` supera umbral |
| Tool nueva añadida a `.bago/tools/` | `bago audit pack` | `git status` detecta tool nueva |

**Regla de formato:**
La sugerencia siempre incluye el comando exacto a ejecutar:

```
→ Sugerencia SAC: has modificado archivos Python.
  Considera: bago audit ast [directorio]
  (Detecta asimetrías callback/async/fixtures/env sin coste extra)
  Omitir: bago audit ast --skip
```

**Límites:**
- La sugerencia NO bloquea ni interrumpe. Es informativa.
- No se repite en la misma sesión para la misma condición.
- No aplica en modo autonomo/daemon (solo en sesiones interactivas).

**Implementación:**
El módulo `bago_start.py` y los gates de commit/push son los puntos de inyección naturales.
El detector de condición vive en `tools/bago_ast_audit.py` (función `run_audit`).

**Anti-patrones:**
- Sugerir sin dar el comando exacto → aumenta fricción.
- Sugerir en cada operación → fatiga de sugerencias.
- Bloquear si el usuario no acepta → viola principio de supervisión no ejecutiva (Canon §5).
