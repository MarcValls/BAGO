# Contrato de ingeniería de BAGO v4

## Alcance

Este contrato cubre los **invariantes de implementación** que ningún otro contrato formaliza:
cómo el sistema escribe estado, protege sus herramientas, controla el consumo de recursos,
aprende de observaciones y garantiza su propia honestidad.

No cubre: modos de sesión ([B][A][G][O]) → `bago_v4_governance_contract.md`,
ni el formato de evidencia → `bago_v4_evidence_contract.md`,
ni la capa de conocimiento → `bago_v4_knowledge_contract.md`.

---

## 1. Portabilidad en tiempo de ejecución

### 1.1 Resolución centralizada de rutas

Ningún módulo hardcodea rutas a `.bago/`, `state/` o archivos internos.
Todos los módulos obtienen las rutas canónicas de un único módulo de resolución.

Orden de resolución de `BAGO_ROOT`:
1. Variable de entorno `BAGO_ROOT`
2. Ascenso desde `__file__` hasta encontrar el directorio `.bago/`
3. CWD como fallback

Orden de resolución de `BAGO_STATE_DIR`:
1. Variable de entorno `BAGO_STATE_DIR`
2. `<BAGO_ROOT>/.bago/state`

### 1.2 UTF-8 Guard

Todo módulo que toca I/O (stdin/stdout/stderr, archivos de estado) debe asegurar
codificación UTF-8 con `errors="replace"` antes de cualquier otra operación.
El sistema nunca aborta por un fallo de codificación; degrada con gracia.

### 1.3 Escrituras de estado atómicas

Toda escritura a archivos de estado debe ser atómica: escribir a fichero temporal
y luego renombrar al destino. La escritura directa que deje archivos parciales en
caso de crash es una violación de este contrato.

### 1.4 Instancia única del loop autónomo

Solo puede existir una instancia activa del loop autónomo en cualquier momento.
Si una segunda instancia intenta arrancar mientras la primera está activa,
debe fallar con un mensaje claro y código de salida no cero.

---

## 2. Calidad e integridad de herramientas

### 2.1 Contrato de cada herramienta

Toda herramienta registrada como `core` o `dangerous` debe cumplir:

| Requisito | Descripción |
|-----------|-------------|
| `--test` | Flag que ejecuta una auto-verificación no destructiva y sale con 0 si pasa |
| Docstring de módulo | Descripción de propósito, uso y opciones |
| Routing en CLI | Ruta explícita en el script de entrada del CLI |
| Registro en suite de tests | Referencia en `integration_tests.py` |

Las herramientas `experimental` pueden violar estas reglas con un warning, no un error.
Las herramientas `legacy` o `internal` están exentas.

### 2.2 Herramientas peligrosas

Cualquier herramienta que pueda modificar estado persistente, ejecutar comandos de sistema
o alterar configuración está marcada como peligrosa. Las herramientas peligrosas:

- Implementan una auto-verificación no destructiva llamable sin efectos secundarios.
- No se ejecutan sin confirmación explícita del operador o flag `--unsafe` en loops autónomos.
- Aparecen en una matriz de comandos peligrosos auditada en cada pre-release.

### 2.3 Detección de huérfanos

El sistema debe poder detectar cuatro categorías de huérfanos y reportarlas:

| Categoría | Definición |
|-----------|------------|
| **Archivo huérfano** | Fichero `.py` en `tools/` no referenciado en el registry |
| **Registro huérfano** | Entrada en registry que apunta a un archivo inexistente |
| **Ruta huérfana** | Comando en el router del CLI sin equivalente en registry |
| **Doc huérfana** | Herramienta sin mención en `docs/` |

Los huérfanos nuevos (no en baseline conocida) bloquean el release.

### 2.4 Sincronización docs–código

La documentación de comandos y capas debe poder regenerarse desde el registry.
La deriva entre docs y registry es detectable automáticamente.
La deriva en comandos `core` bloquea el release.

---

## 3. Gestión de recursos

### 3.1 Freno de tokens

El sistema aplica límites de consumo de tokens por proveedor:

- **Por llamada**: límite duro que impide llamadas anómalas.
- **Diario**: presupuesto operativo normal.
- **Mensual**: presupuesto máximo tolerable.

Un proveedor puede estar `enabled`, `disabled` o en modo `unlimited` (solo para proveedores
locales sin coste por token). Los proveedores con facturación retroactiva sin cap por llamada
deben estar `disabled` por defecto.

Cuando el consumo supera el 80% del límite mensual, el sistema emite una alerta.
Cuando supera el 95%, el sistema rechaza nuevas llamadas hasta que el operador
restablezca explícitamente el contador.

### 3.2 Tokens desperdiciados

El sistema distingue tokens consumidos de tokens desperdiciados. Son desperdiciados:
retries por error recuperable, llamadas que producen respuesta descartada, ruido
de contexto sin contribución al objetivo de la sesión.

La métrica de eficiencia token = `tokens_útiles / tokens_totales` debe ser observable.

---

## 4. Seguridad de ejecución

### 4.1 Sandbox de estado en tests

Ningún test escribe en el directorio de estado real del sistema (`.bago/state/`).
Los tests usan directorios temporales aislados.
Un test que modifique el estado real es un fallo de aislamiento, no un fallo de test.

### 4.2 Separación mutante/no-mutante

Toda acción autónoma debe clasificarse como mutante (modifica estado persistente)
o no-mutante (solo lee y reporta). Las acciones mutantes requieren autorización
explícita del operador antes de ejecutarse en el loop autónomo.

