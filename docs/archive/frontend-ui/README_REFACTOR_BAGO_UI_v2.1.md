# BAGO UI Frontend · Refactor v2.1

## Estado

Versión de corrección sobre `FRONTEND_REFACTORIZADO_BAGO_UI_v2.zip`.

Objetivo de esta iteración: resolver los bloqueos TypeScript detectados por VAL sin rediseñar la interfaz.

## Cambios aplicados

- `ActiveSection` ya no incluye `providers` como sección de navegación principal.
- El estado persistido que aún tenga `activeSection: "providers"` se normaliza a `system`.
- `MainSidebar` importa `OpeningDecision` desde `contracts/backend`.
- `ControlPlane` importa `Icon` para el overlay de ayuda.
- Snapshot de error incluye `canSeedWorkspace`.
- Acceso a `nextSnapshot.permissions` protegido cuando el snapshot puede ser `null`.
- `ControlSections` elimina la rama muerta `providers` y protege `onConfigureProvider` opcional.
- `SystemTabs` normaliza objetos dinámicos antes de leer propiedades anidadas.
- Condicionales JSX sobre valores `unknown` se convierten a booleanos explícitos.
- `setRoutes` recibe cast seguro a `Record<string, unknown>`.

## Validación ejecutada

```bash
npm ci
npm run build
npx tsc --noEmit
npm audit --audit-level=low
```

## Resultado

- `npm ci`: OK.
- `npm run build`: OK.
- `npx tsc --noEmit`: OK.
- `npm audit --audit-level=low`: FAIL por vulnerabilidades heredadas de `vite/esbuild`.

## Nota sobre seguridad de dependencias

`npm audit fix --force` propone instalar una versión mayor de Vite con posible ruptura. No se ha aplicado en esta iteración porque el objetivo era corregir contratos TypeScript sin introducir cambios de plataforma.

## Estado recomendado

`BAGO-EJEC-FrontendRefactorFix-v2.1-HANDOFF-C03`

La siguiente validación debe ejecutar la UI contra backend BAGO real y probar:

- `GET /api/v1/ui/bootstrap`
- `GET /api/v1/events`
- `POST /chat`
- `POST /chat/stream`
- `POST /api/v1/commands`
- `GET /jobs/summary`
- `GET /evidence/receipts`
- `GET /files/list`
- `GET /workspace/status`
