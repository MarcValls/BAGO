# BAGO Dependency Rebuild Report

ID operativo: `BAGO-EJEC-DependencyAudit-v0.1-HANDOFF-C21`

Base: `BAGO_FRONTEND_CONTEXT_MENU_RIGHTCLICK_EJEC5.zip`

## Dependencias reconstruidas

- `vite`: `^8.1.4`
- `@vitejs/plugin-react`: `^6.0.3`
- `typescript`: `^5.9.3`

## Nota de compatibilidad

Se descartó `typescript@7.0.2` porque rompe el `tsconfig.json` actual. La versión compatible validada es `typescript@5.9.3`.

## Validación

```text
npm run build                 OK
npx tsc --noEmit              OK
npm audit --audit-level=moderate  OK / found 0 vulnerabilities
npm run dev                   OK
curl local dev server         HTTP/1.1 200 OK
```

## Uso

Ejecutar:

```bash
npm ci
npm run build
npx tsc --noEmit
npm audit --audit-level=moderate
```

El ZIP no incluye `node_modules`. Debe reconstruirse con `npm ci` usando el `package-lock.json` incluido.
