# BAGO Release Candidate C23

## ID operativo

`BAGO-EJEC-ReleaseCandidate-v0.6-HANDOFF-C23`

## Base

Derivado de `BAGO_FRONTEND_DEPENDENCY_REBUILD_C21.zip`.

## Cambios aplicados

- Añadido contrato de runtime en `package.json`:

```json
"engines": {
  "node": "^20.19.0 || >=22.12.0",
  "npm": ">=10.0.0"
}
```

- Añadido `.nvmrc` con Node validado:

```text
22.16.0
```

- Añadido `.node-version` con Node validado:

```text
22.16.0
```

- Actualizado `package-lock.json` para reflejar el campo `engines` en el paquete raíz.

## Dependencias principales

```text
vite                 ^8.1.4
@vitejs/plugin-react ^6.0.3
typescript           ^5.9.3
react                ^18.3.1
react-dom            ^18.3.1
```

## Validación ejecutada

Entorno usado:

```text
node v22.16.0
npm 10.9.2
```

Comandos validados:

```text
npm ci                            OK
npm run build                     OK
npx tsc --noEmit                  OK
npm audit --audit-level=moderate  OK / found 0 vulnerabilities
npm run dev                       OK / HTTP 200
npx vite preview                  OK / HTTP 200
```

## Resultado

Este paquete queda como release candidate técnico. La reconstrucción de dependencias está limpia y el runtime Node queda fijado explícitamente.

## Pendiente antes de CANON completo

- Validación visual/manual final en el entorno real BAGO.
- Confirmar que el entorno de despliegue usa Node `^20.19.0 || >=22.12.0`.
- Si el entorno real usa Node 18 o Node 20 antiguo, no usar este release candidate sin adaptar runtime o buscar una mitigación alternativa.

## No incluido

- `node_modules` no se incluye en el ZIP.
- No se modificó backend.
- No se añadieron nuevas acciones contextuales.
