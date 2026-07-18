# PROTOCOLO DE CAMBIO · BAGO AMTEC línea canónica previa CORREGIDO

## Objeto

Regular toda modificación aceptada del sistema o de su trazabilidad. En esta edición corregida se amplía el protocolo para incluir la preservación del historial legado y la regeneración consistente de evidencias del paquete.

## Ámbitos a los que aplica

- manifiesto,
- canon,
- taxonomía,
- contratos,
- workflows,
- roles,
- estado estructurado,
- migraciones,
- herramientas de validación,
- árbol y checksums del pack.

## Flujo obligatorio

1. propuesta,
2. análisis de impacto,
3. revisión canónica,
4. decisión,
5. aplicación,
6. validación,
7. registro.

## Reglas reforzadas

### Manifiesto

No se aceptan cambios que rompan resolubilidad de rutas.

### Historia

No se aceptan cambios que oculten o sustituyan historia real sin preservarla.

### Evidencia de paquete

Cuando un cambio afecta al propio contenido del pack, `TREE.txt` y `CHECKSUMS.sha256` deben regenerarse al final, nunca en mitad del proceso.

## Estados permitidos

- `proposed`
- `approved`
- `approved_with_conditions`
- `applied`
- `validated`
- `rejected`
- `deferred`

## Política de migración

Todo cambio de versión con continuidad histórica debe incluir:

- guía de migración,
- mapa de equivalencias,
- preservación del original,
- traducción de elementos importantes a estructuras nuevas,
- criterio de cierre.
