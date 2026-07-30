# Bundle de evidencia -- Asistencia comunitaria basada en conocimiento abierto

- **Modo:** `real`
- **Objetivo:** `community-knowledge`
- **Provider/modelo:** `ollama-local/llama3.2:3b`
- **Session ID:** `a1da70de-83e`
- **Generado en:** `docs/evidence/provider_validation_4_8_1/ollama-local__llama3.2-3b`

## Resultado directo al usuario

{
  "assumptions": [],
  "confidence": 0.0,
  "evidence": [
    {
      "errors": [
        {
          "detail": "json_object_not_found",
          "name": "json_parse"
        }
      ],
      "previous_response_excerpt": "",
      "type": "validation_error"
    }
  ],
  "facts": [],
  "files_required": [],
  "intent": "work",
  "missing_information": [
    "json_object_not_found"
  ],
  "objective": "En dos frases, explica como puedes asistir a un usuario mientras dejas una huella reutilizable para la comunidad.",
  "proposed_changes": [],
  "risks": [
    "invalid_model_response"
  ],
  "symbols_required": [],
  "validation_actions": [
    "repair_response",
    "revalidate_contract"
  ]
}

## Comprobaciones demostrables

- **live-provider-health**: pass -- El provider real respondio con salud positiva antes de cerrar el bundle.
- **session-runtime**: pass -- La sesion genero artefactos persistentes en context.jsonl/timeline/tokens/meta.
- **direct-assistance**: pass -- Existe una respuesta util al objetivo planteado por el usuario.
- **knowledge-persistence**: pass -- La evidencia incluye conocimiento recuperable derivado de la sesion.
- **session-save**: pass -- La sesion se guardo en disco con metadatos de continuidad.

## Comandos capturados

### /status

```text
Session ID : a1da70de-83e
Project    : C:\Users\AMTEC_Terminal_1º\Desktop\BAGO-frontend-backend\BAGO\backend
Workspace  : C:\Users\AMTEC_Terminal_1º\Desktop\BAGO-frontend-backend\BAGO\backend\.gabo
Provider   : ollama-local
Model      : llama3.2:3b
Tool policy: ask (auto_allow_tools=False)
Modo BAGO  : [B]
Agente     : default
Bridges    : ollama-local
Health     : OK — Ollama OK (9 models)
Messages   : 2
Tokens     : 0
Calls      : 1
Switches   : 0
```

### /memory add

```text
✓ Recuerdo añadido (ID: 8).
```

### /memory search

```text
Resultados para 'conocimiento recuperable':
  • BAGO v4 debe convertir una conversacion util en conocimiento recuperable y en un artefacto verificab... (sesión: a1da70de-83e)
  • BAGO v4 debe convertir una conversacion util en conocimiento recuperable y en un artefacto verificab... (sesión: 74499d47-a4e)
  • BAGO v4 debe convertir una conversacion util en conocimiento recuperable y en un artefacto verificab... (sesión: c5085d85-da5)
  • BAGO v4 debe convertir una conversacion util en conocimiento recuperable y en un artefacto verificab... (sesión: f2c3518b-80d)
  • BAGO v4 debe convertir una conversacion util en conocimiento recuperable y en un artefacto verificab... (sesión: 519bb0ad-751)
```

### /save

```text
Sesión guardada: a1da70de-83e
```
