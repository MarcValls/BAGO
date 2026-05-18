# Menú `/` — Manual de Comandos BAGO Chat

> **BAGO — A.M. TECHNOLOGIES**  
> Comandos del REPL conversacional · acceso desde `bago launch`

---

## Activar el menú

Dentro del REPL de `bago launch`, escribe `/` y pulsa **Tab** para abrir  
el **menú interactivo navegable** (flechas + Enter), o escribe directamente  
cualquier comando `/xxx` si ya sabes el que necesitas.

```
[BAGO|AUTO] > /
```

```
┌─ BAGO — Menú principal ─────────────────────────────────────┐
│                                                              │
│  >> 🔑 Providers & Login                                    │
│     🤖 Modelos & Routing                                    │
│     🧠 Agentes                                              │
│     ⚡ Skills                                               │
│     🔀 Matriz de Routing                                    │
│     🏭 Fábrica de artefactos (/new)                        │
│     👤 Roles del orquestador                               │
│     💾 Sesión & Memoria                                    │
│     ⚙️  Configuración                                       │
│     📊 Framework & Proyectos                               │
│                                                              │
│  ↑/↓ navegar   Enter seleccionar   Esc volver               │
└──────────────────────────────────────────────────────────────┘
```

---

## Referencia completa de comandos `/`

### 🔑 Providers y credenciales

| Comando | Descripción |
|---------|-------------|
| `/login` | Abre el menú interactivo de providers (flechas + Enter) |
| `/login github` | Login con GitHub → activa Copilot (`gh auth login`) |
| `/login gpt` | API key OpenAI → activa GPT / Codex |
| `/login openai` | Alias de `/login gpt` |
| `/login codex` | Alias de `/login gpt` |
| `/login anthropic` | API key Anthropic → activa Claude |
| `/login ollama` | Verifica que Ollama local está corriendo |
| `/auth` | Superset de `/login` — gestión completa de credenciales |

**Ejemplo — añadir Anthropic:**
```
[BAGO|AUTO] > /login anthropic
  → Introduce tu API key de Anthropic: sk-ant-...
  ✔ Anthropic activado
```

---

### 🤖 Control de modelo

| Comando | Descripción |
|---------|-------------|
| `/switch <modelo>` | Cambia el motor activo sin perder el historial |
| `/switch copilot` | Salta a GitHub Copilot |
| `/switch ollama` | Salta al mejor modelo Ollama local |
| `/switch qwen2.5:14b` | Modelo específico por nombre |
| `/autoroute on` | Activa routing automático (default) |
| `/autoroute off` | Desactiva — BAGO usa siempre el motor actual |
| `/models` | Lista todos los modelos disponibles por provider |

**Ejemplo — ver modelos:**
```
[BAGO|AUTO] > /models

┌────────────────────────────────────────────────────┐
│                  Registry BAGO                     │
│                                                    │
│  ollama-local                                      │
│    qwen2.5:14b      wire: qwen2.5:14b              │
│    qwen2.5-coder    wire: qwen2.5-coder:7b         │
│    llama3.2         wire: llama3.2:3b              │
│                                                    │
│  copilot                                           │
│    gpt-4o           wire: gpt-4o                   │
│    o3-mini          wire: o3-mini                  │
└────────────────────────────────────────────────────┘
```

---

### 🔀 Estrategias multi-modelo

| Comando | Descripción |
|---------|-------------|
| `/chain m1->m2: prompt` | Pipeline: m1 genera, m2 revisa y mejora |
| `/chain m1->m2->m3: prompt` | Pipeline de 3 etapas |
| `/ensemble m1 m2: prompt` | Paralelo: ambos responden, BAGO sintetiza |

**Ejemplo — chain para código:**
```
[BAGO|AUTO] > /chain qwen2.5-coder->copilot: implementa una función de fibonacci optimizada

  paso 1/2: qwen2.5-coder...  ✔
  paso 2/2: copilot revisando...  ✔

╭─ BAGO  vía copilot (síntesis chain) ──────────────────────╮
│  def fibonacci(n: int) -> int:                             │
│      a, b = 0, 1                                           │
│      ...                                                   │
╰────────────────────────────────────────────────────────────╯
```

**Ejemplo — ensemble para comparar opciones:**
```
[BAGO|AUTO] > /ensemble copilot ollama: ¿PostgreSQL o MongoDB para este proyecto?

  copilot...    ✔
  ollama...     ✔
  BAGO sintetizando...

╭─ BAGO  vía ensemble (copilot + ollama) ──────────────────╮
│  Síntesis de ambas perspectivas:                          │
│  ...                                                      │
╰────────────────────────────────────────────────────────────╯
```

---

### 🧠 Agentes

Los agentes son roles especializados que BAGO puede activar para tareas específicas.

