# Framework Traps — Auditoría BAGO

> **Sesión:** Apr 23, 2026
> **Trigger:** guardian_health=0%, inventarios incompatibles (95 vs 135 vs 55/55 tools)
> **Resultado:** 13 trampas identificadas
> **Estado Mayo 2026:** CHG-002 pendiente — 33 tools sin --test real

---

## Resumen ejecutivo

El framework BAGO, al optimizar para demostración de progreso, desarrolló trampas semánticas
donde los mecanismos de validación reportan ✅ cuando en realidad no ejercitan nada.
Esta auditoría identifica las 13 trampas ordenadas por severidad e impacto.

```
Total trampas: 13
  Alta severidad:       5 (#1, #2, #3, #4, #5)
  Media severidad:      6 (#6, #7, #8, #9, #10, #11)
  Baja-Media severidad: 2 (#12, #13)
```

---

## Tabla de trampas

| # | Trampa | Severidad | CHG |
|---|--------|-----------|-----|
| 1 | `--test` estándar = `print("OK"); sys.exit(0)` — no ejercita lógica real | 🔴 Alta | CHG-002 |
| 2 | Tests autogenerados pasan si `rc==0` y stdout contiene "pasaron" | 🔴 Alta | CHG-002 |
| 3 | `tool_guardian.py` detecta integración por substring grep | 🔴 Alta | CHG-003 |
| 4 | CI convierte excepciones en ✅ | 🔴 Alta | CHG-002 |
| 5 | `contracts.py`: condición falsa = ACTIVE no VIOLATED hasta expiración | 🔴 Alta | CHG-004 |
| 6 | Métricas por cantidad (count >= N) incentivan inflar | 🟡 Media | CHG-005 |
| 7 | Comandos duplicados en CLI inflan el contador | 🟡 Media | CHG-005 |
| 8 | Inventarios incompatibles: 95 vs 135 vs 55/55 tools | 🟡 Media | CHG-006 |
| 9 | `--test` valida solo "carga módulo + existe state/" | 🟡 Media | CHG-002 |
| 10 | Guardian valida "tiene --test" buscando string "--test" | 🟡 Media | CHG-003 |
| 11 | Hook pre-commit silencioso ante parsing error | 🟡 Media | CHG-007 |
| 12 | Tests autogenerados no se regeneran al cambiar tool | 🟠 Baja-Media | CHG-002 |
| 13 | Narrativa "ALL PASS / 100/100" sin provenance | 🟠 Baja-Media | CHG-008 |

---

## Trampas de Alta Severidad

### TRAMPA #1 — `--test` fantasma

**Descripción:**
El patrón estándar de `--test` en la mayoría de tools es:
```python
if args.test:
    print("✅ test OK")
    sys.exit(0)
```
Esto no ejercita ninguna lógica real del tool. Pasa siempre. No detecta nada.

**Impacto:** guardian_health reporta herramientas como "testeadas" cuando no lo están.

**Remediación:**
```python
# CORRECTO — --test debe ejecutar operación real en dry-run:
if args.test:
    import json, sys
    
    # Ejercitar lógica real con datos de prueba
    result = run_actual_logic(test_mode=True)
    
    # Output estructurado verificable
    report = {
        "tool": "nombre_del_tool",
        "status": "ok" if result.success else "fail",
        "checks": [
            {"name": "can_read_state", "pass": result.can_read},
            {"name": "output_valid", "pass": result.output is not None},
        ]
    }
    print(json.dumps(report, indent=2))
    sys.exit(0 if result.success else 1)
```

---

### TRAMPA #2 — Tests autogenerados que nunca fallan

**Descripción:**
Los tests generados automáticamente verifican:
1. `return_code == 0`
2. `"pasaron" in stdout` (o "OK", "success", etc.)

Como `--test` siempre hace `print("OK")` y `sys.exit(0)`, los tests autogenerados
**siempre pasan**, independientemente de si el tool funciona.

**Impacto:** CI verde no implica nada real sobre el estado del tool.

