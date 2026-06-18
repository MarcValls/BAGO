# Manager Visual Grammar

## Objetivo
Unificar `Control`, `Pipelines`, `Ruta`, `Patch Bay`, `Releases`, `Jobs` y `Sessions` bajo un solo lenguaje visual.

## Capas
- `Shell`: marco global, navegación y acciones de alto nivel.
- `Section`: bloque funcional principal.
- `Rail`: biblioteca, lista, registry o colección.
- `Canvas`: espacio de edición nodular.
- `Inspector`: detalle contextual del elemento activo.
- `Contract`: salida, validación o resumen operativo.
- `Registry`: compatibilidad, piezas, conectores y estado.

## Reglas
- Un bloque principal por vista.
- Una acción primaria por bloque.
- Un solo nombre por concepto.
- Un solo camino de edición por objeto.
- Lo visible debe responder en segundos: dónde estoy, qué puedo editar, qué está guardado, qué falta.

## Vocabulario canónico
- `Pipeline`: flujo guardable compuesto por etapas.
- `Nodo`: unidad mínima editable.
- `Etapa`: agrupación de nodos.
- `Conector`: relación entre nodos o piezas.
- `Ruta`: resumen legible del recorrido.
- `Patch Bay`: vista de wiring y registry.
- `Inspector`: detalle del elemento activo.
- `Contrato de salida`: resumen ejecutable o verificable.

## Antipatrones
- Dos pantallas editando el mismo objeto con nombres distintos.
- Vistas vacías sin estado, sin llamada a acción y sin contexto.
- Una acción visible que no sea alcanzable por el flujo real.
- Duplicar `Ruta`, `Pipeline` y `Chain` como sinónimos sin contrato claro.

## Aplicación práctica
- `Pipelines` es la pantalla principal para crear, abrir, duplicar y guardar.
- `Ruta` es una vista resumen, no una segunda edición del pipeline.
- `Patch Bay` es la vista de registry y wiring, no una biblioteca paralela.
- `Control` solo concentra salud, instalación, providers y accesos rápidos.

