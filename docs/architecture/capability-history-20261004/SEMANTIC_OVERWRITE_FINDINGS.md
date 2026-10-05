# Semantic overwrite findings

No P0 loss is demonstrated.

## CAP-LOSS-P1-001 · Autopilot perdió límite histórico de 20 pasos

Severity **P1** · `ACCIDENTALLY_LOST` · El handler actual procesa todos los pasos; no hay decisión de retirada localizada.

Evidence: v4.5.0 max_steps=20; semantic-probes current_25_steps=26 calls vs historical=21

Verification: Boundary probe reproducido; provider/runtime real NOT_RUN.

## CAP-LOSS-P1-002 · Agent spawn/list/run/kill cruza dos registros

Severity **P1** · `REPLACED_NON_EQUIVALENTLY` · La continuidad de identidad entre comandos no está demostrada.

Evidence: 4aa0eb66 añade agent_kit list/run/describe/plan antes de spiral_agent spawn/kill/status; cmd_tools.py ramas actuales

Verification: Trace estático; flujo live NOT_RUN.

## CAP-LOSS-P2-001 · Interpretation detail por ID devuelve colección

Severity **P2** · `REPLACED_NON_EQUIVALENTLY` · Contrato cliente/API incoherente; callsite UI no encontrado.

Evidence: legacy_aliases.py redirige detail a history; handlers_interpret ignora ID; client espera InterpretationResult

Verification: Trace estático; HTTP/UI NOT_RUN.

## CAP-LOSS-P2-002 · issues-gh parser sin dispatcher

Severity **P2** · `UNKNOWN` · Defecto conservado, no pérdida nueva demostrada.

Evidence: parser lo declara; dispatcher lo omite; probe devuelve 0 y help; mismo defecto en v4.5

Verification: Boundary probe reproducido.

## CAP-LOSS-P2-003 · RoleSpiralBuilder ausente del backend actual

Severity **P2** · `UNKNOWN` · Implementación exacta ausente; reemplazo conceptual sin resolver.

Evidence: v3.5 role_embedded + test_v35_features; símbolo ausente en backend rastreado; tags desconectados

Verification: Source trace; equivalencia NOT_RUN.

## CAP-LOSS-P2-004 · SignalMetrics band/channel/hz ausente

Severity **P2** · `UNKNOWN` · Preservación no certificable; no se prueba eliminación lineal.

Evidence: v3.5 prompt_router + tests; routing actual no demuestra equivalente

Verification: Source trace; equivalencia NOT_RUN.
