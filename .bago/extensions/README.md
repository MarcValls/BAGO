# Extensiones · BAGO

Este directorio (`\.bago\extensions\`) aloja extensiones opcionales del framework.

## Extensión registrada

| Extensión | Tipo | Descripción |
|-----------|------|-------------|
| `bash-runner` | Node.js | Ejecutor de comandos bash vía extensiones Copilot |

## Cómo añadir una extensión

1. Crear subdirectorio: `mkdir .bago/extensions/mi_extension`
2. Añadir `extension.mjs` o script de entrada.
3. Registrar en `.bago/extensions/README.md` (este archivo).
4. Validar con `bago extensions check`.

## Regla

Las extensiones nunca deben depender de rutas absolutas del sistema anfitrión. Usar siempre rutas relativas a `BAGO_ROOT`.
