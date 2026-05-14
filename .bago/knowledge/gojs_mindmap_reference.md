# GoJS Mind Map — Referencia para BAGO

## Qué es
GoJS es una librería JavaScript comercial para diagramas interactivos.
El sample `mindMap.html` muestra un editor de mapas mentales completo:
- Drag & drop de nodos y subtrees
- Layout automático de árboles (TreeLayout)
- Edición inline de texto
- Collapse/expand de ramas
- Copy/paste/delete de subtrees
- Zoom y pan

## URL
https://github.com/NorthwoodsSoftware/GoJS/blob/master/samples/mindMap.html

## Por qué es útil para BAGO
1. **Reemplaza el mind map estático** (`bago_mindmap.html`) por uno interactivo
2. **Visualización del router dinámico**: el árbol Entrada→Router→Agente→Modelo encaja perfecto en tree layout
3. **Edición de workflows**: un profesor podría reorganizar el pipeline musical arrastrando nodos
4. **Collapsible knowledge**: las 37 entradas de `.bago/knowledge/` podrían visualizarse como mind map colapsable

## Alternativas libres
| Librería | Licencia | Pros | Contras |
|---|---|---|---|
| GoJS | Comercial ($3-9k) | Completa, soporte | Pago obligatorio para producción |
| D3.js | BSD | Gratis, flexible | Más código manual |
| Cytoscape.js | MIT | Gratis, layouts | Menos features de edición |
| React Flow | MIT | Gratis, React | Requiere React |

## Decision para BAGO
Para el mind map de BAGO usamos HTML/CSS/JS puro (sin dependencias).
Si en el futuro se necesita edición interactiva de workflows,
GoJS es la referencia a seguir, pero se implementaría con
D3.js o Cytoscape.js para mantener BAGO 100% open source.

## Código clave del sample (para referencia)
- `go.TreeLayout` con `angle: 0` para layout horizontal
- `go.Node` con `SpotPanel` para estructura nodo + icono + texto
- `go.Link` con `Bezier` para curvas entre nodos
- `Diagram.commandHandler` para copy/paste/delete
- `Layout.isTreeLayout = true` para animaciones

## Fecha
2026-05-14
