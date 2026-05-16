# `bago launch` — Manual de Usuario

> **BAGO CLI — A.M. TECHNOLOGIES**  
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
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░█░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░█████████████████████░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░█▓▓▓▓▓████████████████▓▓▓▓▓██░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░██████▓▓▓▓▓████████████▓▓▓▓▓███████░░░░░░░░░░░░░
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
░░░███████████████████▓▓▓▓▓▓▓██▓▓▓▓▓▓▓████████████████████░░░
░░░████████████████████▓▓▓▓▓▓▓▓▓▓▓▓▓▓█████████████████████░░░
░░░░███████████████████▓▓██▓▓▓▓▓▓██▓▓████████████████████░░░░
░░░░████████████████████▓▓██▓▓▓▓██▓▓█████████████████████░░░░
░░░░░███████████████████▓▓▓██▓▓██▓▓▓████████████████████░░░░░
░░░░░░██████████████████▓▓▓██████▓▓▓███████████████████░░░░░░
░░░░░░░░█████████████████▓▓▓████▓▓▓██████████████████░░░░░░░░
░░░░░░░░░█████████████████▓▓▓██▓▓▓██████████████████░░░░░░░░░
░░░░░░░░░░░████████████████▓▓▓▓▓▓█████████████████░░░░░░░░░░░
░░░░░░░░░░░░░███████████████▓▓▓▓████████████████░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░████████████▓▓▓▓█████████████░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░█████████▓▓██████████░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░█░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

              ██████╗  █████╗  ██████╗  ██████╗
              ██╔══██╗██╔══██╗██╔════╝ ██╔═══██╗
              ██████╔╝███████║██║  ███╗██║   ██║
              ██╔══██╗██╔══██║██║   ██║██║   ██║
              ██████╔╝██║  ██║╚██████╔╝╚██████╔╝
              ╚═════╝ ╚═╝  ╚═╝ ╚═════╝  ╚═════╝

              ✔  INICIANDO DESDE EL DISPOSITIVO BAGO...
```

El spinner gira hasta **10 segundos** mientras se cargan providers y credenciales.

---

### 2 · Banner principal

Tras el splash aparece el **banner de sesión**:

```
╭──────────────────────────────────────────────────────────────────────────────╮
│ BAGO CLI  v3.3.0  ·  A.M. TECHNOLOGIES                                      │
│ Motor: qwen25-coder (ollama-local)                                           │
│ Providers: copilot  codex  ollama-local  ollama-cloud                       │
│                                                                              │
│ Modo: ESTÁNDAR   AUTONOMO: OFF   PLAN: OFF   BRAINSTORM: OFF                │
│ Routing: AUTO → qwen25-coder / ollama-local  "inicio de sesión"             │
│ Escalado automático: local → local-grande → cloud                           │
╰──────────────────────────────────────────────────────────────────────────────╯
  /  menú
```

#### Anatomía del banner

```
╭──────────────────────────────────────────────────────────────────────────────╮
│ BAGO CLI  v3.3.0  ·  A.M. TECHNOLOGIES                   ← Versión + marca  │
│                                                                              │
│ Motor: qwen25-coder (ollama-local)                        ← Motor interno    │
│        │              │                                                      │
│        │              └─ Provider activo                                     │
│        └─ Modelo subyacente (trabajador de BAGO, nunca expuesto al usuario)  │
│                                                                              │
│ Providers: copilot  codex  ollama-local  ollama-cloud     ← Estado conexión  │
│            verde=activo    rojo=sin credenciales                             │
│                                                                              │
│ Modo: ESTÁNDAR  AUTONOMO: OFF  PLAN: OFF  BRAINSTORM: OFF ← Modos activos    │
│                                                                              │
│ Routing: AUTO → qwen25-coder / ollama-local               ← Traza decisión  │
│          │      │               │                                            │
│          │      │               └─ Provider elegido                          │
│          │      └─ Modelo elegido                                            │
│          └─ Estrategia: AUTO / CHAIN / ENSEMBLE / MANUAL                    │
│                                                                              │
│ Escalado automático: local → local-grande → cloud         ← Política escape  │
╰──────────────────────────────────────────────────────────────────────────────╯
  /  menú                                                   ← Acceso al menú
