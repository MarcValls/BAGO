# Contrato de gobernanza operativa de BAGO v4

## Por qué existe este contrato

Los contratos actuales de v4 cubren bien la **infraestructura de sesión**: cómo se guardan los datos,
cómo se genera evidencia, cómo se persiste el conocimiento.

Lo que no cubren es cómo **BAGO decide cómo trabajar**: en qué modo opera, quién controla
qué, cuándo necesita validación humana, cómo registra que algo falló y por qué no vuelve
a fallar. Esos principios existían en BAGO v3.x y son más relevantes en v4, donde BAGO
tiene mucha más autonomía.

Este contrato formaliza esa capa.

---

## 1. Modos operativos BAGO [B][A][G][O]

Toda sesión productiva opera bajo un modo predominante. El modo debe declararse al inicio
y puede cambiar, pero el cambio debe ser explícito.

| Modo | Acción principal | Cuándo activar |
|------|-----------------|----------------|
| **[B] Balanceado** | Clarificar objetivo, alcance, restricciones, riesgos y criterio de éxito | Al arrancar sin contexto previo |
| **[A] Adaptativo** | Elegir estrategia según estado real del repositorio | Al retomar un sprint o cambiar de plan |
| **[G] Generativo** | Producir artefactos útiles: código, tests, docs, scripts | Cuando el objetivo y el enfoque ya están claros |
| **[O] Organizativo** | Ordenar, empaquetar, actualizar estado y dejar continuidad | Al cerrar una sesión o sprint |

### Regla de activación

- No se activa modo [G] si el objetivo no está clarificado ([B]) o la estrategia no está definida ([A]).
- La sesión no puede ser solo [G] de principio a fin sin pasar por [B].
- "No generar antes de entender" es una invariante del sistema.

### Regla de cierre

Toda sesión debe pasar por [O] antes de cerrar: actualizar estado, registrar lo producido,
dejar el siguiente paso explícito. Cerrar sin [O] es una sesión incompleta.

---

## 2. Preflight de sesión productiva

Antes de empezar trabajo técnico relevante, el sistema debe poder responder:

- ¿Cuál es el objetivo concreto de esta sesión? (verbo + objeto + para qué)
- ¿Qué artefactos se van a tocar o producir?
- ¿Qué tipo de tarea es? (`implementation`, `audit`, `exploration`, `fix`, `refactor`)

Si no puede responderlas, la sesión debe entrar en modo [B] antes de proceder.

### Aplicación en v4

En el REPL, el comando `/session` debe poder mostrar en todo momento:

```
Objetivo:   [declarado o "sin declarar"]
Modo:       [B/A/G/O]
Tarea:      [tipo de tarea]
Artefactos: [lista o "ninguno declarado"]
```

---

## 3. Protocolo de cambio

Todo cambio estructural debe dejar rastro con:

| Campo | Obligatorio | Descripción |
|-------|-------------|-------------|
| `change_id` | Sí | Identificador único |
| `title` | Sí | Describe la mutación real (no la intención) |
| `type` | Sí | `feature`, `fix`, `security`, `refactor`, `breaking` |
| `scope` | Sí | Archivos o módulos afectados |
| `motivation` | Sí | Por qué se hizo |
| `risk` | Sí | Qué puede romperse |
| `rollback` | Recomendado | Cómo revertir |
| `human_approved` | Sí (si sensible) | Validación explícita para cambios sensibles |

### Cambios que requieren validación humana explícita

- Arquitectura del sistema
- Contratos públicos
- Seguridad y permisos
- Cambios destructivos o migraciones
- Contratos internos de `.bago/`

### Ubicación

Los cambios estructurales se registran en `.bago/state/changes/`.

---

## 4. Sistema de culpa (responsabilidad de fallo)

Cuando BAGO o el sistema comete un error verificable, debe registrarlo y aprender de él.

### Estructura de una entrada de culpa

```json
{
  "culpa_id": "culpa_<timestamp>_<hash>",
  "command": "comando que falló",
  "error": "descripción del error",
  "context": "estado relevante en el momento del fallo",
  "status": "open | resolved | stabilized",
  "resolution": "qué se cambió para evitar la recurrencia",
  "consecutive_ok": 0,
  "recorded_at": "ISO 8601",
  "resolved_at": null
}
```

### Reglas

1. Antes de ejecutar un comando que ha fallado antes, el sistema debe advertir que existe
   una culpa abierta relacionada.
2. Una culpa se cierra cuando el mismo comando tiene 3 éxitos consecutivos sin error.
3. Una culpa nunca se elimina; se marca `resolved` o `stabilized`.
4. El sistema no puede declarar "ALL PASS" si hay culpas abiertas relacionadas con lo
   que se está validando.

### Ubicación

`.bago/state/culpas/culpas.jsonl`

---

## 5. Principios de gobernanza de sesión