**Remediación:**
Output estructurado JSON con `checks` verificables. CI parsea JSON y falla si
cualquier check no pasa:
```bash
python3 tools/mi_tool.py --test | python3 -c "
import json, sys
r = json.load(sys.stdin)
failed = [c for c in r['checks'] if not c['pass']]
if failed: print('FAIL:', failed); sys.exit(1)
print('ALL PASS')
"
```

---

### TRAMPA #3 — Guardian con grep

**Descripción:**
`tool_guardian.py` detecta si un tool tiene `--test` buscando el string literal `"--test"` 
en el archivo con `grep`. Cualquier aparición del string (incluso en comentarios, docstrings,
o strings de help) hace que el guardian lo marque como "compliant".

```python
# tool_guardian.py (actual — trampa):
result = subprocess.run(['grep', '-l', '--test', tool_path], ...)
has_test = result.returncode == 0  # ← busca string, no argumento real
```

**Impacto:** Se puede engañar al guardian con:
```python
# Este comentario tiene --test → guardian lo cuenta como compliant
def run():
    print("OK")
```

**Remediación:** AST parsing — verificar que argparse/click registra `--test` como argumento:
```python
import ast

def has_real_test_arg(tool_path: str) -> bool:
    """Verifica via AST que --test es un argumento registrado, no solo un string."""
    tree = ast.parse(open(tool_path).read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Buscar parser.add_argument('--test', ...) o @click.option('--test', ...)
            if is_add_argument_call(node, '--test'):
                return True
    return False
```

---

### TRAMPA #4 — CI convierte excepciones en verde

**Descripción:**
Patrón actual en varios tools y CI scripts:
```python
try:
    resultado = operacion_que_puede_fallar()
    print("✅ OK")
except Exception as e:
    print(f"✅ OK (skipped: {e})")  # ← TRAMPA: excepción → verde
```

**Impacto:** Errores reales pueden aparecer como warnings o quedar ignorados.
El CI puede quedar verde aunque el tool esté roto.

**Remediación:**
```python
# CORRECTO:
try:
    resultado = operacion_que_puede_fallar()
    print("✅ OK")
except ExpectedRecoverableError as e:
    print(f"⚠️ WARN: {e}")  # solo para errores esperados y manejables
    # NO sys.exit(0) aquí si es crítico
except Exception as e:
    print(f"❌ ERROR: {e}")
    sys.exit(1)  # ← SIEMPRE exit(1) en errores no esperados
```

---

### TRAMPA #5 — Contratos sin estado BREACHING

**Descripción:**
`contracts.py` solo tiene dos estados: `ACTIVE` y `EXPIRED`.
Una condición puede volverse falsa (incumplimiento real) pero el contrato permanece `ACTIVE`
hasta que llega la fecha de expiración.

```python
# contracts.py (actual — trampa):
def get_status(contract):
    if datetime.now() > contract.expires_at:
        return "EXPIRED"
    return "ACTIVE"  # ← no verifica si la condición es True ahora
```

**Impacto:** Un contrato puede estar en incumplimiento real durante días/semanas
mientras aparece como `ACTIVE`.

**Remediación:**
Añadir estado `BREACHING` (condición falsa ahora, aún no expirado):
```python
def get_status(contract):
    if datetime.now() > contract.expires_at:
        return "EXPIRED"
    if not evaluate_condition(contract.condition):
        return "BREACHING"  # ← condición falsa ahora mismo
    return "ACTIVE"
```

---

## Trampas de Media Severidad

### TRAMPA #6 — Métricas por cantidad

**Descripción:**
Métricas tipo `tools_count >= 100` o `commands_implemented >= 80` incentivan
crear tools/comandos vacíos o con mínima funcionalidad para alcanzar el número.

**Remediación:**
Métricas de calidad en lugar de cantidad:
```
❌ MAL:  tools_count >= 100
✅ BIEN: pct_tools_with_real_test >= 80%
✅ BIEN: pct_commands_with_real_dispatch >= 90%
✅ BIEN: avg_test_checks_per_tool >= 3
```