```

**Modos:**
| Modo | Activación | Descripción |
|------|-----------|-------------|
| `ESTÁNDAR` | default | Balance calidad/coste |
| `AUTÓNOMO` | `/auto` | Sin confirmaciones |
| `PLAN` | `/plan` | Razona y propone antes de actuar |
| `BRAINSTORM` | `/brainstorm` | Expande ideas sin restricciones |

**Providers** (colores):
| Color | Estado |
|-------|--------|
| 🟢 Verde | Provider activo con credenciales válidas |
| 🔴 Rojo | Sin credenciales / no disponible |

**Routing trace:** muestra la última decisión de BAGO — estrategia + modelo elegido + motivo.

---

### 3 · Barras de contexto + REPL

```
  C:\...\BAGO                              BAGO  ·  C:\Users\...\BAGO
[BAGO|AUTO] > _
──────────────────────────────────────────────────────────────────────
```

| Zona | Descripción |
|------|-------------|
| **Barra superior izquierda** | Ruta del framework BAGO |
| **Barra superior derecha** | Nombre + ruta del proyecto activo (cwd) |
| **Prompt** `[BAGO\|modo]` | Indicador del modo de routing |
| **Barra inferior** `─────` | Separador visual bajo la zona de escritura |

#### Anatomía del prompt

```
[BAGO|AUTO] >
  │     │
  │     └─ Modo de routing actual:
  │          AUTO      = BAGO elige motor automáticamente
  │          MANUAL    = modelo fijo por el usuario (/switch)
  │          CHAIN     = pipeline secuencial activo
  │          ENSEMBLE  = paralelo multi-modelo
  │          AUTO:A    = auto + modo autónomo activo
  │
  └─ Siempre "BAGO" — el usuario habla con el orquestador
```

---

## Flujo de una conversación

```
[BAGO|AUTO] > ¿Cómo optimizo esta función Python?

  → Deduce: tarea de código
  → Selecciona: qwen2.5-coder (ollama-local)
  → Estrategia: SINGLE

╭─ BAGO  vía qwen2.5-coder/ollama-local ──────────────────────────╮
│                                                                  │
│  Para optimizar la función, considera:                           │
│  1. Usa list comprehensions en lugar de bucles for...            │
│  ...                                                             │
│                                                                  │
╰──────────────────────────────────────────────────────────────────╯
```

La respuesta aparece siempre bajo el título `BAGO` con el motor en texto dim.

---

## Escalado automático de contexto

```
local (pequeño)
    ↓  contexto saturado
local (más grande)
    ↓  local agotado
cloud (mejor para la tarea deducida)
```

| Fase | Lógica |
|------|--------|
| **Fase 1** | Busca modelo más grande en Ollama local (7b→14b→32b…) |
| **Fase 2** | Deduce el mejor cloud según la tarea y salta a él |

---

## Opciones de arranque

| Flag | Descripción | Ejemplo |
|------|-------------|---------|
| `--provider <p>` | Fuerza un provider específico | `--provider ollama` |
| `--model <m>` | Usa un modelo concreto | `--model qwen2.5:14b` |
| `--task <t>` | Pre-ruta por tipo de tarea | `--task "revisar código"` |

---

## Providers soportados

| Provider | Identificador | Requiere |
|----------|--------------|---------|
| Ollama Local | `ollama-local` | Ollama corriendo |
| Ollama Cloud | `ollama-cloud` | URL + key |
| GitHub Copilot | `copilot` | `gh auth login` |
| OpenAI / Codex | `codex` | `OPENAI_API_KEY` |
| Anthropic | `anthropic` | `ANTHROPIC_API_KEY` |

---

## Salir de BAGO

| Método | Comportamiento |
|--------|----------------|
| `/exit` | Salida limpia |
| `Ctrl+C` × 1 | "Para copiar usa clic derecho" |
| `Ctrl+C` × 2 | "Una pulsación más para salir" |
| `Ctrl+C` × 3 | "Saliendo de BAGO..." |
| `Ctrl+D` (EOF) | Salida inmediata |

---

## Ver también

- [`docs/SLASH_MENU.md`](./SLASH_MENU.md) — Manual completo del menú `/`
- [`docs/COMMANDS.md`](./COMMANDS.md) — Referencia de todos los comandos BAGO
- [`docs/LAYERS.md`](./LAYERS.md) — Arquitectura de capas del framework

---

*Auto-documentado · BAGO CLI · A.M. TECHNOLOGIES*