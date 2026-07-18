# W6 · Ideación Aplicada

## id

`w6_ideacion_aplicada`

## Objetivo

Analizar el repo y proponer ideas contextualizadas, priorizadas por implementabilidad y estabilidad.

## Flujo

1. Leer el estado y el contexto real del repo.
2. Detectar oportunidades de mejora o extensión que entren en contexto.
3. Priorizar las ideas por impacto, riesgo y coste de implementación.
4. Devolver una lista corta de ideas accionables.
5. Pedir una descripción detallada de una idea concreta si hace falta.
6. Confirmar si la idea elegida entra en `W2`.
7. Descartar propuestas que añadan complejidad innecesaria o comprometan estabilidad.

## Criterio

Las ideas deben ser:

- coherentes con el repo
- pequeñas o medianas
- implementables sin romper estabilidad
- claras para convertirlas luego en `W2`

## Regla

No generar brainstorming abstracto. Toda idea debe poder aterrizarse en una tarea técnica concreta.

## Comando sugerido

- `./ideas`
- `./ideas --detail N`
- `./ideas --accept N`
- `make ideas`
- `./workflow-info W1`
- `make workflow-info WF=W1`
