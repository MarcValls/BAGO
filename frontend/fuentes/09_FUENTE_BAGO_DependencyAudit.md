# FUENTE 09 · BAGO Dependency Audit

## ID operativo

BAGO-EJEC-DependencyAudit-v0.1-HANDOFF-C21

## Propósito

Registrar la reconstrucción de dependencias del frontend BAGO después de consolidar el patrón funcional de menú contextual.

## Paquete base

Origen: `BAGO_FRONTEND_CONTEXT_MENU_RIGHTCLICK_EJEC5.zip`

Estado de partida:

- `npm run build`: correcto.
- `npx tsc --noEmit`: correcto.
- `npm audit --audit-level=moderate`: 2 vulnerabilidades detectadas, 1 moderate y 1 high.
- Riesgo principal: Vite/esbuild vulnerable en la línea anterior.

## Cambios aplicados

Se actualizaron dependencias de desarrollo:

```json
{
  "@vitejs/plugin-react": "^6.0.3",
  "typescript": "^5.9.3",
  "vite": "^8.1.4"
}
```

Se probó inicialmente TypeScript 7.0.2, pero se descartó porque rompe la configuración actual de `tsconfig.json` por eliminación de `baseUrl`. Se fija TypeScript 5.9.3 como versión compatible.

## Resultado validado

Comandos ejecutados:

```bash
npm install -D vite@8.1.4 @vitejs/plugin-react@6.0.3 typescript@5.9.3
npm run build
npx tsc --noEmit
npm audit --audit-level=moderate
npm run dev -- --host 127.0.0.1 --port 5173
curl -I http://127.0.0.1:5173/
```

Resultados:

```text
npm run build: correcto
npx tsc --noEmit: sin errores
npm audit --audit-level=moderate: found 0 vulnerabilities
npm run dev: servidor Vite arranca correctamente
curl local: HTTP/1.1 200 OK
```

## Decisión

La reconstrucción de dependencias queda aceptada como candidata funcional.

## Pendiente

Auditoría CRIT visual/funcional del paquete resultante antes de marcar el frontend completo como CANON.

## Riesgos

Vite 8 es cambio mayor respecto a Vite 5. Aunque build, typecheck, audit y dev server pasan, conviene validar manualmente rutas públicas, Electron/dev shell si aplica y comportamiento real en entorno BAGO.

## Próxima acción recomendada

Abrir `BAGO-CRIT-DependencyAudit-v0.1-ON-C22` para validar el ZIP generado.
