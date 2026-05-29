# Binarios embebidos · BAGO

Este directorio (`\.bago\bin\`) contiene binarios de terceros embebidos necesarios para el funcionamiento del framework.

## Archivos actuales

| Archivo | Versión | Origen | Uso |
|---------|---------|--------|-----|
| `gh.exe` | — | GitHub CLI | Operaciones GitHub (releases, issues, PRs) |

## Regla

- Los binarios deben ser los mínimos indispensables.
- Preferir herramientas ya instaladas en el sistema antes de embeber nuevas.
- Documentar origen, versión y licencia de cada binario añadido.
- No incluir binarios de más de 50 MB salvo justificación explícita.
