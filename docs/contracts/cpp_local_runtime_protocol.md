# Protocolo `cpp-local` — fase 1

Este documento define la frontera mínima entre BAGO Python y un runtime local externo escrito en C++.

## Objetivo

Permitir que el runtime C++ actúe como motor local detrás de `ProviderAdapter`, sin mover fuera de Python:

- la sesión,
- la persistencia,
- la memoria,
- las tools,
- los contratos.

## Transporte recomendado

**Fase 1:** HTTP local en `127.0.0.1`  
**Fase futura opcional:** stdio o named pipe

## Endpoints mínimos

### `GET /health`

Respuesta esperada:

```json
{
  "ok": true,
  "detail": "cpp-local runtime reachable",
  "latency_ms": 2.1,
  "models_available": 1
}
```

### `GET /models`

Respuesta esperada:

```json
{
  "models": [
    {
      "id": "bago-cpp:default",
      "wire_name": "bago-cpp:default",
      "context_tokens": 32768,
      "max_output_tokens": 4096,
      "best_for": "general",
      "cost": "local",
      "available": true
    }
  ]
}
```

También se acepta una lista simple de strings como compatibilidad inicial.

### `POST /chat`

Request:

```json
{
  "model": "bago-cpp:default",
  "messages": [
    {"role": "system", "content": "..." },
    {"role": "user", "content": "hola" }
  ],
  "system": "",
  "temperature": 0.7,
  "stream": false,
  "max_tokens": 512
}
```

### `POST /chat_stream`

Request: mismo payload que `/chat`.

Respuesta: stream NDJSON donde cada línea contiene un chunk:

```json
{"delta":"hola "}
{"delta":"mundo"}
{"done":true,"model_used":"bago-cpp:default","usage":{"input_tokens":2,"output_tokens":2,"total_tokens":4,"calls":1}}
```

### `POST /embed`

Request:

```json
{
  "model": "bago-cpp:default",
  "texts": ["recuerdo 1", "recuerdo 2"]
}
```

Response:

```json
{
  "model_used": "bago-cpp:default",
  "embeddings": [
    [0.1, 0.2, 0.3],
    [0.4, 0.5, 0.6]
  ]
}
```

Response:

```json
{
  "content": "respuesta del runtime",
  "model_used": "bago-cpp:default",
  "finish_reason": "stop",
  "usage": {
    "input_tokens": 12,
    "output_tokens": 21,
    "total_tokens": 33,
    "calls": 1
  },
  "metadata": {
    "backend": "cpp-runtime"
  },
  "tool_calls": []
}
```

## Reglas de autoridad

1. El runtime C++ **no** es dueño de la sesión persistida.
2. Python decide cuándo guardar la conversación y cuándo ejecutar tools.
3. El runtime C++ devuelve inferencia y métricas, no decisiones de producto.
4. Si el runtime falla, BAGO debe fallar sin persistir un turno huérfano.

## Capacidades vigentes tras fases 2–6

- `chat`: sí
- `chat_stream`: sí, mediante NDJSON
- `tool_calls`: sí, con el mismo shape normalizado que espera `tool_registry`
- embeddings: sí
- memoria vectorial: sí, pero almacenada y gobernada por Python

## Validación mínima

```powershell
python .\bago_core\cpp_runtime_host.py --test
python .\.bago\providers\cpp_local.py --test
python .\.bago\core\embedding_store.py --test
python .\bago_core\launcher.py --test
python .\test_e2e.py
```
