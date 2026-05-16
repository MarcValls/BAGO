# `bago launch` — Manual de Usuario

> **BAGO — A.M. TECHNOLOGIES**  
> Comando core · stability: `core` · preflight: `required`

---

## ¿Qué es `bago launch`?

`bago launch` es el **punto de entrada principal** del framework BAGO.  
Abre la interfaz conversacional donde el usuario habla directamente con **BAGO**,  
el orquestador central de A.M. TECHNOLOGIES.

```
El usuario  ──►  BAGO  ──►  [Qwen / GPT / Claude / Llama / ...]
                  ▲                        │
                  └────────────────────────┘
              BAGO recibe, decide y responde
```

Todos los modelos de IA trabajan **dentro** del framework BAGO. Son motores internos.  
El usuario nunca habla con los modelos directamente — habla con **BAGO**.

---

## Uso

```bash
bago launch                        # Detecta provider automáticamente
bago launch --provider copilot     # Fuerza Copilot (GitHub)
bago launch --provider ollama      # Fuerza Ollama local
bago launch --model qwen2.5:14b    # Modelo específico
bago launch --task "revisar código" # Pre-ruta la sesión por tipo de tarea
```

---

## Secuencia de arranque

### 1 · Splash animado (solo en TTY interactivo)

Al ejecutar `bago launch`, aparece el splash de activación:

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░█░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░█████████████████████░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░██████▓▓▓▓▓████████████▓▓▓▓▓██░░░░░░░░░░░░░░░░
░░░░░░░░░░░██████████▓▓▓▓▓████████▓▓▓▓▓███████████░░░░░░░░░░░
░░░░░░░░░██████████████▓▓▓▓▓▓▓▓▓▓▓▓▓▓███████████████░░░░░░░░░
░░░░░░░░█████████████████▓▓▓▓▓▓▓▓▓▓██████████████████░░░░░░░░
░░░░░░██████████████████▓██▓▓▓▓▓▓██▓███████████████████░░░░░░
░░░░░█▓▓▓██████████████▓▓▓███▓▓███▓▓▓██████████████▓▓▓██░░░░░
░░░░█▓▓▓▓▓▓▓▓▓▓█████████▓▓▓█▓▓▓▓█▓▓▓█████████▓▓▓▓▓▓▓▓▓▓██░░░░
░░░░█▓▓▓▓█████▓▓▓▓▓▓▓▓███▓▓▓▓▓▓▓▓▓▓███▓▓▓▓▓▓▓▓█████▓▓▓▓██░░░░
░░░█▓▓▓▓█████████████▓▓▓▓██████████▓▓▓▓█████████████▓▓▓▓██░░░
░░░▓▓▓▓▓▓▓▓▓▓▓▓▓████████▓▓▓▓▓▓▓▓▓▓▓▓████████▓▓▓▓▓▓▓▓▓▓▓▓▓█░░░
░░░███████████▓▓▓▓▓▓▓▓▓▓▓▓▓██▓▓██▓▓▓▓▓▓▓▓▓▓▓▓▓████████████░░░
░░████████████████████▓▓▓▓▓▓████▓▓▓▓▓▓█████████████████████░░
░░░██████████████████▓▓▓▓▓▓▓████▓▓▓▓▓▓▓███████████████████░░░
░░░░███████████████████▓▓▓▓▓▓██▓▓▓▓▓▓▓████████████████████░░░░
░░░░░███████████████████▓▓██▓▓▓▓▓▓██▓▓████████████████████░░░░
░░░░░░██████████████████▓▓▓██████▓▓▓███████████████████░░░░░░
░░░░░░░░█████████████████▓▓▓████▓▓▓██████████████████░░░░░░░░
░░░░░░░░░░░████████████████▓▓▓▓▓▓█████████████████░░░░░░░░░░░

              ██████╗  █████╗  ██████╗  ██████╗
              ██╔══██╗██╔══██╗██╔════╝ ██╔═══██╗
              ██████╔╝███████║██║  ███╗██║   ██║
              ██╔══██╗██╔══██║██║   ██║██║   ██║
              ██████╔╝██║  ██║╚██████╔╝╚██████╔╝
              ╚═════╝ ╚═╝  ╚═╝ ╚═════╝  ╚═════╝

              ⣾  INICIANDO DESDE EL DISPOSITIVO BAGO...
