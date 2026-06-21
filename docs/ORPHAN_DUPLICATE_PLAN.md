# Plan de limpieza y conexión

For the row-by-row migration plan, see `docs/BAGO_MIGRATION_SPRINTS.md`.

## 1. Mantener como canónico
- `manager/` como fuente editable del manager.
- `.bago/tools/bago_utils.py` como helper compartido.
- `debt_scanner.py` y `skill_engine.py` como motores internos si siguen siendo dependencias de otras piezas.

## 2. Mantener como generado
- `site-dist/manager/` como espejo de publicación, no como fuente manual.
- No editar a mano `site-dist/manager.html` si es solo alias del build.

## 3. Conectar o archivar
- No hay huérfanos claros en `.bago/tools` con esta heurística.

## 5. Eliminar duplicidades
- Eliminar duplicación manual entre `manager/` y `site-dist/manager/` solo si el build las regenera al vuelo.
- Si ambos deben existir, documentar que `site-dist/` es salida y nunca fuente.

## 6. Regla de cierre
- Un tool nuevo debe tener un solo camino: CLI, docs y una dependencia clara; si no, se queda como soporte interno.

## 7. Soporte interno que no se debe borrar a ciegas
- `.bago\tools\bago_utils.py`
- `.bago\tools\debt_scanner.py`
- `.bago\tools\harmony_gate.py`
- `.bago\tools\skill_engine.py`