| Comando | Descripción |
|---------|-------------|
| `/agents` | Lista todos los agentes registrados |
| `/agents <nombre>` | Ver detalle de un agente |
| `/agents add <nombre>` | Crear un agente nuevo (asistido por LM) |
| `/agents toggle <nombre>` | Activar / desactivar un agente |
| `/agents set <nombre> <campo> <valor>` | Editar campo del agente |
| `/agents del <nombre>` | Eliminar agente |

**Ejemplo — listar agentes:**
```
[BAGO|AUTO] > /agents

╭─ Agentes BAGO ──────────────────────────────────────────╮
│  ● MAESTRO_BAGO      activo   orquestador central       │
│  ● VALIDADOR         activo   calidad y validación      │
│  ○ EXPLORADOR        inactivo investigación web         │
│  ● DOC_WRITER        activo   documentación             │
╰──────────────────────────────────────────────────────────╯
```

---

### ⚡ Skills

Las skills son capacidades especializadas reutilizables.

| Comando | Descripción |
|---------|-------------|
| `/skills` | Lista todas las skills |
| `/skills <nombre>` | Ver detalle de una skill |
| `/skills add <nombre>` | Crear skill nueva (asistido por LM) |
| `/skills set <nombre> <campo> <valor>` | Editar campo |
| `/skills del <nombre>` | Eliminar skill |

---

### 🗺️ Matriz de routing

La matriz define qué motor usa BAGO para cada tipo de tarea.

| Comando | Descripción |
|---------|-------------|
| `/routing` | Ver la matriz completa de reglas |
| `/routing <id>` | Ver una regla concreta |
| `/routing add <id> provider=X model=Y keywords=K reason=R` | Añadir regla |
| `/routing del <id>` | Eliminar regla |
| `/routing fallback <provider> <model>` | Cambiar el fallback global |
| `/routing move <id> up\|down` | Reordenar prioridad de reglas |

**Ejemplo — ver matriz:**
```
[BAGO|AUTO] > /routing

╭─ Matriz de routing BAGO ────────────────────────────────────╮
│  #  ID              Provider       Model           Keywords  │
│  1  code-tasks      ollama-local   qwen2.5-coder   código,fn │
│  2  analysis        copilot        gpt-4o          analiza   │
│  3  creative        anthropic      claude-3.5      redacta   │
│  —  [fallback]      ollama-local   qwen2.5:14b               │
╰──────────────────────────────────────────────────────────────╯
```

---

### 🏭 Fábrica de artefactos (`/new`)

El wizard asistido por LM para crear cualquier artefacto BAGO.

| Comando | Descripción |
|---------|-------------|
| `/new` | Abre el wizard de fábrica |
| `/wizard` | Alias de `/new` |
| `/fabrica` | Alias de `/new` |

**7 tipos de artefacto en 3 categorías:**

```
┌─ BAGO — Fábrica de Artefactos ─────────────────────────────┐
│                                                             │
│  🧠 INTELIGENCIA                                           │
│     >> Agente        (rol especializado con memoria)       │
│        Skill         (capacidad reutilizable)              │
│                                                             │
│  ⚡ SPRINT / NEURAL                                        │
│        Nodo Neural   (toolbox de sprint adaptativo)        │
│                                                             │
│  🔀 ORQUESTACIÓN                                           │
│        Regla routing          (cuándo usar qué motor)      │
│        Preferencia de tarea   (cómo abordar un tipo)       │
│        Modo orquestador       (offline/eco/estándar/full)  │
│                                                             │
│  🔧 HERRAMIENTAS                                           │
│        Tool Python   (genera script con main() listo)      │
│                                                             │
│  ↑/↓ navegar   Enter seleccionar   Esc volver              │
└─────────────────────────────────────────────────────────────┘
```

Describes en lenguaje natural lo que quieres → el LM genera la definición completa.

---

### 👤 Roles del orquestador

Los roles definen el perfil de comportamiento de BAGO.

| Comando | Descripción |
|---------|-------------|
| `/roles` | Ver modos disponibles |
| `/roles <modo>` | Ver detalle de un modo |
| `/roles tasks` | Ver preferencias por tipo de tarea |
| `/roles tasks <tarea>` | Ver configuración para una tarea concreta |

**Modos disponibles:**
| Modo | Descripción |
|------|-------------|
| `offline` | Solo modelos locales, sin cloud |
| `eco` | Minimiza coste — prioriza modelos rápidos y baratos |
| `standard` | Balance calidad/coste (default) |
| `full` | Máxima calidad, sin restricciones de coste |
| `auto` | BAGO decide según contexto y complejidad |

```
[BAGO|AUTO] > /generative
→ Selecciona modo: standard ✔   (/mode sigue siendo alias)
```

---

### 💾 Sesión, memoria y sincronización