### 4.3 Whitelist de intenciones del inbox

El inbox del loop autónomo solo acepta intenciones preaprobadas. El sistema no
procesa objetivos arbitrarios ni instrucciones en texto libre provenientes del inbox.
Toda intención no reconocida es rechazada con error claro.

---

## 5. Observabilidad y aprendizaje

### 5.1 Bus de eventos

El sistema emite eventos estructurados en un archivo de eventos append-only cuando
ocurren cambios de estado relevantes (salud degradada, proveedor caído, culpa abierta,
sesión cerrada sin [O]).

Los eventos son reproducibles: releer el archivo reproduce la historia del sistema.

### 5.2 Promoción de patrones

Las observaciones del ciclo OBSERVE se acumulan en un JSONL append-only.
Cuando un patrón aparece en múltiples ciclos sucesivos, se promueve automáticamente
a la base de conocimiento del sistema (`knowledge/auto_patterns.md`).

El umbral de promoción es configurable. El valor por defecto debe estar documentado.

### 5.3 Criterio de quiescencia

El loop autónomo no termina por timer sino por quiescencia:
cuando no hay delta accionable durante N ciclos consecutivos, el loop termina limpiamente.

Existe un límite absoluto de ciclos como red de seguridad contra bucles infinitos.
Ambos valores (N y límite absoluto) son configurables con defaults documentados.

### 5.4 Modos harmónicos (perfil operativo del loop)

El loop autónomo selecciona su perfil de operación en SENSE basándose en métricas
del sistema (salud, limpieza de repo, estado de auditoría). Los perfiles posibles son:

| Perfil | Condición de activación |
|--------|------------------------|
| `production_monitor` | Sistema en estado saludable y verificado |
| `clean_install` | Instalación nueva sin historial de estado |
| `crisis_recovery` | Salud por debajo de umbral crítico o auditoría fallida |
| `rd_spiral` | Ciclo de investigación y desarrollo activo |

Las reglas de transición automática están definidas en el código; este contrato
establece que deben existir y ser observables.

> Nota: Los modos harmónicos son el perfil de operación del **loop autónomo**.
> Los modos [B][A][G][O] son el modo de la **sesión de trabajo humano**.
> Son ejes ortogonales, no alternativas.

---

## 6. Control de release

### 6.1 Verdad de versión

Antes de marcar un release, todas las fuentes de versión del repositorio deben
estar sincronizadas. Ninguna fuente puede ir por delante o por detrás de las demás.

Las fuentes de versión del repositorio son: `pyproject.toml`, módulo `__init__.py`,
archivo de pack, estado global y tag de Git. Si hay más fuentes, deben listarse
en el artefacto `VERSION_CONTRACT.json`.

### 6.2 Gate de pre-commit

La deriva de contratos se verifica antes de cada commit. Si el sistema detecta deriva
bloqueante, el commit se aborta con un mensaje que indica el artefacto afectado
y el comando para diagnosticar.

El gate puede omitirse con variable de entorno explícita (nunca silenciosamente).

### 6.3 Deuda de tests legacy

Los tests con error de importación y los tests marcados `xfail` se distinguen
explícitamente. Los tests con error de importación deben repararse o eliminarse;
`xfail` es deuda técnica aceptada pero rastreada.

La deuda no crece entre releases sin justificación explícita.

### 6.4 Fallos en cascada

Cuando un agente de supervisión falla, los fallos de agentes dependientes causados
por ese fallo se marcan como cascada, no como fallos independientes.

El reporte de supervisión distingue: causa raíz, efectos en cascada, y fallos genuinamente
independientes. Esta distinción es necesaria para reparar el origen sin sobre-reaccionar
a los síntomas.

---

## 7. Sinceridad de la documentación

La documentación del sistema se escanea en busca de anti-patrones que enmascaran
la verdad operativa. Los anti-patrones bloqueantes son:

| Anti-patrón | Definición |
|-------------|-----------|
| **Flattery** | Adjetivos decorativos sin dato que los sostenga |
| **Absolutos sin evidencia** | "100%", "siempre", "nunca falla", "garantizado" sin referencia |
| **Success-washing** | "✅ completado", "listo para producción" sin artefacto verificable |
| **Futuro como hecho** | Promesa en futuro dentro de contexto marcado como completado |
| **Evidencia ausente** | Declaración fuerte (PASSED, STABLE, PRODUCTION-READY) sin link a test/artifact |
| **Checklist vacía** | Items marcados pero sin detalle ejecutable |

Las violaciones de tipo `ERROR` bloquean el release.
Las de tipo `WARN` se reportan pero no bloquean.

---

## Validación de este contrato

```
[FAIL] si un módulo hardcodea una ruta absoluta a .bago/state/
[FAIL] si una escritura de estado no es atómica (escribe directo al destino)
[FAIL] si un test escribe en el .bago/state/ real
[FAIL] si existe un archivo .py en tools/ no referenciado en el registry (huérfano nuevo)
[FAIL] si un provider de facturación retroactiva está enabled por defecto sin cap por llamada
[FAIL] si la sincerity scan detecta ERROR en docs/
[FAIL] si existen dos instancias del loop autónomo con el mismo BAGO_ROOT
[WARN] si hay herramienta core sin --test implementado
[WARN] si hay deriva entre docs/COMMANDS.md y el registry
```

```powershell
python bago_core\launcher.py validate
python bago_core\claim_ledger.py --test
python test_e2e.py
python test_governance.py   # incluye checks de este contrato
```
