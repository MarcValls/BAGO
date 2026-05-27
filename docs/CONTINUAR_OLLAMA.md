# Informe de continuidad para Ollama

Fecha: 2026-05-27

## Estado actual

- `bago llm status` funciona y confirma que Ollama está activo en `localhost:11434`.
- El runtime de BAGO ya reconoce el motor local y el catálogo de modelos.
- `bago llm` ya expone:
  - `status`
  - `models`
  - `download [ID]`
  - `start [ID]`
  - `stop`
  - `chat <mensaje>`
  - `node`
- La detección y normalización de IDs de modelos ya está corregida para varios alias y tags.
- `send.now` ya se separó como flujo propio con `bago sendnow`, no debe mezclarse con el trabajo de Ollama.

## Lo importante para continuar

- Prioridad: estabilizar la ruta local de Ollama, no la nube.
- El objetivo práctico es que BAGO:
  - detecte bien Ollama local,
  - descargue modelos sin romper IDs,
  - arranque y pare el servidor de forma predecible,
  - elija el modelo local correcto cuando el contexto lo pida.

## Pendientes recomendados

1. Revisar la descarga de modelos con `bago llm download <id>`.
2. Verificar que los IDs canónicos y aliases resuelvan al tag correcto.
3. Probar `bago llm start <id>` con un modelo descargado.
4. Confirmar que `bago llm chat <mensaje>` usa el modelo activo esperado.
5. Revisar el routing para que el local sea opt-in y no se cuele como default.

## Riesgos conocidos

- Ollama puede responder activo pero sin modelos descargados.
- Algunos flujos siguen siendo interactivos y requieren terminal real.
- Si se usa un entorno sin consola Windows real, `prompt_toolkit` puede fallar en TUI.
- El servicio `send.now` tiene su propio límite de peticiones y debe tratarse aparte.

## Comandos útiles

```bat
bago llm status
bago llm models
bago llm download qwen25-coder
bago llm start qwen25-coder
bago llm chat "hola"
```

## Nota operativa

- Si algo falla en Ollama, mirar primero:
  - disponibilidad de `ollama.exe`
  - modelos descargados
  - puerto `11434`
  - salida de `bago llm status`
- No mezclar esta línea de trabajo con `send.now`, `portable` o sincronización de repos.
