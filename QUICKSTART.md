# Manual de usuario · BAGO v3.4.1

> Para quien instala BAGO por primera vez y quiere entender cómo usarlo en su día a día.

---

## 1. ¿Qué es BAGO?

**BAGO** (Balanceado · Adaptativo · Generativo · Organizativo) es una capa de operación que vive dentro de tu repositorio y trabaja junto a cualquier agente de IA (GitHub Copilot, Claude, GPT…).

Resuelve cuatro problemas concretos:

| Problema | Sin BAGO | Con BAGO |
|---|---|---|
| Pérdida de contexto entre sesiones | El agente no recuerda qué hiciste | Estado persistente en `.bago/state/` |
| Arranques improvisados | El agente empieza sin rol ni protocolo | Bootstrap estructurado antes de cada sesión |
| Cambios sin rastro | Las decisiones se pierden | Cada cambio genera un artefacto `BAGO-CHG` |
| Ideas sin gestión | Las mejoras se quedan en el aire | `bago ideas` con puntuación y registro |

BAGO **no es** un agente. Es el sistema operativo debajo de cualquier agente.

---

## 2. Instalación

### Requisitos
- Python 3.9 o superior
- Sin dependencias externas (usa solo la librería estándar)

### Pasos

```bash
# 1. Clona el repositorio
git clone https://github.com/MarcValls/BAGO.git
cd BAGO

# 2. Instala el comando bago
pip install -e .

# 3. Verifica que el sistema está bien
bago validate

# Salida esperada:
# GO manifest
# GO state
# GO pack

# 4. Comprueba el estado inicial
bago health

# Salida esperada en instalación limpia:
# BAGO Health: initializing ⚪
# No closed sessions yet...
```

> **Nota:** El estado `initializing` es **correcto** en una instalación nueva. El score de salud solo sube con el uso real del sistema.

---

## 3. Comandos clave

### Diagnóstico

#### `bago health`
Muestra el estado de salud del sistema (0–100).

```bash
bago health
```

- En instalación limpia: `initializing ⚪` (normal, sin historial todavía)
- Con sesiones reales: `🟢 80/100` o similar

---

#### `bago validate`
Verifica la integridad del sistema: manifiesto, estado y checksums.

```bash
bago validate
```

Ejecuta este comando **antes y después** de cada sesión de trabajo. Si algo está mal, lo indica aquí.

---

#### `bago audit`
Auditoría completa: integridad, inventario, reportes, health score y workflow recomendado.

```bash
bago audit full
```

Ejemplo de salida:
```
[1] INTEGRIDAD    ✅  GO pack
[2] INVENTARIO    ✅  ses=0/chg=0/evd=0
[3] REPORTING     ✅  Sin artefactos stale
[4] HEALTH SCORE  ✅  🟢 80/100
[5] VÉRTICE       ✅  CLEAN
[6] WORKFLOW      →  W0_FREE_SESSION
```

---

#### `bago status`
Estado actual: flujo activo, tarea pendiente y salud del sistema.

```bash
bago status
```

---

#### `bago context stale`
Detecta artefactos o tareas que llevan demasiado tiempo sin cerrarse.

```bash
bago context stale
```

---

### Comandos de trabajo

#### `bago ideas`
Lista las ideas priorizadas (0–100) para el siguiente paso de mejora del sistema.

```bash
bago ideas

# Aceptar una idea para trabajarla (la convierte en tarea W2):
bago ideas --accept 1

# Ver detalle de una idea concreta:
bago ideas --detail 2
```

---

#### `bago task`
Muestra la tarea W2 activa (si existe).

```bash
bago task
```

Las tareas se crean al aceptar una idea con `bago ideas --accept N`.

---

#### `bago session`
Gestión del ciclo de sesión.

```bash
bago session open     # abre sesión desde el handoff anterior
bago session close    # cierra la sesión actual
bago session harvest  # cosecha artefactos (protocolo W9)
```

---

#### `bago flow`
Gestión del workflow activo.

```bash
bago flow status      # ver workflow activo
bago flow start W2    # activar un workflow
bago flow done        # cerrar el workflow actual
```

