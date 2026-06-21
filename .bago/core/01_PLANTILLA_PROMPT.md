# 01 · PLANTILLA DE PROMPT BAGO

Plantilla estándar para construir prompts internos, handoffs entre roles o tareas acotadas dentro de una sesión.

## Objetivo

Evitar prompts difusos, demasiado generales o incompatibles con el estado y el canon.

## Plantilla

```md
# [TITULO_CORTO]

## 1. Rol objetivo

**ROL:** [nombre del rol]

## 2. Modo BAGO principal

Elegir uno:

- [B] Balanceado
- [A] Adaptativo
- [G] Generativo
- [O] Organizativo

## 3. Objetivo del rol en esta tarea

Descripción breve y precisa.

## 4. Contexto relevante

Resumen de 8 a 15 líneas con:

- lo que quiere el usuario,
- qué ya está decidido,
- qué no debe cambiar,
- qué restricciones aplican,
- qué piezas del repo o sistema afectan.

## 5. Entradas concretas

- archivos,
- rutas,
- requisitos,
- restricciones,
- decisiones congeladas,
- referencias al estado BAGO vigente si aplica.

## 6. Instrucciones detalladas

1. Analiza o ejecuta...
2. Propón...
3. Genera...
4. Evita...
5. Señala pendientes si los hay.

## 7. Formato de salida esperado

- estructura,
- idioma,
- nivel de detalle,
- necesidad o no de código,
- rutas de archivos si aplica,
- necesidad o no de checklist.

## 8. Checklist de calidad

- [ ] Cumple el objetivo.
- [ ] Respeta restricciones.
- [ ] Es utilizable tal cual.
- [ ] No contradice el estado vigente.
- [ ] No introduce cambios laterales innecesarios.
- [ ] Indica pendientes si existen.
```

## Cuándo conviene usarla

- cuando una tarea es compleja y se quiere repartir por roles,
- cuando se hace handoff interno entre análisis y generación,
- cuando una iteración necesita repetir patrones de calidad,
- cuando se quiere convertir una necesidad difusa en trabajo ejecutable.

## Cuándo no hace falta

- en tareas triviales de una sola respuesta,
- cuando la petición ya es extremadamente específica y no gana nada con formalización adicional.

## Regla de sobriedad

La plantilla ayuda si reduce ambigüedad. Si añade ruido, no debe usarse.
