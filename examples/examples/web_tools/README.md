# BAGO — Web tools

Herramientas HTML estáticas del framework. Este directorio existe para no mezclar
assets web con `.bago/tools/`, que queda reservado para comandos CLI/runtime.

## Herramientas

- `bago_matrix.html` — matriz 2D agente/herramienta.
- `bago_matrix_3d.html` — matriz 3D agente/herramienta.
- `bago_matrix_music_editor.html` — editor musical móvil.
- `bago_mindmap.html` — mapa mental estático.
- `bago_score_transposer.html` — transpositor de partituras.

## Recursos

Algunos HTML cargan librerías desde `../vendor/` para funcionar tanto servidos por
el launcher como abiertos directamente desde el sistema de archivos.