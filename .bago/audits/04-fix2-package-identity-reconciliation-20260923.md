# 04-FIX2 — Reconciliación de identidad del paquete congelado

Fecha: 2026-09-23

Estado de la evidencia: `EXECUTED`

Estado de promoción: `NOT_PROMOTED`

## Resultado

La identidad del baseline congelado queda reconciliada localmente mediante la
pareja inmutable nombre + ruta + SHA-256:

- Artefacto: `C:\Users\AMTEC_Terminal_1º\Documents\ARQUITECTURA_DE_CONTEXTO\BAGO_ARCONTEXT\RED_RAZONAMIENTO_LR_FROZEN_OPEN_2026-09-21.zip`
- Tamaño: `36583` bytes
- SHA-256 real: `e50b310f2d9775979cce813f27fd92640cb4380290204b2da510d38653da60db`
- Contrato 04 incluido: `5db2b02ce92b0618cc51559e275c7d12f8d297ce36831213bd2789a4b5288146`

El ZIP contiene los cinco contratos LR, `OPEN_CONTRACTS_STATUS.md`,
`PACKAGE_MANIFEST.md` y `SHA256SUMS.txt`. La verificación de las siete entradas
declaradas en `SHA256SUMS.txt` devuelve `PASS`, incluido el contrato 04.

## Clasificación del hash anterior

El SHA-256 que figuraba en la decisión y en la review
(`748556bc39e5c41bec642d9812d31fc5fe78a436a9d8734931c1f975eb2a3d68`) no es el
SHA del paquete congelado. Corresponde exactamente a otro artefacto:

- Artefacto: `C:\Users\AMTEC_Terminal_1º\BAGO\output\BAGO-causal-kernel-audit-20260921-a575291c.zip`
- Tamaño: `12802482` bytes
- Contrato interno: `bago.third-party-remediation.v1`
- Candidato: `a575291c`

Ese bundle contiene `audit/bundle-contract.json`, parches y logs de auditoría;
no contiene el baseline documental `RED_RAZONAMIENTO_LR_FROZEN_OPEN_2026-09-21`
y no puede sustituirlo.

## Decisión de reconciliación

1. La autoridad local de BAGO queda vinculada al ZIP congelado de nombre
   `RED_RAZONAMIENTO_LR_FROZEN_OPEN_2026-09-21.zip` con SHA-256 `e50b310f…`.
2. La referencia `748556bc…` se conserva como historial superseded y se
   clasifica como hash del bundle de auditoría, no del baseline.
3. No se renombra, reemplaza, reempaqueta ni modifica ningún ZIP externo ni
   ningún contenido congelado.
4. La review externa que todavía cita `748556bc…` queda identificada como
   proyección stale de procedencia; esta reconciliación local no la presenta
   como evidencia fresca ni altera su archivo original.
5. Esta reconciliación no cierra por sí sola el review 04-FIX2, no promueve el
   contrato y no registra por sí sola el adapter `plan.execute`; la integración
   bounded se documenta separadamente en
   `04-fix2-runtime-integration-20260923.md`.

## Siguiente límite de autoridad

La identidad del paquete ya no es el bloqueo local. El review 04-FIX2 queda
`OPEN / EXECUTED`: los invariantes y retests locales ya se ejecutaron en el
sidecar bounded y Scheduler/PlanEngine están `CONNECTED_SCOPED` al adapter de
`plan.execute`. Siguen pendientes la verificación independiente candidate-bound
y cualquier gate global de inventory; por eso no se promueve a `VERIFIED` ni
`VALIDATED`.
