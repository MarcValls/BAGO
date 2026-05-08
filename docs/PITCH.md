# BAGO — Propuesta de Valor

> **BAGO** (Balanceado · Adaptativo · Generativo · Organizativo)  
> Capa operacional persistente para trabajo técnico asistido por IA.

---

## El problema

El trabajo con agentes de IA tiene cuatro grietas estructurales:

| Grieta | Impacto real |
|--------|-------------|
| **Pérdida de contexto entre sesiones** | El agente vuelve a empezar desde cero cada vez |
| **Arranques improvisados** | Sin rol, sin protocolo, sin estado previo |
| **Cambios sin rastro** | Decisiones y decisiones tomadas que desaparecen |
| **Derive entre estado declarado y realidad** | El agente cree que algo está hecho y no lo está |

Estos problemas no los resuelve ningún agente por sí solo. Son problemas de capa de operación, no de capacidad de generación.

---

## La solución

BAGO es una **capa operacional persistente** que vive dentro del repositorio y trabaja junto a cualquier agente de IA (GitHub Copilot, Claude, GPT).

```
Desarrollador ──► BAGO CLI ──► Agente IA
                     │              │
                     ▼              ▼
               .bago/state     .bago/core
               (persiste)     (protocolos)
```

BAGO **no es** un agente. Es el sistema operativo debajo de cualquier agente.

---

## Propuesta de valor única

### 1. Contexto que sobrevive entre sesiones
El estado se persiste en `.bago/state/`. Cuando el agente arranca, ya sabe en qué fase estás, qué decisiones se tomaron y qué está pendiente.

### 2. Workflows estructurados para cualquier tipo de tarea
11 protocolos de trabajo (W0–W10) con precondiciones, pasos, artefactos y criterios de salida definidos. El agente no improvisa: ejecuta un protocolo.

### 3. Trazabilidad automática de cambios
Cada cambio significativo genera un artefacto `BAGO-CHG` con evidencia adjunta. El historial es inmutable y consultable.

### 4. Salud del sistema medible
`bago health` devuelve un score 0–100 basado en 5 dimensiones: integridad, uso de workflows, decisiones capturadas, tareas sin stale e inventario consistente.

### 5. Auditoría de sinceridad
`bago health sincerity` detecta afirmaciones no verificadas en la documentación. Evita el "cargo-cult documentation".

---

## Métricas de tracción

BAGO se ha construido usando BAGO. Los datos que siguen son reales, capturados con `bago efficiency` en cada release:

| Versión | Comandos CLI | Tools | Docs | Workflows | Índice de Eficiencia |
|---------|:---:|:---:|:---:|:---:|:---:|
| **2.3-clean** *(baseline)* | 10 | 19 | 68 | 12 | 78.6 |
| **2.4-v2rc** | 10 | 27 | 73 | 12 | 89.3 |
| **2.5-stable** | 35 | 111 | 77 | 20 | 100.0 |
| **2.6-taxonomy** | 51 | 177 | 278 | 8 | 100.0 |
| **3.3.0** *(actual)* | **54** | **218** | — | **11** | **100.0** |

**Crecimiento 2.3 → 3.3.0:** ×5 comandos · ×11 tools · ×4 docs

### CI en producción
8 gates activos. Ninguno acepta fallos (`continue-on-error: false`):

```
gate-registry  ✅  gate-syntax   ✅  gate-security  ✅  gate-tests    ✅
gate-package   ✅  gate-validate ✅  gate-docs      ✅  gate-wheel    ✅
```

48 tests pasando. 0 fallos. 1 xfail esperado.

### Caso de uso real: proyecto DERIVA
Un videojuego cyberpunk point-and-click construido íntegramente bajo BAGO en 21 fases:
- 458 tests pasando (contracts + engine + ui-runtime)
- 0 errores TypeScript en producción
- 7/7 endings simulados y verificados
- PWA publicable — build 309 kB gzip:92 kB

> Ver [`CASO_DE_USO_DERIVA.md`](CASO_DE_USO_DERIVA.md) para el análisis completo.

---

## Diferenciación

| Dimensión | Sin BAGO | Con BAGO |
|-----------|---------|---------|
| Contexto entre sesiones | ❌ Perdido | ✅ Persistido en `.bago/state/` |
| Protocolo de trabajo | ❌ Ad hoc | ✅ Workflow W0–W10 |
| Trazabilidad | ❌ Ninguna | ✅ BAGO-CHG + evidencia |
| Verificabilidad del estado | ❌ Confianza ciega | ✅ `bago validate` + `bago health` |
| Auditoría de decisiones | ❌ Imposible | ✅ `bago audit full` |
| Escalado a múltiples agentes | ❌ Caótico | ✅ `bago cabinet` (multi-agente) |

BAGO no compite con los agentes. Los potencia.

---

## Modelo de adopción

**Fase 1 — Individual:** Un desarrollador instala BAGO en su repositorio. Costo: 0. Dependencias: ninguna (Python stdlib).

**Fase 2 — Equipo:** Múltiples agentes coordinados via `bago cabinet`. Estado compartido.

**Fase 3 — Organización:** Biblioteca de workflows propios, memoria distribuida por proyecto (`bago project`), métricas de eficiencia agregadas.

---

## Potencial de mercado

El mercado de herramientas para desarrollo asistido por IA crece a un ritmo que ninguna herramienta de tipo "wrapper de LLM" puede capturar a largo plazo. BAGO apunta a la capa de infraestructura: **la que convierte un agente potente pero amnésico en un colaborador estructurado y auditable.**

El diferencial no es la generación. Es la **gobernanza**.

---

## Roadmap de producto

Ver [`HOJA_DE_RUTA.md`](HOJA_DE_RUTA.md) para el detalle por fase.

**En síntesis:**
- **v4.0** — Distribución `pip install bago` sin instalación editable
- **v5.0** — PADRE/SIEMBRA: separación limpia framework/proyecto + seed mechanism
- **Horizonte** — Sincronización cloud + marketplace de workflows

---

## Stack técnico

- **Lenguaje:** Python 3.9+ (sin dependencias externas)
- **Instalación:** `pip install -e .` o alias directo
- **Compatibilidad:** macOS · Linux · Windows (parcial)
- **Agentes compatibles:** GitHub Copilot, Claude, GPT-4+, cualquier agente con acceso a CLI
- **Licencia:** MIT

---

*BAGO v3.3.0 · Mayo 2026 · github.com/MarcValls/BAGO*
