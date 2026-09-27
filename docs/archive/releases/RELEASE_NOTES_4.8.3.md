# BAGO 4.8.3

## Nuevas capacidades

- Profundidad de pensamiento por sesión: Normal, Media, Alta y Máxima.
- Conexión GitHub desde Workspace mediante `gh` autenticado.
- Lectura de repositorio y README desde la interfaz.
- Creación confirmada de repositorios desde UI por `gh` o por la herramienta MCP `github_create_repository`.

## Seguridad MCP

- MCP continúa en solo lectura por defecto.
- La escritura exige `BAGO_MCP_MODE=write`, `BAGO_ALLOW_MUTATING=1` y `confirm=true`.
- La UI muestra los errores de autenticación, permisos o validación sin simular éxito.

## Validación

- Frontend: typecheck, build y 74 tests.
- Backend: `test_ui_static_contract.py` y `test_api_dispatch_route_meta.py` (25 tests, 109 subtests).
- Política MCP de lectura/escritura validada con prueba aislada.
- Smoke HTTP real de `/router/reasoning-depth`, `/github/status` y `/github/mcp-create`.
