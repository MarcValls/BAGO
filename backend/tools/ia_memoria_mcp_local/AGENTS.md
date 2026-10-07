# Instrucciones para agentes

1. No añadir shell, subprocess, red o lectura arbitraria.
2. Toda ruta pasa por `safe_resolve`.
3. La raíz de memoria es el único filesystem autorizado.
4. Una propuesta no es memoria activa hasta `memory_commit`.
5. Deprecar en lugar de borrar historia.
6. Markdown es fuente humana; SQLite es índice y registro.
7. Lecturas marcadas `readOnlyHint=true`.
8. Escrituras en mundo cerrado: `openWorldHint=false`.
9. Ejecutado no equivale a verificado.
10. Compilar y probar antes de declarar cierre.