---

#### `bago workflow`
Inspecciona los workflows disponibles o uno concreto.

```bash
bago workflow         # ver todos los workflows
bago workflow W2      # inspeccionar uno concreto
```

---

### Comandos de visión

#### `bago dashboard`
Vista general del sistema: estado del pack, inventario y detector W9.

```bash
bago dashboard
```

---

#### `bago audit scan`
Detecta si el contexto del repositorio ha cambiado desde la última sesión.

```bash
bago audit scan
```

---

## 4. Los 11 workflows operativos

Los workflows son los "modos de trabajo" de BAGO. El sistema los recomienda automáticamente según el contexto, pero puedes elegir el tuyo.

| Workflow | Cuándo usarlo |
|---|---|
| **W0 · Sesión Libre** | Exploración sin estructura, modo off |
| **W1 · Cold Start** | Primera vez en un repositorio desconocido |
| **W2 · Implementación Controlada** | Tienes una tarea concreta y quieres hacerla bien |
| **W3 · Refactor Sensible** | Cambios estructurales de alto riesgo |
| **W4 · Debug Multicausa** | Un bug con varias causas posibles |
| **W5 · Cierre y Continuidad** | Cerrar la sesión con handoff completo |
| **W6 · Ideación Aplicada** | Generar y priorizar ideas de mejora |
| **W7 · Foco de Sesión** | Sesión con objetivo único y bien delimitado *(recomendado para uso diario)* |
| **W8 · Exploración** | Explorar el pack sin objetivo concreto previo |
| **W9 · Cosecha** | Formalizar valor generado en sesión libre |
| **W10 · Auditoría de Sinceridad** | Detectar afirmaciones sin evidencia en el historial |

### ¿Cuál usar en el día a día?

```
¿Tienes un objetivo concreto?
  → Sí → W7 (Foco de Sesión)
  → No, quiero explorar → W8 (Exploración)
  → Hay un bug → W4 (Debug Multicausa)
  → Quiero ideas → W6 (Ideación) → luego W2 para implementar
  → Fin de sesión → W9 (Cosecha) o W5 (Cierre y Continuidad)
```

---

## 5. Flujo de sesión típico

### Sesión estándar (30–90 min)

```bash
# 1. ANTES DE EMPEZAR — verifica el sistema
bago validate
bago health

# 2. DECIDE QUÉ HACER
bago status             # ver flujo activo y tarea pendiente
bago ideas              # ver qué hay priorizado

# 3. TRABAJA
# Abre .bago/AGENT_START.md en tu agente de IA
# El agente cargará el estado y sabrá dónde estás

# 4. AL TERMINAR — registra el trabajo
bago session harvest    # cosecha artefactos (W9)
bago validate           # verifica que todo sigue bien
```

### Flujo de una idea nueva → implementación

```bash
# Ver ideas disponibles
bago ideas

# Aceptar la idea #1
bago ideas --accept 1

# Ver la tarea creada
bago task

# Trabajar con tu agente de IA (señalar AGENT_START.md como contexto)

# Al terminar, cosechar
bago session harvest
```

---

## 6. Integrar BAGO con tu agente de IA

### GitHub Copilot / Claude / GPT

El punto de entrada para el agente es `.bago/AGENT_START.md`. Añade esta instrucción al inicio de tu sesión:

```
Lee .bago/AGENT_START.md antes de hacer nada. Luego procede.
```

### Con GitHub Copilot CLI

Si tienes instalada la extensión BAGO para Copilot CLI:

```bash
bago setup
```

### Disparador automático `.bago/`

Para que el agente arranque BAGO automáticamente cuando escribes `.bago/`, crea un archivo `AGENTS.md` en la raíz del repo:

```markdown
# AGENTS

## BAGO Trigger

Si el usuario escribe `.bago/`, lee `.bago/AGENT_START.md` y sigue la ruta oficial de arranque.
No listar la carpeta `.bago/` salvo petición explícita.
```

---

## 7. Conceptos clave

