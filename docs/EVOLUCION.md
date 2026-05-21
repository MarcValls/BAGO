# BAGO — Evolución del Framework

> Síntesis de aprendizajes de 26 instancias + 58 sesiones · propuestas de evolución v4.0+  
> Fuente: framework_traps.md, topics/project-patterns.md, april_2026_arc.md, bago_universe.md

---

## Contexto: de dónde venimos

| Versión | Estado | Hitos clave |
|---------|--------|-------------|
| v2.2.2 | Archivado | Primera versión estable con Guardian |
| v2.5-stable | Archivado | Absorción de 7 proyectos, 10 lecciones de abril 2026 |
| v3.0 | Archivado | Refactor arquitectural, CI gates |
| **v3.3.0** | **Activo** | CHG-002 resuelto, pendrive SanDisk, 58 sesiones, 60 commits |
| v4.0 | Roadmap | Ver sección de propuestas abajo |

---

## Trampas confirmadas (a corregir en v4.0)

Extraídas de `framework_traps.md` — 15 trampas identificadas y verificadas.  
Ordenadas por impacto en producción:

---

### TRAMPA-001 · Tests que siempre pasan (crítica)

**Qué pasa:**  
```python
# Implementación actual (falsa seguridad)
def test_bago_validate():
    print("OK")
    exit(0)  # ← nunca ejercita la lógica real
```

**Por qué es grave:** CI pasa en verde. El Guardian lo marca como cubierto. En realidad no se testa nada.

**Corrección propuesta v4.0:**
```python
def test_bago_validate():
    result = subprocess.run(["python3", "bago", "validate"], capture_output=True)
    assert result.returncode == 0
    assert "OK" in result.stdout.decode()  # requiere output real
```
**Señal de detección:** `bago sincerity` — debe bloquear tests que no produzcan output verificable.

---

### TRAMPA-002 · Guardian con grep en lugar de AST (crítica)

**Qué pasa:**  
El Guardian actual detecta cobertura con `grep "def test_"` en archivos de test.  
Un archivo con `def test_placeholder(): pass` cuenta como "cubierto".

**Corrección propuesta v4.0:**  
Reemplazar grep por parsing AST:
```python
import ast
tree = ast.parse(open("test_tool.py").read())
funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
real_tests = [f for f in funcs if len(f.body) > 1]  # descarta pass/print/exit
```

**Impacto:** CHG-002 ya parcialmente resuelto (0% → 100% con `--test` real). Pendiente: AST para cobertura de lógica.

---

### TRAMPA-003 · Estado BREACHING ausente en contracts.py

**Qué pasa:**  
`contracts.py` tiene estados: `{PENDING, ACTIVE, COMPLETED, FAILED}`.  
**Falta:** `BREACHING` — un contrato puede estar activo pero violando sus postcondiciones silenciosamente.

**Corrección propuesta v4.0:**
```python
class ContractState(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    BREACHING = "breaching"  # ← NUEVO: activo pero violando postcondiciones
    COMPLETED = "completed"
    FAILED = "failed"
```

**Detección automática:** `bago sincerity` debería evaluar postcondiciones periódicamente y transicionar a BREACHING antes del fallo.

---

### TRAMPA-004 · CI captura excepciones y retorna verde

**Qué pasa:**  
```python
try:
    run_tool(args)
except Exception as e:
    logger.warning(f"Tool failed: {e}")
    return True  # ← CI marca como OK aunque la tool falló
```

**Corrección propuesta v4.0:**  
Todas las tools deben retornar exit codes reales. CI no puede "perdonar" excepciones silenciosamente.

```python
# Regla: si hay excepción crítica → exit(1), no return True
```

---

### TRAMPA-005 · Documentación inflada sin evidencia

**Qué pasa:**  
README afirma "54 tools, all passing". Guardian lo verifica con grep. CI pasa. En realidad 33 tools tenían `--test` que era `print("OK"); exit(0)`.

**Solución implementada:** CHG-002 resuelto en v3.3.0 → Guardian ahora ejercita lógica real.  
**Pendiente:** `bago sincerity` como gate obligatorio antes de cada release — rechazar si hay divergencia doc ↔ código.

---

### TRAMPA-006 · Cross-contamination entre proyectos

**Qué pasa:**  
Copiar arquitectura Canvas de BIANCA a DERIVA. Ambas son Canvas pero tienen supuestos distintos (BIANCA: determinista; DERIVA: estocástica).

**Regla de diseño a formalizar:**  
Cada proyecto mantiene su propia arquitectura Canvas. No hay herencia entre instancias `bago` aunque compartan el mismo pack.

**Implementación propuesta:**  
```bash
bago map --show-canvas-type    # nuevo flag: muestra BIANCA vs DERIVA vs custom
```

---

## Patrones a incorporar (de topics/project-patterns.md)

### P-001 · Datos canónicos, nunca hardcoded

```python
# ❌ Antes
TEMPO = 128  # hardcoded en 3 archivos

# ✅ Después
TEMPO = canonical_data["session"]["tempo"]  # fuente única
```

**Propuesta:** `bago check --canonical` — detecta valores duplicados en múltiples archivos.

---

### P-002 · 1 feature por sprint, build verificado antes de reportar

**Regla operacional:**  
No reportar "feature X implementada" hasta haber ejecutado `bago validate && bago health`.  
El guardian debe bloquear commits si hay más de 1 feature activa sin completar.

---

### P-003 · Archivos `._*` en macOS — limpieza preventiva

macOS crea forks de recursos `._archivo` silenciosamente en volúmenes FAT/ExFAT (pendrive).

```bash
# Limpieza antes de cada commit en pendrive
dot_clean -m /Volumes/bago_core/

# O en el gitignore
echo "._*" >> /Volumes/bago_core/.gitignore
```

