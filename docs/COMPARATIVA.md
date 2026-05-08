# BAGO vs Alternativas

> BAGO no compite directamente con ninguna herramienta existente.  
> Ocupa una capa que las demás dan por resuelta (y no lo está).

---

## La capa que nadie cubre

Las herramientas existentes operan en dos capas:

- **Capa de generación:** los agentes IA (Copilot, Claude, GPT). Excelentes generando código, malos manteniendo contexto.
- **Capa de gestión de proyectos:** Jira, Linear, Notion. Excelentes organizando trabajo humano, invisibles para los agentes.

**Entre estas dos capas hay un vacío:** nadie gestiona el estado operacional de la sesión AI, los protocolos de trabajo, la trazabilidad de decisiones ni la verificabilidad del estado.

BAGO ocupa ese vacío.

```
┌─────────────────────────────────────┐
│     Gestión de proyecto (Jira...)   │  ← visible para humanos
├─────────────────────────────────────┤
│     BAGO (capa operacional)         │  ← visible para agentes y humanos
├─────────────────────────────────────┤
│     Agente IA (Copilot, Claude...)  │  ← genera código
└─────────────────────────────────────┘
```

---

## BAGO vs Agente IA sin framework

| Dimensión | Bare AI agent | BAGO + agente |
|-----------|:---:|:---:|
| Contexto entre sesiones | ❌ | ✅ |
| Protocolo de trabajo definido | ❌ | ✅ |
| Decisiones auditables | ❌ | ✅ |
| Verificación del estado declarado | ❌ | ✅ |
| Detección de stale tasks | ❌ | ✅ |
| Múltiples agentes coordinados | ❌ | ✅ |
| Medición de salud del sistema | ❌ | ✅ |

Un agente sin framework es potente pero **amnésico y sin gobernanza**. BAGO le da memoria, estructura y trazabilidad.

---

## BAGO vs Gestores de tareas (Jira, Linear, GitHub Issues)

| Dimensión | Jira / Linear / Issues | BAGO |
|-----------|:---:|:---:|
| Visible para el agente IA | ❌ | ✅ |
| Estado cargado automáticamente al inicio de sesión | ❌ | ✅ |
| Protocolos de trabajo accionables | ❌ | ✅ |
| Artefactos de cambio inmutables | ❌ | ✅ |
| Verificación de consistencia automática | ❌ | ✅ |
| Sin dependencias ni SaaS externo | ✅ | ✅ |
| Integración con revisión de PR | ✅ | ⚠️ parcial |
| Tableros visuales | ✅ | ❌ |

Los gestores de tareas son **para humanos que coordinan trabajo**. BAGO es **para agentes que ejecutan trabajo bajo supervisión humana**. Son complementarios, no excluyentes.

---

## BAGO vs Task runners (Make, npm scripts, Taskfile)

| Dimensión | Make / npm scripts | BAGO |
|-----------|:---:|:---:|
| Automatización de comandos | ✅ | ⚠️ parcial |
| Estado persistente entre ejecuciones | ❌ | ✅ |
| Protocolos de trabajo estructurados | ❌ | ✅ |
| Health score del sistema | ❌ | ✅ |
| Contexto de sesión IA | ❌ | ✅ |
| Sin dependencias externas | ✅ | ✅ |

Los task runners ejecutan comandos. BAGO **estructura cómo y cuándo se ejecutan**, y registra qué pasó.

---

## BAGO vs Soluciones de memoria para IA (MemGPT, mem0, Zep)

| Dimensión | MemGPT / mem0 | BAGO |
|-----------|:---:|:---:|
| Memoria de conversación | ✅ | ⚠️ a nivel de sesión |
| Memoria de estado del proyecto | ❌ | ✅ |
| Protocolos de trabajo | ❌ | ✅ |
| Sin dependencias / sin nube | ❌ | ✅ |
| Trazabilidad auditable | ❌ | ✅ |
| Instalación en cualquier repo | ⚠️ compleja | ✅ sencilla |
| Agnóstico al agente IA | ⚠️ | ✅ |

Las soluciones de memoria se enfocan en **recordar conversaciones**. BAGO se enfoca en **estructurar y auditar el trabajo técnico**. Pueden coexistir.

---

## BAGO vs Cursor / Windsurf Rules (`.cursorrules`, `.windsurfrules`)

| Dimensión | .cursorrules | BAGO |
|-----------|:---:|:---:|
| Define cómo trabaja el agente | ✅ | ✅ |
| Estado persistente entre sesiones | ❌ | ✅ |
| Workflows accionables | ❌ | ✅ |
| Trazabilidad de cambios | ❌ | ✅ |
| CLI propia | ❌ | ✅ |
| Medición de salud | ❌ | ✅ |
| Multiplataforma / multi-IDE | ❌ | ✅ |

Los ficheros de reglas de IDE son un primer paso correcto pero **estáticos y sin estado**. BAGO es la versión operacional completa.

---

## Tabla de posicionamiento

```
                         Alta estructura
                              │
           BAGO ──────────────┼── Jira / Linear
          (técnica,           │   (humana,
           para agentes)      │    para equipos)
                              │
──────────────────────────────┼──────────────────── Para equipos
                              │
     .cursorrules             │   GitHub Issues
     MemGPT                   │
                              │
                         Baja estructura
```

BAGO es la única herramienta en el cuadrante **alta estructura + orientada a agentes IA técnicos**.

---

## Cuándo NO usar BAGO

- Para proyectos de un solo script de menos de 100 líneas: overkill.
- Como sustituto de un gestor de proyectos para equipos grandes no técnicos: BAGO no tiene UI.
- Como reemplazo de CI/CD: BAGO audita, no despliega.

---

*BAGO v3.3.0 · Mayo 2026*
