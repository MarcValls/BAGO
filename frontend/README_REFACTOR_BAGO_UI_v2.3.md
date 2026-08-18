# FRONTEND_REFACTORIZADO_BAGO_UI_v2.3

Estado: DRAFT_VALIDADO_LOCALMENTE_CON_CAPTURAS

## Objetivo

Iteración VAL + EJEC sobre v2.2 para mejorar la UI sin cambiar contratos backend y entregar capturas de todas las pantallas navegables.

## Cambios v2.3

- Añadida capa de preparación operativa en el header de cada sección.
- Añadido flujo operativo en Home: Conectar, Vincular, Certificar, Ejecutar.
- Mejorado Chat con chips rápidos para comandos frecuentes.
- Eliminado efecto colateral detectado en VAL: el workspace ya no abre el inspector automáticamente al cargar la app.
- Mejoradas superficies visuales para captura: sombras, jerarquía, separación de paneles y estados.
- Mantenida la arquitectura v2.2: bootstrap canónico, SSE, chat toggle, inspector drawer y sidebar jerárquico.

## Pantallas capturadas

1. Home cockpit
2. Workspace
3. Grafo
4. Pipeline
5. Evidencia
6. Contexto
7. Operación / sistema
8. Chat split
9. Command palette
10. Help overlay
11. Inspector drawer

Las capturas se generaron con un backend mock compatible con el inventario BAGO para visualizar estados reales sin depender del backend vivo del entorno.

## Validación local

- `npm ci`: OK
- `npm run build`: OK
- `npx tsc --noEmit`: OK
- `npm audit`: FAIL no bloqueante por Vite/esbuild heredado

## Bloqueo para CANON

Sigue faltando validación con backend BAGO real contra:

- `GET /api/v1/ui/bootstrap`
- `GET /api/v1/events`
- `/chat`, `/chat/stream`, `/api/v1/commands`
- workspace, files, evidence, jobs y router

## Nota

No se aplicó `npm audit fix --force` porque propone salto mayor de Vite y debe tratarse como ciclo separado de dependencias.
