# Retoma 15 Min Brutal

## QuÃ© estÃ¡ abierto

- El Ã¡rbol tiene dos capas mezcladas: runtime y estado generado.
- `E:\bago_fw` es el checkout/runtime real.
- `E:\bago_projects\task_manager` es el Ãºnico proyecto visible ahora.
- `validate_pack` pasa.
- `bago smoke` pasa.
- `health_score` estÃ¡ en `100 green`.
- Sigue habiendo suciedad de git por estado y docs nuevas.

## QuÃ© no tocar

- No mezclar `bago_core/` con `.bago/state/`.
- No tocar `global_state.json` si no estÃ¡s cerrando una cosecha o una sesiÃ³n.
- No intentar arreglar todo a la vez.
- No saltar entre copias distintas del runtime.
- No empezar otro proyecto nuevo.

## QuÃ© hacer hoy en 15 minutos

1. Ejecuta:

```powershell
python .bago\tools\validate_pack.py
python .bago\tools\smoke_runner.py
```

2. Mira `git status --short`.

3. Elige solo una vÃ­a:

- `limpieza`: separar cÃ³digo de estado generado.
- `producto`: volver a `E:\bago_projects\task_manager`.
- `estabilidad`: validar instalaciÃ³n limpia real.

## Regla final

- Un Ã¡rbol.
- Un frente.
- Un resultado.