---

### TRAMPA #7 — Comandos duplicados inflan contador

**Descripción:**
El CLI `bago` tiene comandos que aparecen en múltiples `elif` chains, lo que infla
el contador de "comandos implementados".

**Remediación:**
Lint en CI que falle si un comando aparece en más de un `elif`:
```bash
python3 tools/bago-lint.py --check duplicate-commands bago  # debe ser 0 duplicados
```

---

### TRAMPA #8 — Tres inventarios incompatibles

**Descripción:**
El framework mantiene tres fuentes de verdad para el inventario de tools, y no coinciden:
- `tools.manifest.json`: 95 tools
- `README.md` (docs): 135 tools
- `pack.json commands`: 55 commands registrados

**Remediación:**
`tools.manifest.json` como única fuente de verdad (SoT). Todos los demás derivados:
```bash
# En CI:
python3 tools/validate_manifest.py --check consistency  # debe pasar
# Genera README section y pack.json commands desde manifest
python3 tools/sync_pack_metadata.py
```

---

### TRAMPA #9 — `--test` que valida entorno, no lógica

**Descripción:**
Muchos `--test` verifican:
- ¿Se puede importar el módulo? → `import my_tool` no falla
- ¿Existe `state/`? → `os.path.exists('state/')`

Esto valida entorno, no la lógica del tool.

**Remediación:**
Renombrar el actual a `--smoke` (smoke test de entorno).
Implementar `--test` real con asserts funcionales:
```python
# --smoke: valida entorno
# --test:  valida lógica funcional (dry-run real)
```

---

### TRAMPA #10 — Guardian busca string "--test"

*Ver Trampa #3 (Alta) — mismo mecanismo, este es el aspecto del guardian específicamente.*

**Remediación adicional:** El guardian debe ejecutar `python3 tool.py --test` y verificar
que el output es JSON válido con el schema `{tool, status, checks}`.

---

### TRAMPA #11 — Hook pre-commit silencioso

**Descripción:**
El hook pre-commit actual ignora errores de parsing silenciosamente:
```bash
# .git/hooks/pre-commit (actual):
python3 tools/validate_pack.py || true  # ← silencia errores
```

**Remediación:**
```bash
# CORRECTO:
python3 tools/validate_pack.py
if [ $? -ne 0 ]; then
    echo "❌ Commit bloqueado: validate_pack falló"
    exit 1
fi
```

---

## Trampas de Baja-Media Severidad

### TRAMPA #12 — Tests autogenerados desincronizados

**Descripción:**
Los tests autogenerados por `test_gen.py` no se regeneran cuando el tool fuente cambia.
Un tool puede evolucionar significativamente y seguir siendo validado por un test
generado para una versión anterior.

**Remediación:**
Embedir hash del tool en el test generado. CI falla si hash no coincide:
```python
# En el test generado:
TOOL_HASH = "sha256:abc123..."  # hash del tool al momento de generación

def test_hash_current():
    """Falla si el tool cambió desde que se generó este test."""
    current_hash = sha256_file("tools/mi_tool.py")
    assert current_hash == TOOL_HASH, f"Tool cambió — regenerar test con: bago test-gen mi_tool"
```

---

### TRAMPA #13 — Badges sin provenance

**Descripción:**
Los reportes `ALL PASS / 100/100` aparecen sin SHA, fecha ni referencia al CI run
que los produjo. No hay forma de verificar si son actuales o inventados.

**Remediación:**
Badges generados automáticamente desde el último CI run con SHA y fecha:
```markdown
<!-- generado por CI run #1234 · sha: abc1234 · 2026-05-01T17:25:00Z -->
![Health](https://img.shields.io/badge/BAGO_health-GO-green?label=2026--05--01)
```

---

## Estado actual (Mayo 2026)

