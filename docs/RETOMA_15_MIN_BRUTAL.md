# Retoma 15 Min Brutal

## Qué está abierto

- El árbol tiene dos capas mezcladas: runtime y estado generado.
- `E:\bago_fw` es el checkout/runtime real.
- `E:\bago_projects\task_manager` es el único proyecto visible ahora.
- `validate_pack` pasa.
- `bago smoke` pasa.
- `health_score` está en `100 green`.
- Sigue habiendo suciedad de git por estado y docs nuevas.

## Qué no tocar

- No mezclar `bago_core/` con `.bago/state/`.
- No tocar `global_state.json` si no estás cerrando una cosecha o una sesión.
- No intentar arreglar todo a la vez.
- No saltar entre copias distintas del runtime.
- No empezar otro proyecto nuevo.

## Qué hacer hoy en 15 minutos

1. Ejecuta:

```powershell
python .bago\tools\validate_pack.py
python .bago\tools\smoke_runner.py
```

2. Mira `git status --short`.

3. Elige solo una vía:

- `limpieza`: separar código de estado generado.
- `producto`: volver a `E:\bago_projects\task_manager`.
- `estabilidad`: validar instalación limpia real.

## Regla final

- Un árbol.
- Un frente.
- Un resultado.