**Propuesta:** `bago sync` incluye dot_clean automático en entornos macOS.

---

### P-004 · Activación temporal de BAGO en repos sin `.bago`

Cuando BAGO no está en el repo destino (cliente, colaborador):

```bash
git clone https://github.com/MarcValls/BAGO.git /tmp/bago-tmp
cd /tmp/bago-tmp
# trabajar...
git push
rm -rf /tmp/bago-tmp
```

**Propuesta comando:** `bago temp-activate <repo-url>` — automatiza este flujo.

---

## Features propuestas para v4.0

### F-001 · `bago universe`
Mostrar el catálogo completo de agentes activos en el sistema.

```bash
$ bago universe
╔══════════════════════════════════════════╗
║  BAGO Universe — 13 agentes activos      ║
╠══════════════════════════════════════════╣
║  FAMILIA COGNITIVA                       ║
║  • Detector     ✓ active                 ║
║  • Supervisor   ✓ active                 ║
║  • Sincerity    ✓ active                 ║
║  FAMILIA EJECUTIVA                       ║
║  • Builder      ✓ active                 ║
║  • Guardian     ✓ active (AST v4.0)      ║
║  ...                                     ║
╚══════════════════════════════════════════╝
```

**Por qué:** `bago_universe.md` tiene 13 agentes documentados. Ningún comando los muestra todos.

---

### F-002 · `sincerity_detector` como gate obligatorio de release

Actualmente `bago sincerity` es opcional. En v4.0 debe ser **bloqueante**:

```bash
# En SEQ-06 (RELEASE PREP), si sincerity falla → no se puede continuar
bago sincerity --strict   # exit(1) si hay divergencia doc ↔ comportamiento real
```

---

### F-003 · Protocolo de aprendizaje cross-proyecto

Actualmente el conocimiento acumulado en `.bago/knowledge/` se construye manualmente.  
Propuesta: pipeline automático de extracción.

```bash
bago harvest --to-knowledge   # nuevo: convierte cosecha de sesión en entrada de knowledge
bago knowledge sync            # sincroniza knowledge local con el repo GitHub
```

---

### F-004 · `bago temp-activate`

```bash
bago temp-activate <repo-url>   # clone, activa BAGO temporalmente, trabaja, limpia
bago temp-activate --cleanup    # elimina la instalación temporal
```

---

### F-005 · Dashboard de salud multi-proyecto

```bash
bago dashboard   # muestra health score de todos los proyectos .bago detectados
```

```
╔═══════════════════════════════╗
║  BAGO Dashboard               ║
╠═══════════════════════════════╣
║  ~/BAGO           health: 100 ║
║  ~/DERIVA         health:  87 ║
║  ~/AMTEC/TPV      health:  92 ║
╚═══════════════════════════════╝
```

---

### F-006 · `bago check --canonical` (anti hardcoding)

Detecta valores duplicados que deberían ser canónicos:

```bash
bago check --canonical
# → WARNING: "128" aparece en 3 archivos — considera canonicalizar como TEMPO
# → WARNING: "ws://localhost:8765" aparece en 4 archivos
```

---

## Lecciones de abril 2026 aplicables a v4.0

Extraídas de `april_2026_arc.md` (10 lecciones verificadas):

| Lección | Aplicación en v4.0 |
|---------|--------------------|
| L-003: BAGO funciona para cualquier dominio (no solo dev) | Nuevo tutorial: BAGO para proyectos creativos / música / TPV |
| L-005: Codex CLI = mejor T2I sin API key en M1 | Añadir a `image_generation` como método recomendado en docs |
| L-007: NUNCA pipear output de `codex exec` | Advertencia en COMMANDS.md |
| L-009: TypeScript 6.0 necesita `"ignoreDeprecations": "6.0"` + Vite 5.x | Actualizar GETTING_STARTED templates |
| L-010: La deriva silenciosa es peor que el error evidente | SEQ-09 SUPERVISIÓN EVOLUTIVA — hacerla periódica obligatoria |

---

## Estado de CHG-002 (resuelto en v3.3.0)

**Problema original:** Guardian reportaba 100% cobertura porque 33 de 54 tools tenían `--test` que era `print("OK"); exit(0)`.

**Solución implementada:**
- Todas las tools ahora tienen `--test` que ejercita lógica real
- Guardian verifica output real, no solo exit code
- Health: 0% → 100% ✅

**Pendiente para v4.0:** Upgrade del Guardian a parsing AST (TRAMPA-002) para cobertura de lógica, no solo de invocación.

---

## Resumen de prioridades v4.0

| Prioridad | Feature/Fix | Impacto |
|-----------|-------------|---------|
| 🔴 crítico | TRAMPA-001: tests reales vs `print("OK")` | Falsos positivos en CI |
| 🔴 crítico | TRAMPA-002: Guardian con AST | Cobertura real vs cobertura de nombres |
| 🔴 crítico | TRAMPA-003: estado BREACHING en contracts | Contratos pueden fallar silenciosamente |
| 🟡 alto | F-002: sincerity como gate bloqueante | Releases con divergencia doc↔código |
| 🟡 alto | F-001: `bago universe` | Visibilidad del sistema de agentes |
| 🟢 medio | F-003: harvest → knowledge automático | Knowledge base más viva, menos manual |
| 🟢 medio | F-005: dashboard multi-proyecto | Visión global del ecosistema |
| 🟢 bajo | F-004: `bago temp-activate` | Comodidad en repos sin BAGO |

---

*BAGO v3.3.0 → v4.0 · Documento de evolución · 2026-05-08*  
*Fuente: framework_traps.md (15 trampas), topics/project-patterns.md, april_2026_arc.md (10 lecciones)*
