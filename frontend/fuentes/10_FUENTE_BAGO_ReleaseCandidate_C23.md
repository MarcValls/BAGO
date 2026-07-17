# FUENTE 10 · BAGO Release Candidate C23

## Propósito

Registrar la preparación del release candidate posterior a la reconstrucción de dependencias C21.

## ID operativo

`BAGO-EJEC-ReleaseCandidate-v0.6-HANDOFF-C23`

## Estado

DRAFT técnico validado. Pendiente de validación visual/manual final antes de CANON completo del frontend.

## Base

`BAGO_FRONTEND_DEPENDENCY_REBUILD_C21.zip`

## Cambios definidos

- Se añade `engines` en `package.json` para fijar runtime compatible con Vite 8.
- Se añade `.nvmrc` con `22.16.0`.
- Se añade `.node-version` con `22.16.0`.
- Se actualiza `package-lock.json` para reflejar `engines`.

## Runtime requerido

```text
Node: ^20.19.0 || >=22.12.0
npm:  >=10.0.0
```

Runtime validado:

```text
Node: v22.16.0
npm:  10.9.2
```

## Validaciones pasadas

```text
npm ci                            OK
npm run build                     OK
npx tsc --noEmit                  OK
npm audit --audit-level=moderate  OK / 0 vulnerabilities
npm run dev                       OK / HTTP 200
npx vite preview                  OK / HTTP 200
```

## Decisión

La reconstrucción de dependencias y el contrato de runtime quedan listos como release candidate técnico.

## Pendiente

- CRIT debe hacer validación final visual/funcional.
- Confirmar entorno Node real de BAGO.
- No marcar el frontend completo como CANON hasta esa confirmación.

## Riesgo

Si BAGO se ejecuta en Node 18 o Node 20 anterior a 20.19.0, Vite 8 puede no ser compatible.
