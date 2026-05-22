# Principio de Coherencia BAGO — Variables Acumulativas

## Regla de oro
"Si hago A, luego hago B, no debería tener que volver a hacer A."

Cada tarea debe dejar VARIABLES (estado, infraestructura, conocimiento)
que las siguientes tareas reutilicen sin repetir trabajo.

## Ejemplos aplicados

### Mal (no coherente)
1. Crear launcher BAGO.ps1
2. Hacer tests del launcher
3. Detectar que el launcher no está en PATH
4. Volver a editar el launcher para PATH
5. Volver a testear

→ Se repite paso 2 porque el paso 1 no dejó la variable PATH lista.

### Bien (coherente)
1. Crear launcher + instalar en PATH (deja variable: BAGO disponible global)
2. Hacer tests (usa la variable, no repite instalación)
3. Usar BAGO contribute (usa la misma variable)

→ Cada paso acumula. No se repite.

## Jerarquía de variables (de más a menos persistente)

1. **Infraestructura** (PATH, directorios, configs) — dura sesiones
2. **Estado** (índices, health checks, historial) — dura entre comandos
3. **Aprendizaje** (knowledge, lessons) — dura entre agentes
4. **Salida** (archivos, commits) — dura entre sesiones

## Decisión de siguiente paso

Dadas las tareas pendientes:
- BAGO contribute → requiere PATH (infraestructura)
- Tests → requieren PATH (infraestructura)
- BAGO global → crea PATH (infraestructura)

El paso más coherente: **BAGO como comando global**.
Deja la variable que todo lo demás usa.

## Fecha
2026-05-14
