# Taxonomía de estados BAGO

Esta taxonomía separa dos dominios:

- Estado técnico de runtime.
- Estado de madurez de implementación.

No deben mezclarse bajo una misma etiqueta genérica.

## Estados de madurez

- `No iniciado`
- `En implementación`
- `Implementado parcialmente`
- `Implementado y pendiente de integración`
- `Integrado y pendiente de validación`
- `Validado`
- `Canonizado`

## Regla operativa

- `status` o `state` siguen describiendo runtime, sesión, pipeline o contexto técnico.
- `implementation_state` describe madurez de entrega y debe usar uno de los siete valores anteriores.
- `falta cerrar` no se usa como estado canónico porque no distingue alcance, integración ni validación.

## Correspondencia recomendada

- Backend: declarar `implementation_state` de forma explícita.
- UI: mostrar la etiqueta exacta, sin traducirla a `pending` o `partial`.
- Auditoría: citar el dominio del estado cada vez que se compare avance técnico con avance de madurez.
