# Informe de continuidad para Ollama

Fecha: 2026-05-27

## Estado actual

- `bago llm status` funciona y confirma que Ollama estÃ¡ activo en `localhost:11434`.
- El runtime de BAGO ya reconoce el motor local y el catÃ¡logo de modelos.
- `bago llm` ya expone:
  - `status`
  - `models`
  - `download [ID]`
  - `start [ID]`
  - `stop`
  - `chat <mensaje>`
  - `node`
- La detecciÃ³n y normalizaciÃ³n de IDs de modelos ya estÃ¡ corregida para varios alias y tags.
- `send.now` ya se separÃ³ como flujo propio con `bago sendnow`, no debe mezclarse con el trabajo de Ollama.

## Lo importante para continuar

- Prioridad: estabilizar la ruta local de Ollama, no la nube.
- El objetivo prÃ¡ctico es que BAGO:
  - detecte bien Ollama local,
  - descargue modelos sin romper IDs,
  - arranque y pare el servidor de forma predecible,
  - elija el modelo local correcto cuando el contexto lo pida.

## Pendientes recomendados

1. Revisar la descarga de modelos con `bago llm download <id>`.
2. Verificar que los IDs canÃ³nicos y aliases resuelvan al tag correcto.
3. Probar `bago llm start <id>` con un modelo descargado.
4. Confirmar que `bago llm chat <mensaje>` usa el modelo activo esperado.
5. Revisar el routing para que el local sea opt-in y no se cuele como default.

## Riesgos conocidos

- Ollama puede responder activo pero sin modelos descargados.
- Algunos flujos siguen siendo interactivos y requieren terminal real.
- Si se usa un entorno sin consola Windows real, `prompt_toolkit` puede fallar en TUI.
- El servicio `send.now` tiene su propio lÃ­mite de peticiones y debe tratarse aparte.

## Comandos Ãºtiles

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
- No mezclar esta lÃ­nea de trabajo con `send.now`, `portable` o sincronizaciÃ³n de repos.

## Instalacion en disco local (C:\bago_true)

**Estructura:**
- C:\bago_true -> clone del repo motor (MarcValls/BAGO)
- C:\bago_true\bago-knowledge -> clone del repo knowledge (MarcValls/bago-knowledge)
- E:\bago_fw\.bago\knowledge -> ahora tambien es un clone de bago-knowledge

**Bidireccionalidad:**
- Ambos apuntan a GitHub como origin (fuente de verdad)
- Remotes cruzados: usb apunta a E:\bago_fw, disk apunta a C:\bago_true
- El script bago_sync_bidirectional.py auto-commitea, hace pull/push entre locales y sube a GitHub

**Estado:**
- bago launch --local funciona desde C:\bago_true
- bago llm status detecta modelos locales en ambas instalaciones
- Sync probado y OK

<!-- SYNC_OK: bidirectional sync verified -->
