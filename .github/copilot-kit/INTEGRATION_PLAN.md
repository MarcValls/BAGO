# BAGO Copilot CLI: pack e integracion

## Resultado y alcance

El ZIP es un snapshot de fuentes seleccionadas del checkout, no un instalador,
una nueva autoridad ni una certificacion de funcionamiento en Copilot CLI.
Mantiene rutas originales dentro de cada seccion `source` para conservar
procedencia y facilitar diffs. No descomprimir sobre un repositorio activo.
No copiar todo el pack como configuracion confiable.

Leer `INVENTORY.md` para el listado por archivo y `INVENTORY.json` para
clasificacion por significado. `SOURCE_MANIFEST.json` contiene hashes de cada
pieza. La existencia de codigo prueba existencia, no comportamiento correcto.
Las descripciones extraidas del codigo son pistas, no contratos verificados.

## Clasificacion por significado

| Significado | Piezas | Uso |
|---|---|---|
| Autoridad y limites | Instrucciones, contratos, protocolos de skills | Resolver permisos y conflictos antes de ejecutar. |
| Observacion y conocimiento | Explorer, mapper, inventario, lectura, contexto Git | Descubrir fuentes y producir evidencia trazable. |
| Evaluacion y diagnostico | Auditores, scanners, sincerity, doctor | Evaluar una pregunta acotada sin certificar por nombre. |
| Coordinacion y preparacion | Roles, factories, router, preflight, grafo de workflows | Elegir responsables y prerrequisitos; no concede permisos. |
| Intervencion | Workers, edicion, scaffolding, auto-heal, runners | Requiere alcance aprobado y revision de efectos. |
| Verificacion y cierre | Final-verifier, prompts 22, plantillas y helpers | Evidencia fresca y separacion de implementador/verificador. |
| Continuidad | Helpers BAGO y Copilot | Inicializar estado nuevo del destino; nunca importar estado vivo. |
| Integracion y transporte | MCP, hooks, SDK extension, plugin | Revisar contratos, dependencias, permisos y discovery. |
| Produccion de artefactos | Templates, workpacks, empaquetador | Generar salidas con origen y limites explicitos. |

## Fases con dependencias y criterios de salida

| Fase | Depende de | Acciones | Criterio para avanzar |
|---|---|---|---|
| P0: comprobar snapshot | Ninguna | Validar hashes, identidad del checkout, exclusiones y delta local. Descomprimir en carpeta nueva, fuera de directorios de discovery. | Todas las entradas verificadas; diferencias y dependencias externas identificadas. |
| P1: instrucciones y roles | P0 | Comparar instrucciones con las del destino. Integrar solo agentes/skills elegidos en `.github`. Conservar referencias completas. Adaptar rutas BAGO especificas. | `/instructions`, `/agent`, `/skills` y `/env` muestran lo esperado en una sesion del destino; tarea read-only de muestra. |
| P2: prompts y playbooks | P1 | Seleccionar inventario, preflight y verificacion. Reconciliar prompts/workflows duplicados; usar prompts como texto si discovery no esta soportado. | Prueba de punta a punta: pregunta -> fuente -> hallazgo -> evidencia, sin escrituras inesperadas. |
| P3: herramientas read-only | P2 | Resolver manifiesto vs fuentes vs registro runtime. Revisar cada efecto. Crear wrappers acotados con raiz fijada, entradas/salidas tipadas y errores explicitos. | Casos nominales y de rechazo: traversal, raiz ajena, symlinks, errores, timeout y ausencia de efectos no autorizados. |
| P4: MCP read-only | P3 | Sustituir rutas de otro checkout en config; identificar imports/dependencias externas. Configurar servidor desde `/mcp` solo despues de revisar. | Handshake, listado y llamadas reales; rechazo de operaciones mutantes; evidencia de raiz efectiva. |
| P5: hooks y extensiones | P3 | Confirmar lifecycle real. Revisar hook y plugin por separado. No instalar `bash-runner` como esta: reemplazar shell arbitrario por operaciones permitidas. | Pruebas de eventos, consentimiento, cancelacion, permisos, salida y logs sin datos sensibles. |
| P6: escritura autorizada | P4 y P5 si se usan | Adoptar solo cambios delimitados; no importar permisos ni sandbox de Codex. Remote/admin/remediation requieren autorizacion especifica. | Rechazo de acciones fuera de alcance; efectos autorizados trazados con evidencia. |
| P7: cierre | Fases adoptadas | Verificacion independiente del candidato final; registrar que se integro, que se excluyo y como retirar solo lo integrado. | Criterios explicitos satisfechos; limitaciones visibles; nada se declara VALIDATED por empaquetar. |

Los comandos interactivos anteriores proceden del help local de Copilot CLI.
La disponibilidad concreta depende de version, configuracion y confianza del
destino. Este pack no ejecuta discovery ni prueba servidores MCP.

