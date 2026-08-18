# Tests, build, CI y runtime

Usa `bago_test_auditor`.

Antes de ejecutar nada:
1. registra git status;
2. inspecciona package scripts, backend test commands y workflows CI.

Ejecuta sólo gates reales y seguros que el entorno permita.
No edites source, config, manifests ni lockfiles.
Registra comandos exactos, exit codes, fallos y evidencia.
Al final vuelve a registrar git status y señala cualquier artefacto generado.

Relaciona tests con capacidades, no sólo con cantidad.
Distingue PASA, FALLA, NO EJECUTABLE y NO CUBIERTO.
