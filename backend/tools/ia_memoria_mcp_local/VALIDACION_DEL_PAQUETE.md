# Validación del paquete

Fecha: 2026-07-18

## Comprobaciones realizadas

- Compilación de todos los módulos de `src`.
- Inicialización de SQLite.
- Disponibilidad de FTS5.
- Indexación de los documentos iniciales y de los trece volúmenes.
- Detección de los cinco proyectos.
- Rechazo de una ruta con `..`.
- Creación de una propuesta de prueba.
- Confirmación y búsqueda de la memoria de prueba.
- Deprecación sin borrado histórico.
- Limpieza de los artefactos de prueba.
- Reinicialización del índice limpio.

## Resultado

Código compilado y núcleo de persistencia validado.

El handshake MCP no se ejecutó en el entorno de generación porque el SDK `mcp` no estaba preinstalado. El instalador incluye la dependencia estable `mcp>=1.28.1,<2`. Después de instalar, ejecutar `scripts\test_after_install.cmd`.
