# Caso de uso: Proyecto DERIVA bajo BAGO

> **DERIVA** es un videojuego cyberpunk point-and-click construido íntegramente  
> con asistencia IA y gobernado en todas sus fases por BAGO.

---

## Resumen ejecutivo

| Métrica | Valor |
|---------|-------|
| Fases completadas | 21 |
| Tests en producción | 458 (15 contracts + 43 engine + 400 ui-runtime) |
| Errores TypeScript | 0 |
| Build final | 309.63 kB · gzip 92.46 kB |
| Endings simulados | 7/7 verificados |
| Duración suite de simulación | 11 ms |
| PWA | Sí — service worker cache-first |
| Agentes BAGO involucrados | 3 (bug fix multiagente, fase 10) |

---

## El reto

DERIVA es un proyecto de complejidad real:
- Monorepo TypeScript con `pnpm workspaces` (5 packages + 1 app)
- Stack: TypeScript 5.6.3 + Vite 6 + React 18 + Canvas 2D + Zod 3.24.1
- Sistema de combate por turnos estilo Pokémon con IA de enemigos
- Sistema narrativo FATE con diálogos ramificados
- Renderer isométrico (BiancaIsoRenderer como adaptador de IRenderer)
- Internacionalización completa (150+ claves ES)
- PWA con Service Worker

Un proyecto de esta envergadura, asistido por IA sin un sistema de gobernanza, acumula deuda técnica invisible, estados divergentes y regresiones no detectadas.

---

## Cómo BAGO gobernó el proyecto

### Estado persistente entre sesiones

Cada sesión arrancaba con el estado completo cargado desde `.bago/state/global_state.json`:
- Fase activa y sprint en curso
- Decisiones congeladas (stack, renderer, contratos)
- Build status y conteo de tests
- Items pendientes con estado actualizado

El agente nunca empezaba desde cero. El contexto estaba siempre disponible.

### Decisiones congeladas (frozen decisions)

Las decisiones arquitectónicas irreversibles se registraron como frozen decisions:

```json
"frozen_decisions": [
  "stack: TypeScript 5.6.3 + Vite 6 + React 18 + Canvas 2D",
  "monorepo: pnpm workspaces",
  "contracts: Zod 3.24.1",
  "renderer: BiancaIsoRenderer as IRenderer adapter",
  "engine_base: motor_hexen_ts_engine_hexenlike_v1_1",
  "destination: /Volumes/Warehouse/AMTEC/DERIVA/"
]
```

Ningún agente podía sugerir ni implementar cambios que contradijesen estas decisiones sin revisión explícita.

### Trazabilidad de fases

Cada fase completada quedó registrada con:
- Feature implementada
- Estado del build (GREEN/RED)
- Errores TypeScript antes/después
- Tests añadidos
- Ficheros modificados
- Hallazgos de auditoría

Ejemplo — Phase 21 (Act 2 enemies):

```
Feature: guardia_temporal + drone_datos + constructo_ia
Build: GREEN — 0 TypeScript errors
Tests: 458/458 PASS (antes: 446)
Tests nuevos: 12 (T_ACT2_01..12)
Ficheros: 5 modificados
```

### Bug fix multiagente (Fase 10)

La fase 10 resolvió 4 bugs en el flujo "Nueva Partida" utilizando **3 agentes BAGO en paralelo**. Cada agente investigó un subsistema distinto bajo el mismo estado de sesión compartido. Los resultados se integraron sin conflicto gracias al protocolo de cambio BAGO.

### Suite de simulación

Se desarrolló `tools/simulate_all_endings.ts` para verificar los 7 endings del juego de forma determinista:

```
Total: 8 simulaciones
Pass:  8 / 8
Fail:  0
Duración: 11 ms

player_won       ✓
enemy_won        ✓
fled             ✓
HOTSPOT_ACTIVATED    ✓
HOTSPOT_MISSING_ITEM ✓
HOTSPOT_LOCKED       ✓
DIALOGUE_STARTED     ✓
```

RNG determinista via `withRNG()`. IRenderer y ICollisionBackend mockeados. localStorage mockeado en globalThis.

---

## Evolución del proyecto por fases

| Fase | Contenido | Build |
|------|-----------|-------|
| 0–2 | Estructura monorepo + contratos Zod | 🟢 |
| 3–5 | Engine, renderer isométrico, sistema narrativo FATE | 🟢 |
| 6–7 | App de juego + contenido Act 1 (3 mapas, 3 diálogos) | 🟢 |
| 8–9 | Save/Load, Act 2 stub, QA automatizado | 🟢 |
| 10 | Bug fix multiagente — Nueva Partida reparada | 🟢 |
| 11 | Click-to-move + combate por turnos | 🟢 |
| 12–13 | Tooling: Collision Editor, Frame Editor, Sprite Sequence Builder | 🟢 |
| 14 | Game design mechanics + BattleEngine v2 (Moves/PP/Status/Speed/IA) | 🟢 |
| 15–16 | Visual upgrade: sprites Bianca + fondos contextual | 🟢 |
| 17–18 | Spritesheets animados pixel art + SpriteAnimator por entidad | 🟢 |
| 19–20 | Bug fix coordenadas ratón + IntroCodex SVG JSX | 🟢 |
| 21 | Act 2 enemies: 3 tipos, 12 tests, mobs en mapas | 🟢 |

21 fases completadas. **0 regresiones no detectadas.**

---

## Lecciones extraídas

### 1. El estado persistente elimina el "¿dónde estábamos?"
En ninguna sesión se perdió tiempo reconstruyendo contexto. El agente arrancaba con la fase activa, el sprint, las decisiones congeladas y los pendientes ya cargados.

### 2. Las decisiones congeladas previenen la deriva
Sin el mecanismo de frozen decisions, los agentes tendían a proponer alternativas de stack en cada sesión. Con él, esas propuestas no llegaban a formularse.

### 3. La auditoría de sinceridad evita el estado optimista
`bago health sincerity` detectó en varias sesiones items marcados como DONE en el estado que en realidad no habían sido verificados. Se corrigieron antes de que se convirtieran en deuda técnica invisible.

### 4. Los workflows estructuran la incertidumbre
Las fases de bug fix (W4) y las de features nuevas (W2) seguían protocolos distintos. Esto redujo el tiempo de diagnóstico y evitó confundir síntomas con causas.

### 5. La suite de simulación es el contrato de calidad final
Tener 7/7 endings simulados en 11 ms proporciona una red de seguridad que ninguna revisión manual puede igualar en velocidad.

---

## Configuración BAGO usada en DERIVA

```json
{
  "mode": "Generativo",
  "active_project": "DERIVA",
  "active_workflows": [
    "monorepo_build",
    "game_content_pipeline",
    "simulation_testing"
  ],
  "active_roles": [
    "engineer",
    "game_designer",
    "content_author",
    "tester"
  ]
}
```

---

*Caso de uso registrado en BAGO state · Mayo 2026*