Estos principios son invariantes operativas, no sugerencias:

| Principio | Formulación |
|-----------|-------------|
| Claridad sobre estética | Una respuesta técnicamente precisa supera a una visualmente elegante |
| Trazabilidad sobre velocidad ciega | Si no hay rastro, no hubo progreso |
| Reparar antes que castigar | Cuando algo falla, primero entender y corregir, luego evaluar causa |
| Supervisión solo con evidencia | No emitir juicio de estado sin artefacto verificable que lo sostenga |
| No confundir documentación con progreso | Escribir sobre lo que se va a hacer no es hacerlo |
| No generar antes de entender | Producir artefactos sin objetivo claro es deuda técnica inmediata |
| No rediseñar por impulso | Un rediseño solo es válido si el problema que resuelve está diagnosticado |
| No cerrar sin continuidad | Toda sesión cerrada debe dejar el siguiente paso explícito |

---

## 6. Supervisión evolutiva (GUIA_VERTICE)

v4 necesita un mecanismo de meta-control que detecte deriva silenciosa sin interrumpir
el flujo normal de trabajo.

### Condiciones de activación

La capa de supervisión se activa cuando detecta alguna de estas señales:

- Estado y código divergen (lo que dicen los contratos ya no refleja el código)
- Misma clase de error recurrente en culpas (patrón de fallo repetido)
- Evidencia simulada presentada como evidencia real
- Expansión de roles o responsabilidades sin justificación
- Contratos que ya no pueden validarse con los comandos declarados
- Un "ALL PASS" sin asserts sustantivos

### Qué produce

Cuando se activa, la supervisión genera un reporte en `.bago/state/supervision/drift_report.json`
con:
- señal detectada
- artefactos que la evidencian
- recomendación concreta
- severidad: `info | warn | critical`

La supervisión recomienda pero no ejecuta. La decisión es humana.

---

## 7. SAC — Superficie Activa por Condición

Cuando el estado del entorno cumple naturalmente las precondiciones de una herramienta
o acción, BAGO debe sugerirla con el comando exacto, no esperar a que el usuario recuerde
que existe.

### Ejemplos de condiciones → sugerencias

| Condición detectada | Sugerencia |
|---------------------|-----------|
| Hay culpas abiertas al arrancar | `→ SAC: hay culpas abiertas. Considera: /culpa list` |
| Sesión sin objetivo declarado después de N mensajes | `→ SAC: sesión sin objetivo. Considera: /session objetivo "<tu objetivo>"` |
| `validate` falla pero hay culpas relacionadas | `→ SAC: el fallo está relacionado con culpa conocida <id>` |
| Modo [G] activado sin pasar por [B] | `→ SAC: generando sin objetivo declarado — verifica con /status` |

### Límites

- La sugerencia no bloquea ni interrumpe. Es informativa.
- No se repite en la misma sesión para la misma condición.
- Nunca en modo daemon o no interactivo.

---

## 8. Invalidez canónica

Una propuesta de cambio o una respuesta del sistema es canónicamente inválida si:

- Declara "validado" sin nombre del gate, comando ejecutado, stdout y timestamp.
- Declara "hecho" sin artefacto producido verificable.
- Generaliza de un test parcial a una conclusión global.
- Presenta evidencia simulada como evidencia real.
- Abre una segunda fuente de verdad para datos que ya tienen SSOT.
- Introduce un contrato que no puede validarse con un comando declarado.
- Registra un "ALL PASS" sin asserts sustantivos.

---

## 9. Regla de precedencia de fuentes de verdad

| Ámbito | Fuente |
|--------|--------|
| Configuración operativa | `.bago/config.json` |
| Normas del sistema | `docs/contracts/` |
| Estado vivo de sesión | `.bago/state/sessions/<id>/` |
| Culpas abiertas | `.bago/state/culpas/culpas.jsonl` |
| Cambios estructurales | `.bago/state/changes/` |
| Supervisión / deriva | `.bago/state/supervision/` |
| Evidencias | `.bago/state/evidence/` |

En caso de conflicto entre lo que dice un contrato y lo que hay en el código,
el código manda — pero la divergencia debe registrarse como cambio o culpa.

---

## Validación de este contrato

Este contrato no puede validarse solo con `test_e2e.py`. Requiere tests negativos:

```
[FAIL] si auto_allow_tools es true en config.json
[FAIL] si execute_command usa shell=True
[FAIL] si API arranca en 0.0.0.0 sin token
[FAIL] si /load no cambia el ContextStore
[FAIL] si un "ALL PASS" aparece sin asserts sustantivos
[FAIL] si hay culpas abiertas y validate las ignora
[FAIL] si una evidencia simulated se presenta sin etiqueta SIMULATED
```

```powershell
python test_e2e.py
python test_governance.py  # pendiente de implementar
```
