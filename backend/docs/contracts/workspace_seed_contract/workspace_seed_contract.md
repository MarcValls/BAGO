# Contrato workspace seed v1

## Proposito

`workspace seed` prepara un workspace para que BAGO use `.gabo` como fuente dinamica de contexto.
La semilla es una capacidad del framework, no un archivo copiado dentro de cada workspace.
Si hace falta una huella de origen, se guarda en metadatos de `.gabo`, no en un `seed.py` local.
La resolucion de rutas, alias y raices canónicas vive en `docs/contracts/resolver_contract.json`.

## Autoridad

- `workspace_root` es la raiz del proyecto una vez resuelta por el resolver.
- `.gabo` es el estado portable del workspace.
- `.bago` es el framework BAGO y no debe convertirse en estado por workspace.
- La UI y el modelo consumen el resultado de `workspace seed`, pero no deciden la semilla.

## Entradas

- `workspace_root`: directorio candidato a sembrar.
- `seed_depth`: profundidad maxima de recorrido.
- `seed_profile`: `fast`, `normal` o `deep`.
- `ref_root`: referencia opcional para diff.
- `force`: permite regenerar artefactos con autorizacion explicita.
- `budget`: limite de lectura, simbolos y dependencia.

## Flujo canonico

1. Resolver `workspace_root` usando el contrato de resolver.
2. Preguntar si se quiere trabajar en el directorio del terminal o en otro directorio.
3. Validar autoridades de ruta y salir si el root no pertenece al alcance permitido.
4. Detectar si `.gabo` existe.
5. Si `.gabo` no existe, ofrecer sembrarla.
6. Si el usuario acepta, crear la estructura base de `.gabo`.
7. Recorrer el arbol con profundidad 9 (`depth 9`) en modo `deep`, o con la profundidad del perfil en otros modos.
8. Registrar metadatos de cada archivo: ruta, tipo, extension, tamano, fecha, hash y exclusiones.
9. Leer contenido solo de archivos de texto y solo dentro del presupuesto.
10. Clasificar cada archivo por responsabilidad respecto al proyecto real.
11. Construir el mapa del repositorio.
12. Indexar simbolos.
13. Construir el grafo de dependencias.
14. Construir el working set inicial.
15. Escribir snapshot, manifests y receipt.

## Reglas de lectura

- Primero metadatos, despues contenido.
- No leer el repositorio completo sin presupuesto ni justificacion.
- Excluir por defecto: `.git`, `.bago`, `.gabo`, `node_modules`, `dist`, `build`, `coverage`, `.venv`, `__pycache__`.
- Archivos binarios se registran por metadatos salvo necesidad explicita.
- No se permite salir del `workspace_root` mediante enlaces, rutas relativas o includes.

## Clasificacion de responsabilidad

Cada archivo debe etiquetarse, como minimo, como:

- framework
- proyecto
- workspace
- backend
- ui
- tests
- docs
- config
- scripts
- generated
- unknown

## Salidas obligatorias

| Artefacto | Proposito |
|---|---|
| `.gabo/workspace.json` | identidad y politica del workspace |
| `.gabo/live.json` | huella y estado operativo |
| `.gabo/tree.json` | arbol relativo del workspace |
| `.gabo/index.md` | resumen legible de la semilla |
| `.gabo/manifests/*.json` | manifest por area |
| `.gabo/context/repository_map.json` | mapa operativo del proyecto |
| `.gabo/context/repository_map.md` | version legible del mapa |
| `.gabo/context/symbols.json` | indice de simbolos |
| `.gabo/context/dependency_graph.json` | grafo de relaciones |
| `.gabo/context/working_set.json` | contexto de trabajo inicial |
| `.gabo/context/events.jsonl` | trazabilidad de la semilla |
| `.gabo/diffs/vs_<ref>.json` | diff opcional contra referencia |
| `.gabo/seed.meta.json` | trazabilidad de la ejecucion |

## Limitaciones y seguridad

- El seed no ejecuta comandos arbitrarios del sistema.
- El seed no publica resultados parciales si falla una fase critica.
- El seed conserva el ultimo snapshot valido si una recarga falla.
- Cada operacion debe dejar evidencia con `execution_id`.
- El comportamiento debe ser determinista para la misma entrada y el mismo presupuesto.

## Receipt minimo

Cada ejecucion debe registrar:

- `execution_id`
- `workspace_root`
- `seed_depth`
- `seed_profile`
- `files_scanned`
- `files_indexed`
- `symbols_indexed`
- `dependencies_indexed`
- `working_set_size`
- `warnings`
- `errors`
- `snapshot_id`
- `seed_tool_version`

## Criterios de aceptacion

`workspace seed` solo se considera correcto cuando:

- `.gabo` queda creada o actualizada de forma coherente.
- La semilla no sale del workspace autorizado.
- La clasificacion por responsabilidad separa proyecto, framework y workspace.
- El mapa del repositorio, el indice de simbolos y el grafo de dependencias existen.
- El working set inicial explica por que se incluyo cada fragmento.
- El resultado es repetible y auditado.