### Estado (`state/`)
BAGO mantiene su estado en `.bago/state/`:
- `global_state.json` — estado global (versión, health, inventario)
- `ESTADO_BAGO_ACTUAL.md` — resumen en lenguaje natural del estado actual
- `pending_w2_task.json` — tarea W2 activa (si existe)

`.bago/state/` es **gitignored**. Las plantillas de estado limpio viven en `.bago/state.example/` (versionadas).

### Artefactos BAGO-CHG
Cada cambio significativo genera un artefacto en `.bago/state/changes/`:
```
BAGO-CHG-001-descripcion.json
```
Estos artefactos son la trazabilidad del sistema.

### Roles
BAGO tiene 13 roles especializados organizados en 4 categorías:

| Categoría | Roles |
|---|---|
| **Gobierno** | MAESTRO_BAGO, ORQUESTADOR_CENTRAL |
| **Supervisión** | VÉRTICE, AUDITOR_CANÓNICO |
| **Producción** | ANALISTA, ARQUITECTO, GENERADOR, ORGANIZADOR, VALIDADOR |
| **Especialistas** | REVISOR_UX, REVISOR_PERFORMANCE, REVISOR_SEGURIDAD, INTEGRADOR_REPO |

El agente activa solo los roles necesarios para cada sesión (máximo 3 activos a la vez).

### Pack (`pack.json`)
El manifiesto central del sistema. Define versión, rutas canónicas, contratos y workflows registrados. **No editar manualmente.**

---

## 8. Preguntas frecuentes

**¿Por qué `bago health` dice "initializing" pero `bago audit` muestra 80/100?**
Son dos modos distintos. `bago health` es contextual: si no hay sesiones cerradas, muestra "initializing" para indicar que aún no hay historial. `bago audit` calcula el score técnico del pack independientemente del historial. Ambos son correctos.

**¿Debo ejecutar `bago validate` siempre?**
Sí. `bago validate` regenera `CHECKSUMS.sha256` y `TREE.txt`. Ejecutarlo antes y después de cada sesión es una buena práctica. Sus cambios deben incluirse en cada commit.

**¿Cómo se usa el comando `bago versions`?**
Requiere un directorio `cleanversion/` con snapshots históricos del sistema. No está incluido en el repositorio público. Se usa internamente para comparar versiones anteriores del framework.

**¿Puedo usar BAGO en cualquier repositorio?**
Sí. Clona el repo con `git clone https://github.com/MarcValls/BAGO.git`, instala con `pip install -e .` y ejecuta `bago validate`. Para que el agente de IA lo detecte automáticamente, añade el `AGENTS.md` descrito en la sección 6.

**¿Qué significa que un comando es "legacy"?**
Los comandos legacy redirigen a su equivalente actual. Por ejemplo, `bago cosecha` redirige a `bago session harvest`. Funcionan, pero usa los equivalentes modernos para evitar deprecaciones futuras.

---

## 9. Referencia rápida

```bash
# DIAGNÓSTICO
bago health              → estado de salud (0–100)
bago validate            → integridad del sistema
bago audit full          → auditoría completa
bago status              → flujo activo + tarea pendiente
bago context stale       → artefactos caducados

# TRABAJO
bago ideas               → ideas priorizadas
bago task                → tarea activa W2
bago session open        → abrir sesión desde handoff
bago flow start W2       → activar workflow
bago workflow            → inspeccionar workflows

# AUTONOMÍA
bago autonomous --dry-run   → vista previa del bucle autónomo
bago autonomous --yes       → ejecutar bucle SENSE/PLAN/ACT/LEARN
bago inbox add <intent>     → añadir intent al inbox
bago inbox list             → ver intents pendientes

# CIERRE
bago session harvest     → cosechar sesión (W9)

# VISIÓN
bago dashboard           → vista general
bago audit scan          → detector de drift
bago context map         → mapa del workspace

# VER TODOS LOS COMANDOS
bago help
```

---

*BAGO v3.4.1 · Mayo 2026 · 126 comandos públicos · 38 core · 80 experimental · 8 dangerous · 28 legacy*