## Posibles entes (propuestas, no capacidades instaladas)

| Candidato | Base existente | Adaptacion / limite |
|---|---|---|
| bago-inventory | `bago_inventory.py`, `read_repository_map.py`, prompt 01 | Inventario estructurado de una raiz autorizada. |
| bago-search | `search_text.py`, `search_symbol.py`, `find_references.py`, `find_dependents.py` | Fuentes incluidas; comparar con la busqueda nativa antes de crear un wrapper duplicado. |
| bago-evidence-snapshot | `git_context.py`, `read_git_diff.py`, plantilla evidencia | Snapshot con identidad y hashes, sin promover estado. |
| bago-preflight | `preflight_engine.py`, prompt 00 | Informe de condiciones de entrada, no permiso de ejecucion. |
| bago-audit-pack | `secret_scan.py`, `dep_audit.py`, `code_metrics.py`, `dead_code.py` | Revisar efectos reales antes de llamar read-only a cada scanner. |
| bago-role-plan | `agent_router.py`, manifest de roles | Producir plan; no activar ejecutores automaticamente. |
| bago-workflow-select | `WORKFLOW_GRAPH.json`, indice workflows | Selector con dependencias y limites, no auto-run. |
| bago-truth-check | `sincerity_detector.py`, prompt 12 | Contrastar afirmaciones con evidencia del candidato. |
| bago-tool-catalog | `_registry_*`, `tool_registry.py`, manifiesto | Distinguir presente, declarado, registrado y habilitado. |
| bago-mcp-readonly | Servidor MCP y toolbox catalog | Binding parametrizado y allowlist verificada. |
| bago-hook-adapter | Hook JSON y handler Python | Adaptar eventos despues de confirmar contrato CLI. |
| bash-runner-safe | `extension.mjs` | Sustituir ejecucion arbitraria; no habilitar original. |
| bago-final-verifier gate | Agente existente y prompt 22 | Adaptacion operativa del rol ya existente, no un ente nuevo. |

## Exclusiones y dependencias

Se excluyen credenciales, `.env`, bases de datos, logs, bytecode, caches, sesiones,
estado/contexto/memoria vivos, backups y payloads historicos. El empaquetador usa
listas de directorios y extensiones permitidos y rechaza enlaces de filesystem.
Los helpers de continuidad se entregan sin estado y no deben ejecutarse en el
pack como si fuese el repo BAGO.

Las fuentes framework de soporte se incluyen para inspeccionar dependencias,
pero no todo el backend, frontend, herramientas del sistema o dependencias de
terceros. Imports externos siguen siendo requisitos del destino. El MCP config
original queda como referencia en la seccion de revision, no como configuracion
lista para usar. El plugin GitHub administra recursos externos y queda inactivo.

La comprobacion de patrones de secretos es una barrera limitada, no una garantia
de ausencia de datos sensibles. Antes de distribucion externa, revisar las fuentes
y aplicar el proceso de release del proyecto. Este trabajo entrega un ZIP local.
Dos literales sinteticos `FAKE` de los generadores canary se exceptuan solo en
sus dos archivos fuente; no se exceptuan valores similares en otros archivos.
Todo `backend/.bago/node_control/` queda fuera: en este checkout es un
directorio ignorado de estado local, no una fuente versionada, e incluye
evidencia y registros de instalaciones, conectores, piezas y compatibilidad.
El runtime local de backend queda excluido por completo; no se empaquetan
handoffs ni informes historicos.
Solo `.bago/bin` se considera raiz de helpers; el arbol ignorado
`.gabo/copilot/` de continuidad queda excluido por completo.
Se conserva la licencia MIT del repositorio en `06-documentation/LICENSE`.

## Correcciones del rebarrido anterior

El informe del explorador era orientativo y no una certificacion. La generacion
del pack enumera realmente cada fuente: incluye los cuatro modulos de busqueda
omitidos en su listado textual, distingue archivos de roles de roles efectivos
y contrasta tambien los hashes del manifiesto, no solo nombres y conteos.
En este snapshot hay 32 hashes distintos entre las 33 entradas declaradas;
no interpretar el manifiesto historico como evidencia vigente.
Las propuestas son 12 adaptaciones candidatas y un gate del verificador ya
existente, no 13 implementaciones nuevas.

## Reproduccion y retirada

Desde la raiz BAGO, con Python disponible:

```powershell
python .github\copilot-kit\build_pack.py --output C:\ruta\nueva\BAGO-copilot-kit.zip
```

El empaquetador no sobrescribe un ZIP existente. Registra el HEAD y hashes de
las fuentes, comprueba integridad del ZIP y genera un `.sha256` lateral.
No modifica los originales ni instala dependencias.

Para integrar, guardar un diff y la lista exacta de archivos adoptados en el
destino. Para retirar, revisar esos diffs y revertir solo cambios propios y
autorizados; nunca borrar `.github`, `.bago` o `.gabo` completos.
