# Matriz minima de pruebas para `workspace seed`

## Objetivo

Estas pruebas aseguran que `workspace seed` no sea solo una idea, sino una capacidad
verificable. El gate minimo debe cubrir:

- deteccion de directorio al arrancar,
- siembra de `.gabo`,
- caso `no .gabo` al arrancar,
- escaneo profundo,
- escaneo profundo `depth 9`,
- clasificacion de responsabilidad,
- lectura segura de contenido,
- salida determinista,
- trazabilidad y rollback.

## Casos minimos

| Caso | Preparacion | Accion | Esperado |
|---|---|---|---|
| `startup_current_dir` | abrir BAGO en un directorio valido | elegir trabajar en el directorio actual | BAGO entra en contexto con esa raiz |
| `startup_other_dir` | abrir BAGO en un directorio que no es el objetivo | elegir otro directorio | BAGO usa la nueva raiz y no hereda la anterior |
| `seed_prompt_when_missing` | proyecto sin `.gabo` | pedir contexto inicial | BAGO ofrece sembrar `.gabo` |
| `seed_create_gabo` | proyecto sin `.gabo` | aceptar la siembra | se crea `.gabo` con metadatos, manifests y snapshot |
| `deep_scan_depth_9` | proyecto con arbol amplio | ejecutar `workspace seed` en modo `deep` | el recorrido llega a profundidad 9 |
| `metadata_first` | archivo grande y archivo pequeno | ejecutar la semilla | primero se guardan metadatos; contenido solo si aplica |
| `text_sampling_limits` | archivo binario y archivo de texto | ejecutar la semilla | binarios no se leen como texto; texto si entra en presupuesto |
| `responsibility_split` | repo con backend, ui, tests y docs | ejecutar la semilla | cada archivo queda clasificado por responsabilidad |
| `repository_map_written` | workspace sembrado | ejecutar la semilla | existen `repository_map.json` y `repository_map.md` |
| `symbol_index_written` | codigo con funciones y clases | ejecutar la semilla | el indice contiene simbolos reales y rutas |
| `dependency_graph_written` | modulo con imports y pruebas | ejecutar la semilla | el grafo registra relaciones relevantes |
| `working_set_reasoned` | archivos candidatos + pruebas | ejecutar la semilla | el working set explica por que entra cada fragmento |
| `deterministic_repeat` | misma raiz y mismo presupuesto | repetir la semilla | mismo snapshot o snapshot equivalente |
| `workspace_escape_blocked` | ruta con symlink o include malicioso | ejecutar la semilla | la ruta fuera de alcance se rechaza |
| `incremental_refresh` | modificar un solo archivo | resembrar o refrescar | solo cambia la parte afectada del indice |
| `receipt_present` | semilla completada | revisar salida | existe receipt con `execution_id` y recuentos |

## Niveles de prueba

1. Prueba documental.
2. Prueba de smoke de seed.
3. Prueba de profundidad y presupuesto.
4. Prueba de seguridad de rutas.
5. Prueba de incrementalidad.
6. Prueba de determinismo.
7. Prueba de rollback al ultimo snapshot valido.

## Gate minimo recomendado

```powershell
python -m pytest tests\test_workspace_seed_contract.py -q
```

## Notas de implementacion

- La matriz de pruebas valida el contrato, no una copia local de `seed.py`.
- `workspace seed` debe vivir en el framework y operar sobre el workspace activo.
- El resultado del seed debe poder consumirse por BAGO Terminal y por la UI.
