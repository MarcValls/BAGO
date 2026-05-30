# Comunidad abierta de conocimiento — visión v4

BAGO v4 trata el conocimiento como un bien reutilizable: una conversación útil no debe quedarse en una respuesta efímera, sino convertirse en memoria recuperable, plan reutilizable y evidencia verificable.

## Objetivo

Construir un repositorio abierto donde cada mejora relevante deje:

1. **Ayuda directa al usuario**: una respuesta o acción concreta.
2. **Ayuda indirecta a la comunidad**: conocimiento persistente, contrato actualizado o herramienta reusable.
3. **Evidencia reproducible**: un bundle que permita demostrar qué se hizo, cómo se validó y qué artefactos quedaron.

## Principios operativos

- **La sesión es la fuente de verdad**: la ayuda se rastrea desde `context.jsonl`, `timeline.jsonl`, `tokens.json` y `meta.json`.
- **La evidencia vale más que la intención**: una capacidad no cuenta como contrato hasta que existe un comando que la valide.
- **El conocimiento debe ser recuperable**: toda contribución útil debe poder buscarse después con `/memory search`.
- **Simulado y real son complementarios**: el modo simulado protege reproducibilidad; el modo real prueba utilidad frente a un provider vivo.
- **Los artefactos deben servir**: un bundle, plan o memoria debe poder asistir a otro usuario o a una tarea futura.

## Bucle de contribución

1. Identificar una necesidad concreta del usuario.
2. Convertirla en cambio verificable o nuevo artefacto.
3. Registrar lo aprendido como conocimiento persistente o contrato.
4. Generar evidencia con `bago evidence`.
5. Publicar la mejora con trazabilidad suficiente para que otra persona la pueda repetir.

## Fuente de verdad contractual

- `docs\contracts\bago_v4_runtime_contract.json`
- `docs\contracts\bago_v4_repl_contract.md`
- `docs\contracts\bago_v4_evidence_contract.md`
- `docs\contracts\bago_v4_knowledge_contract.md`

