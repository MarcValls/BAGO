# Contrato REPL de BAGO v4

## Alcance

Este contrato cubre el parser de comandos y la superficie mínima del REPL. La referencia operativa es `.bago\chat\commands.py` y `.bago\chat\repl.py`.

## Forma mínima de respuesta

Todo comando reconocido debe devolver un `dict` con:

- `ok: bool`
- `message: str`
- `action: str` cuando el comando delega una acción especial (`quit`, `menu`, etc.)

Los comandos que generan estructuras adicionales pueden añadir claves como `plan`, `provider`, `model` o `session_id`, pero no pueden omitir `ok` ni `message`.

## Garantías mínimas

| Comando | Garantía demostrable |
|---------|----------------------|
| `/help` | Devuelve un resumen navegable de comandos disponibles. |
| `/menu` | Activa una navegación agrupada de funciones sin alterar la sesión. |
| `/status` | Devuelve session id, provider, modelo, salud y métricas básicas. |
| `/save` | Persiste la sesión activa en `.bago\state\sessions`. |
| `/load <session_id>` | Recupera una sesión guardada por id. |
| `/switch <provider> [modelo]` | Intenta cambiar el motor sin perder la sesión. |
| `/plan <tarea>` | Genera un plan en texto y actualiza el plan activo del runtime. |
| `/memory add/search/list/delete` | Opera sobre conocimiento persistente recuperable. |
| `/quit` | Señala salida ordenada del REPL con `action: "quit"`. |

## Modos demostrables

### Simulado

Debe pasar sin red ni credenciales usando:

```powershell
python bago_core\cli.py evidence --mode simulated --objective community-knowledge --output docs\evidence\ui_shell_current --overwrite
```

La evidencia simulada debe incluir:

- `commands\results.json`
- `session\context.jsonl`
- `session\session.json`

### Real

Debe validar contra un provider vivo:

```powershell
python bago_core\cli.py evidence --mode real --provider <provider> --model "<modelo>" --output <directorio>
```

El modo real falla si el provider no responde o si la respuesta queda vacía.

## Validación base

```powershell
python test_e2e.py
python .bago\chat\commands.py --test
```
