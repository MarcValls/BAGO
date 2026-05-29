# Health Tools Index

Este directorio contiene el paquete Python `health` y los **wrappers CLI** que lo
consumen.

## Paquete interno (`health/`)

| Módulo | Propósito | Comando principal |
|--------|-----------|-------------------|
| `health/__main__.py` | Router/orquestador de health checks | `bago health …` |
| `health/_check.py` | Health check individual (discos, git, python, ollama) | `bago health check` |
| `health/_report.py` | Genera reporte Markdown/HTML de health | `bago health report` |
| `health/_score.py` | Calcula health score numérico (0-100) | `bago health score` |

## Wrappers thin (legacy)

Los siguientes scripts son **thin wrappers** que re-exportan el paquete interno.
Se mantienen por compatibilidad. **No añadir nueva lógica aquí**.

| Wrapper | Delega a | Estado |
|---------|----------|--------|
| `health_check.py` | `health._check` | Legacy |
| `health_report.py` | `health._report` | Legacy |
| `health_score.py` | `health._score` | Legacy |
| `bago_health_router.py` | `health.__main__` | Router oficial (usar este) |

## Regla de oro

- **Nuevo health metric** → añadir a `health/_check.py` o crear módulo en `health/`.
- **Nunca** duplicar lógica entre un wrapper thin y el paquete interno.
