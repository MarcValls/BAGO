# Retoma 15 Min Brutal

## QuÃƒÂ© estÃƒÂ¡ abierto

- El ÃƒÂ¡rbol tiene dos capas mezcladas: runtime y estado generado.
- `E:\bago_fw` es el checkout/runtime real.
- `E:\bago_projects\task_manager` es el ÃƒÂºnico proyecto visible ahora.
- `validate_pack` pasa.
- `bago smoke` pasa.
- `health_score` estÃƒÂ¡ en `100 green`.
- Sigue habiendo suciedad de git por estado y docs nuevas.

## QuÃƒÂ© no tocar

- No mezclar `bago_core/` con `.bago/state/`.
- No tocar `global_state.json` si no estÃƒÂ¡s cerrando una cosecha o una sesiÃƒÂ³n.
- No intentar arreglar todo a la vez.
- No saltar entre copias distintas del runtime.
- No empezar otro proyecto nuevo.

## QuÃƒÂ© hacer hoy en 15 minutos

1. Ejecuta:

```powershell
python .bago\tools\validate_pack.py
python .bago\tools\smoke_runner.py
```

2. Mira `git status --short`.

3. Elige solo una vÃƒÂ­a:

- `limpieza`: separar cÃƒÂ³digo de estado generado.
- `producto`: volver a `E:\bago_projects\task_manager`.
- `estabilidad`: validar instalaciÃƒÂ³n limpia real.

## Regla final

- Un ÃƒÂ¡rbol.
- Un frente.
- Un resultado.
