# Audit Tools Index

Este directorio contiene el paquete Python `audit` y los **wrappers CLI** que lo
consumen.

## Paquete interno (`audit/`)

| Módulo | Propósito | Comando principal |
|--------|-----------|-------------------|
| `audit/__main__.py` | Router/orquestador: `full`, `ast`, `security`, `pack`, `scan`, `commit`, `push`, `doctor`, `heal`, `quality`, `purity` | `bago audit …` |
| `audit/_v2.py` | Auditoría integral (integrity → inventory → reporting → health → workflow) | `bago audit full` |
| `audit/_ast.py` | Análisis AST semántico (callbacks sin handler, async sin await, etc.) | `bago audit ast` |
| `audit/_security.py` | Auditoría de seguridad de dependencias npm | `bago audit security` |

## Wrappers thin (legacy)

Los siguientes scripts son **thin wrappers** que re-exportan el paquete
interno. Se mantienen por compatibilidad con `legacy_registry.py` y scripts
externos. **No añadir nueva lógica aquí** — usar el paquete `audit/` o el
router `bago_audit_router.py`.

| Wrapper | Delega a | Estado |
|---------|----------|--------|
| `audit_v2.py` | `audit._v2` | Legacy (usado por pack.json) |
| `bago_ast_audit.py` | `audit._ast` | Legacy |
| `security_audit.py` | `audit._security` | Legacy |

## Auditores especializados (independientes)

| Script | Propósito | Relación con `audit/` |
|--------|-----------|-----------------------|
| `audit_state_pointers.py` | Detecta punteros huérfanos en `global_state.json` | Independiente |
| `audit_utf8_boilerplate.py` | Detecta/migra bloques UTF-8 duplicados en tools | Independiente |
| `dep_audit.py` | Auditoría de dependencias Python (requirements.txt, etc.) | Independiente |
| `spanish_audit.py` | Detecta inconsistencias ortográficas españolas en claves/rutas | Independiente |
| `bago_learning_audit.py` | Trazabilidad de aprendizaje por proyecto | Independiente |

## Regla de oro

- **Nuevo escáner genérico** → añadir como subcomando en `audit/__main__.py`.
- **Nuevo escáner especializado** → crear script independiente en `tools/`.
- **Nunca** duplicar lógica entre un wrapper thin y el paquete interno.
