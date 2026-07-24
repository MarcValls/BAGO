# Contrato de producto: Contexto BAGO

## Propósito

Contexto es el árbol vivo del proyecto. Organiza el contexto de trabajo de cada tarea dentro del contexto general del proyecto. Las tareas permanecen abiertas como ramas hasta que se cierran con una conclusión y evidencia.

## Ejemplo UI

```text
Proyecto
└── UI
    ├── Pantallas
    │   ├── Inicio
    │   ├── Chat
    │   ├── Workspace
    │   ├── Contexto
    │   └── Evidencia
    ├── Componentes compartidos
    ├── Navegación
    ├── Estados visuales
    ├── Decisiones de diseño
    ├── Problemas detectados
    └── Tareas abiertas
```

## Recopilar contexto

La acción `Recopilar contexto` analiza el historial disponible del Chat y prepara una propuesta de ramas/nodos. Puede pedir aclaraciones al usuario. La propuesta se revisa antes de aplicarse y nunca modifica el árbol sin permiso explícito.

Estados que deben distinguirse:

- aceptado;
- propuesta pendiente;
- no confirmado;
- pregunta abierta;
- rechazado.

Workspace aporta recursos, Chat aporta conversación, Contexto conserva la estructura y Evidencia respalda el resultado.

## Implementación actual

`Recopilar contexto` solicita al modelo una propuesta usando el endpoint de Chat existente y la persiste como propuesta pendiente. Si el modelo no responde, usa el historial local como fallback visible. Cuando detecta UI, propone `UI → Pantallas → tarea abierta`. La detección proactiva desde cada turno del Chat queda como siguiente integración.
