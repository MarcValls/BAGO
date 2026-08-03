# CAPTAR - Mapeo canonico de comprension de preguntas

Status: canonical_complement
Scope: complemento operativo para interpretacion previa a respuesta
Authority: no sustituye `CANON.MD`, `ReflexiveQuestionRecord`, `ContextEnvelope` ni `ContextReceipt`

## 1. Veredicto

La leccion CAPTAR entra en canon vigente como metodo pedagogico y operativo.
Complementa RC5-R1 porque baja a pasos humanos la regla canonica de no responder
antes de explicar que se interpreto, que evidencia lo sostiene y que queda abierto.

No corrige una regla vigente. La operacionaliza.

## 2. Idea integrada

Una pregunta no queda definida solo por su forma gramatical. Debe conservarse su
funcion comunicativa, su objeto, la accion solicitada, el resultado esperado, las
restricciones, las presuposiciones, la evidencia disponible y los riesgos de mala
interpretacion.

La salida correcta de esta fase no es la respuesta final. Es el contrato que una
respuesta suficiente debe cumplir.

## 3. Mapeo CAPTAR -> canon BAGO

| Fase CAPTAR | Operacion | Campo o contrato canonico | Criterio de suficiencia |
|---|---|---|---|
| Capturar | Conservar la pregunta original sin reescritura destructiva | `literal_question`, `request_id`, evidencia original | La frase original puede reconstruirse sin perdida |
| Aislar | Identificar objeto, accion, dependencias y secuencia | `object_level_target`, `formalization`, `intent`, `unknowns` | No se confunde tema con operacion solicitada |
| Perfilar | Reconstruir situacion, participantes, capacidades, restricciones y ausencias | `ContextEnvelope.objetivo`, `ContextEnvelope.restricciones`, `context_factors`, `assumptions` | Queda claro que se sabe, que falta y que solo se infiere |
| Trazar | Separar lectura literal, contexto, inferencias e hipotesis de intencion | `alternatives`, `selected_interpretation`, `evidence_anchor_ids`, `limits` | Cada interpretacion usada tiene soporte o queda marcada como provisional |
| Arquitectar | Definir contrato de respuesta, formato, profundidad, validacion y criterio de exito | `TaskSpecification`, `response_contract`, `ContextEnvelope`, criterios de aceptacion | Se sabe que debe hacer una respuesta antes de generarla |
| Revisar | Comprobar invenciones, omisiones, trazabilidad, riesgo y suficiencia | `ContextReceipt`, guardrails, estado `blocked`/`partial`/`ready` | No se autoriza respuesta si falta evidencia critica o capacidad real |

## 4. Complementos que aporta

- Distingue de forma explicita forma y funcion de una pregunta.
- Convierte `objeto + accion + resultado esperado` en unidad minima de analisis.
- Distingue incognita, objetivo y resultado esperado.
- Separa saber, poder ejecutar, estar autorizado y poder verificar.
- Trata presuposiciones como claims que pueden requerir evidencia.
- Introduce ausencias criticas como condicion de bloqueo o respuesta parcial.
- Evita seleccionar una intencion no declarada sin soporte.
- Obliga a declarar supuestos cuando se avanza sin aclaracion.
- Define criterio de suficiencia antes de responder.

## 5. No debe hacer

- No sustituye `ReflexiveQuestionRecord`.
- No sustituye `ContextEnvelope`.
- No sustituye `ContextReceipt`.
- No convierte una interpretacion estable en verdad factual.
- No autoriza ejecucion si falta capacidad, permiso o evidencia.
- No permite presentar inferencias como hechos confirmados.

## 6. Brechas de integracion detectadas

Estas piezas estan implicitas en el interprete reflexivo, pero CAPTAR las nombra
con mas precision. Son candidatas a campos o subestructuras futuras:

- `requested_action`: accion principal solicitada.
- `secondary_actions`: acciones secundarias y dependencias.
- `expected_result`: forma concreta de la salida esperada.
- `critical_absences`: datos faltantes que bloquean conclusion responsable.
- `presuppositions`: premisas asumidas por la pregunta.
- `capability_boundary`: diferencia entre saber, ejecutar, autorizar y verificar.
- `response_contract`: operacion, formato, profundidad y criterio de aceptacion.
- `sufficiency_criteria`: condiciones para declarar la respuesta suficiente.

## 7. Estado operativo de una pregunta

CAPTAR clasifica la pregunta antes de responder:

| Estado | Significado | Respuesta permitida |
|---|---|---|
| incomplete | faltan datos criticos | pedir dato concreto o declarar bloqueo |
| provisional | hay hipotesis razonables, pero no certeza | responder con supuestos declarados |
| ready | objeto, accion, contexto y restricciones son suficientes | responder o ejecutar segun autorizacion |
| blocked | falta acceso, permiso, capacidad o evidencia esencial | no simular capacidad; explicar bloqueo |
| invalid | la representacion perdio trazabilidad o contradice evidencia | rehacer interpretacion |

## 8. Regla de integracion

Antes de una respuesta compleja, BAGO debe poder emitir una ficha CAPTAR o una
estructura equivalente dentro de `ReflexiveQuestionRecord`:

```text
pregunta original
-> objeto
-> accion solicitada
-> resultado esperado
-> contexto y restricciones
-> evidencia, inferencias y supuestos
-> ausencias criticas
-> contrato de respuesta
-> estado: incomplete | provisional | ready | blocked | invalid
```

Si la tarea es trivial, CAPTAR puede ser implicito. Si la tarea es compleja,
reflexiva, ambigua, riesgosa o ejecutable, CAPTAR debe quedar trazable.