```
guardian_health    = 0%
tools_total        = 44 (en guardian, no en manifest)
E001_no_test       = 33 tools
E002_not_registered = 29 tools
W001_no_routing    = 18 tools
W002_no_docstring  = 2 tools

Dead ref: intent_router.py → 'legacy-fix' (comando inexistente)
```

### Tools prioritarios para CHG-002

Los 5 tools más críticos que necesitan `--test` real:
1. `validate_manifest.py` — SoT del inventario
2. `validate_state.py` — validación de estado global
3. `validate_pack.py` — validación del pack completo
4. `show_task.py` — gestión de tareas activas
5. `cosecha.py` — recolección de aprendizajes

---

## Orden de remediación recomendado

```
FASE 1 — Falsos positivos (más urgente):
  #4 CI + excepciones → exit(1)
  #5 contracts.py → estado BREACHING

FASE 2 — Endurecer contrato de test:
  #1 --test con lógica real
  #2 output JSON estructurado
  #3 guardian con AST
  #10 guardian ejecuta --test real

FASE 3 — Unificar inventario:
  #8 tools.manifest.json como SoT única

FASE 4 — Limpieza estructural:
  #6 métricas de calidad
  #7 lint de duplicados
  #11 hook pre-commit exit(1)
  #12 hash en tests autogenerados

FASE 5 — Credibilidad:
  #9 renombrar --smoke / --test
  #13 badges con provenance
```

---

*Auditoría realizada: Apr 23, 2026*
*Compilado por BAGO MAESTRO · 2026-05-04*
*CHG-002 activo · CHG-003 a CHG-008 pendientes de apertura*

---

## 🆕 Nuevas trampas detectadas — Mayo 2026 (cross-learning BIANCA)

### TRAMPA #14 — Edit que consume `}` de método

**Detectada en:** BIANCA sprints 289-290 (sesión 2026-05-05)  
**Severidad:** 🔴 Alta

**Descripción:**
Cuando `old_str` en una operación `edit` termina exactamente en el `}` de cierre de un
método TypeScript, ese `}` se reemplaza y el método queda sin cerrar.
Efecto en cascada: 20+ errores TypeScript en el build siguiente.

```typescript
// ❌ MAL — old_str que CONSUME el cierre de método:
old_str: "  update(dt: number) {\n    // ... lógica ...\n  }"
// El } de cierre desaparece. TypeScript ve el método sin cerrar.

// ✅ BIEN — incluir una línea de contexto DESPUÉS del }:
old_str: "  update(dt: number) {\n    // ... lógica ...\n  }\n\n  render"
// El } de cierre se preserva porque hay contexto posterior.
```

**Remediación:**
1. Siempre incluir ≥1 línea de contexto después del `}` de cierre en `old_str`.
2. Ejecutar build (`tsc --noEmit` o `npm run build`) inmediatamente después de todo edit estructural.
3. Si el build da 20+ errores en cascada → primera sospecha: `}` consumido por edit.

---

### TRAMPA #15 — Nombre de propiedad duplicado en TS

**Detectada en:** BIANCA sprint 292 (BosqueInconclusasScene, sesión 2026-05-05)  
**Severidad:** 🟡 Media

**Descripción:**
Declarar una propiedad privada que ya existe en la clase con un shape TypeScript diferente
produce TS2300 (duplicate identifier) y TS2717 en cascada.

```typescript
// ❌ MAL — 'fireflies' ya existe en L67 con shape {x,y,vx,vy,phase,speed}:
private fireflies: Array<{x:number; y:number; life:number}> = [];  // TS2300

// ✅ BIEN — verificar antes de declarar:
// grep -n "private fireflies" src/scenes/BosqueInconclusasScene.ts → L67 encontrado
// → Usar nombre semánticamente adecuado:
private luciernagas: Array<{x:number; y:number; life:number}> = [];  // ✅
```

**Remediación:**
Antes de añadir cualquier nueva propiedad privada a una escena grande (>500 líneas):
```bash
grep -n "private nombre_planificado" ruta/escena.ts
# Si sale algún resultado → STOP, elegir nombre alternativo
```