```

**Colores del splash:**
| Símbolo | Color | Significado |
|---------|-------|-------------|
| `░` | Verde dim | Fondo / espacio vacío |
| `▓` | Cyan | Tonos medios del logo |
| `█` | Blanco brillante | Estructura sólida del robot |
| Logo BAGO | Gradiente cyan→azul | Nombre del framework |
| Spinner `⣾⣽⣻⢿⡿⣟⣯⣷` | Cyan | Progreso de inicialización |

El spinner gira hasta **10 segundos** mientras se cargan providers y credenciales.

---

### 2 · Banner principal

Tras el splash aparece el **banner de sesión**:

```
+--------------------------------------------------------+
| BAGO — Orquestador Central  ·  A.M. TECHNOLOGIES       |
| Motor: qwen2.5:14b (ollama-local)  |  Routing: AUTO    |
| Providers: copilot  ollama-local  ollama-cloud  codex  |
| Escalado automático: local → local-grande → cloud      |
| /help para comandos   /login para providers            |
+--------------------------------------------------------+
```

#### Anatomía del banner

```
┌─────────────────────────────────────────────────────────┐
│  BAGO — Orquestador Central  ·  A.M. TECHNOLOGIES       │  ← Identidad
│                                                         │
│  Motor: qwen2.5:14b (ollama-local)  |  Routing: AUTO   │  ← Motor interno
│  │       │             │                   │            │
│  │       │             │                   └─ AUTO / MANUAL / CHAIN / ENSEMBLE
│  │       │             └─ Provider activo
│  │       └─ Modelo subyacente (trabajador interno de BAGO)
│  └─ Campo dim — el usuario ve BAGO, no el modelo
│                                                         │
│  Providers: copilot  ollama-local  ollama-cloud  codex  │  ← Estado conexiones
│  │           verde=activo    rojo=sin credenciales       │
│                                                         │
│  Escalado automático: local → local-grande → cloud      │  ← Política escalado
└─────────────────────────────────────────────────────────┘
```

**Campo "Motor"** (dim, interno):
- Muestra qué motor de IA está trabajando actualmente
- El usuario no habla con él directamente — es un trabajador de BAGO
- Puede cambiar dinámicamente según la tarea (escalado automático)

**Campo "Routing":**
| Valor | Significado |
|-------|-------------|
| `AUTO` | BAGO elige el motor automáticamente según la tarea |
| `MANUAL` | El usuario ha fijado un modelo con `/switch` |
| `CHAIN` | Pipeline secuencial activo (modelo A → modelo B) |
| `ENSEMBLE` | Consulta paralela a varios modelos |
| `AUTO:A` | Auto + modo autónomo activado |

**Providers** (colores):
| Color | Estado |
|-------|--------|
| 🟢 Verde | Provider activo con credenciales válidas |
| 🔴 Rojo | Sin credenciales / no disponible |

---

### 3 · REPL conversacional

Tras el banner, BAGO abre el REPL:

```
[BAGO|AUTO] >
```

#### Anatomía del prompt

```
[BAGO|AUTO] >
  │     │
  │     └─ Modo de routing actual:
  │          AUTO      = routing automático
  │          MANUAL    = modelo fijo por el usuario
  │          CHAIN     = pipeline multi-modelo
  │          ENSEMBLE  = paralelo multi-modelo
  │          AUTO:A    = autónomo activo
  │
  └─ Siempre "BAGO" — el usuario habla con el orquestador,
     nunca directamente con el modelo subyacente
```

---

## Flujo de una conversación

```
[BAGO|AUTO] > ¿Cómo optimizo esta función Python?

  ╔══ BAGO — analizando tarea... ══╗
  ║  → Deduce: tarea de código      ║
  ║  → Selecciona: qwen2.5-coder    ║
  ║  → Estrategia: SINGLE (local)   ║
  ╚════════════════════════════════╝

╭─ BAGO  vía qwen2.5-coder/ollama-local ──────────────────╮
│                                                          │
│  Para optimizar la función, considera:                   │
│  1. Usa list comprehensions en lugar de bucles for...    │
│  ...                                                     │
│                                                          │
╰──────────────────────────────────────────────────────────╯
```

**La respuesta aparece siempre bajo el título `BAGO`** con el motor en texto dim.

---

## Escalado automático de contexto

BAGO implementa escalado automático cuando el contexto se satura:

```
local (pequeño)
    ↓  contexto saturado