| Comando | Descripción |
|---------|-------------|
| `/session` | Gestión completa de sesión |
| `/save` | Guarda la sesión actual en disco |
| `/clear` | Limpia el historial de conversación |
| `/status` | Estado completo de la sesión activa |
| `/sync` | Sincroniza con GitHub/USB + post-sync |
| `/memory` | Base de conocimiento + memoria episódica |

**`/status` — información detallada:**
```
[BAGO|AUTO] > /status

╭─ Estado BAGO ───────────────────────────────────────────────╮
│  Modelo:      qwen2.5:14b (ollama-local)                   │
│  Wire:        qwen2.5:14b                                   │
│  Modo:        standard                                      │
│  Routing:     AUTO → qwen2.5-coder (ollama-local)          │
│  Motivo:      tarea de código detectada                     │
│  Historial:   12 mensajes                                   │
│  Switches:    1                                             │
│  Tiempo:      0:04:32                                       │
│  Auto-route:  ON                                            │
│  Post-sync:   continuar                                     │
│  Providers:   ollama-local, copilot                        │
╰──────────────────────────────────────────────────────────────╯
```

**`/session` — opciones:**
```
┌─ Gestión de sesión ──────────────────────────────────────────┐
│  >> Guardar en disco                                         │
│     Sesión temporal (no persiste)                           │
│     Cargar sesión anterior                                  │
│     Repliegue (pausa + guardar estado)                      │
│     Letargo   (hibernar)                                    │
│     Cerrar                                                  │
└──────────────────────────────────────────────────────────────┘
```

---

### 🤖 Modo autónomo (`/auto`)

BAGO puede actuar sin pedir confirmaciones.

| Comando | Descripción |
|---------|-------------|
| `/auto` | Abre el panel de configuración autónoma |

**Panel `/auto`:**
```
┌─ Modo autónomo BAGO ─────────────────────────────────────────┐
│                                                              │
│  >> [ ON ] Modo autónomo         (actualmente OFF)          │
│     [ ADAPTATIVO ] Confirmaciones (always / adaptativo / balanceado / never) │
│     Máx. iteraciones: 10                                    │
│                                                              │
│  ─────────────────────────────────────────────────          │
│     Activar autónomo ahora                                   │
│     Ver historial de acciones                               │
│     Desactivar                                              │
└──────────────────────────────────────────────────────────────┘
```

| Nivel de confirmación | Comportamiento |
|----------------------|----------------|
| `always` | Siempre pide confirmación |
| `adaptativo` | Ajusta la autonomía según contexto y riesgo (default) |
| `balanceado` | Equilibra autonomía y supervisión |
| `never` | Sin confirmaciones — máxima autonomía |

---

### ⚙️ Configuración global

| Comando | Descripción |
|---------|-------------|
| `/config` | Abre el panel de configuración persistente |

---

### 📊 Framework y proyectos

| Comando | Descripción |
|---------|-------------|
| `/framework` | Vista evolutiva: sprint activo, health, ideas, componentes |
| `/workspaces` | Gestión de workspaces (un workspace = N proyectos) |
| `/projects` | Gestión de proyectos dentro del workspace activo |

---

### 🚪 Sesión — salida y control

| Comando | Descripción |
|---------|-------------|
| `/exit` | Sale del REPL limpiamente |
| `/clear` | Limpia el historial de conversación (no cierra) |
| `/save` | Guarda la sesión en disco |
| `/status` | Estado completo (modelo, routing, tiempo, historial) |

---

## Referencia rápida (cheatsheet)

```
PROVIDERS
  /login               → menú interactivo
  /login github        → activa Copilot
  /login openai        → activa GPT/Codex
  /login anthropic     → activa Claude
  /login ollama        → verifica Ollama

MODELOS
  /switch <modelo>     → cambia motor
  /autoroute on|off    → routing auto
  /models              → lista modelos

MULTI-MODELO
  /chain m1->m2: ...   → pipeline
  /ensemble m1 m2: ... → paralelo

ARTEFACTOS
  /new                 → fábrica wizard

AGENTES & SKILLS
  /agents              → gestión agentes
  /skills              → gestión skills

ROUTING
  /routing             → matriz reglas
  /roles               → modos orquestador
  /generative          → cambio rápido modo (/mode es alias)

SESIÓN
  /status              → estado completo
  /save                → guardar
  /clear               → limpiar historial
  /session             → gestión sesión
  /sync                → sincronizar
  /memory              → conocimiento

CONFIG
  /config              → configuración
  /auto                → modo autónomo

FRAMEWORK
  /framework           → vista evolutiva
  /workspaces          → workspaces
  /projects            → proyectos

SALIR
  /exit                → salir limpio
  Ctrl+C × 3          → salir forzado
```

---

*Auto-documentado · BAGO framework · A.M. TECHNOLOGIES*