local (más grande)
    ↓  local agotado
cloud (mejor para la tarea deducida)
```

| Fase | Lógica |
|------|--------|
| **Fase 1** | Busca un modelo más grande en Ollama local (por nombre: 7b→14b→32b…) |
| **Fase 2** | Si local está agotado, deduce el mejor cloud según la tarea y salta a él |

**Deducción del cloud por tarea:**
| Provider | Activado por palabras clave |
|----------|----------------------------|
| `codex` | código, función, clase, script, API, test, bug, refactor… |
| `copilot` | explica, analiza, diseña, arquitectura, razonamiento, estrategia… |
| `anthropic` | redacta, escribe, resume, traduce, artículo, ensayo… |

---

## Opciones de arranque

| Flag | Descripción | Ejemplo |
|------|-------------|---------|
| `--provider <p>` | Fuerza un provider específico | `--provider ollama` |
| `--model <m>` | Usa un modelo concreto | `--model qwen2.5:14b` |
| `--task <t>` | Pre-ruta por tipo de tarea | `--task "revisar código"` |

Sin flags, BAGO **autodetecta** el mejor provider disponible según credenciales activas.

**Prioridad de autodetección:**
```
1. ollama-local   (si Ollama está corriendo)
2. copilot        (si hay credenciales GitHub)
3. codex          (si hay API key OpenAI)
4. anthropic      (si hay API key Anthropic)
```

---

## Providers soportados

| Provider | Identificador | Modelos típicos | Requiere |
|----------|--------------|-----------------|---------|
| Ollama Local | `ollama-local` | qwen2.5, llama3, mistral, codestral… | Ollama corriendo |
| Ollama Cloud | `ollama-cloud` | Modelos remotos vía Ollama API | URL + key |
| GitHub Copilot | `copilot` | GPT-4o, o3-mini | `gh auth login` |
| OpenAI / Codex | `codex` | gpt-4, o1, codex… | `OPENAI_API_KEY` |
| Anthropic | `anthropic` | claude-3.5-sonnet… | `ANTHROPIC_API_KEY` |

Para añadir credenciales:
```bash
/login            # menú interactivo
/login github     # activa Copilot vía gh CLI
/login ollama     # verifica Ollama local
/login openai     # añade API key OpenAI
/login anthropic  # añade API key Anthropic
```

---

## Salir de BAGO

| Método | Comportamiento |
|--------|----------------|
| `/exit` | Salida limpia |
| `Ctrl+C` × 1 | Aviso: "Para copiar usa clic derecho" |
| `Ctrl+C` × 2 | Aviso: "Una pulsación más para salir" |
| `Ctrl+C` × 3 | Salida: "Saliendo de BAGO..." |
| `Ctrl+D` (EOF) | Salida inmediata |

> **¿Por qué 3×Ctrl+C?** En terminales Windows, Ctrl+C interrumpe texto seleccionado.  
> BAGO protege contra salidas accidentales con el `CtrlCGuard`.

---

## Modos de routing disponibles

| Modo | Activación | Descripción |
|------|-----------|-------------|
| `AUTO` | Default | BAGO elige motor + estrategia automáticamente |
| `MANUAL` | `/autoroute off` o `/switch <modelo>` | El usuario controla el motor |
| `CHAIN` | `/chain m1->m2: prompt` | Pipeline: m1 genera, m2 refina |
| `ENSEMBLE` | `/ensemble m1 m2: prompt` | Paralelo: varios motores, BAGO sintetiza |
| `AUTÓNOMO` | `/auto` | BAGO actúa sin confirmaciones (requiere `/auto` primero) |

---

## Ver también

- [`docs/SLASH_MENU.md`](./SLASH_MENU.md) — Manual completo del menú `/`
- [`docs/COMMANDS.md`](./COMMANDS.md) — Referencia de todos los comandos BAGO
- [`docs/LAYERS.md`](./LAYERS.md) — Arquitectura de capas del framework

---

*Auto-documentado · BAGO framework · A.M. TECHNOLOGIES*
