# BAGO — Historia Completa desde el Principio
_Generado: 2026-05-13 | Excavación profunda: discos + GitHub + sesiones_
_Cobertura: ~2 años de trabajo · desde mediados 2023 hasta mayo 2026_

---

## 📅 LÍNEA TEMPORAL COMPLETA

### ERA 0 — Prehistoria (Mid-2023 / Sep-Dic 2023)
**Warehouse/2023_MEDIADOS, I_SEPTIEMBRE_2023, J_OCTUBRE_2023, L_DICIEMBRE_2023**

- Actividad principal: **producción musical** (colección y edición de tracks)
- No hay proyectos de software registrados todavía
- Periodo de gestación antes del primer código
- Herramienta: ningún BAGO — trabajo manual sin framework

---

### ERA 1 — Primeros proyectos (2024)
**Warehouse/2024/A_ENERO → L_DICIEMBRE_2024**

- 2024 es principalmente **música** en archivo (por meses)
- **Mayo 2024**: primer registro de BAGO como sistema
  - `BAGOv4_Roles_Activos_Capas.csv` tiene fecha de creación `2024-05-23`
  - Los roles v4 originales (Maestro, Fábrica de Roles, etc.) se crean en esta fecha
  - BAGO nace como sistema de **gobernanza por roles** para ChatGPT
- Primeros roles v4 (14 roles, 5 capas):
  - **Capa 0**: BIOS, Watchdog Absoluto, Monitor de Recursos
  - **Capa 1**: Heartbeat, Limpieza Básica, Monitor Energía
  - **Capa 2**: Maestro, Disco Duro, Logging Centralizado, Llave Maestra, Pool Data, Memoria Caché
  - **Capa 3**: Empresa de Limpieza, Auditor de Integridad, Fábrica de Roles, Notificador, Integrador Externo
  - **Capa 4**: Aprendizaje Adaptativo, IA Exploratoria
- BAGO en esta era = **sistema de instrucciones para ChatGPT**, no CLI

---

### ERA 2 — Primeros productos web (Jun-Oct 2025)
**GitHub: INTELIA_Manager, app, vamosintelia, TallerGestion, INTELIAwarehouseMANAGER**

| Fecha | Proyecto | Stack | Estado |
|-------|----------|-------|--------|
| Jun 2025 | INTELIA_Manager | Flask backend + README | Primer proyecto serio |
| Jun 2025 | INTELIA_Manager_FINAL | — | Iteración |
| Jun 2025 | app (vamosintelia) | — | Testing IA agents |
| Jun 2025 | vamosintelia | Prompt maestro + 5 roles AI-testing | Template para testing |
| Ago 2025 | TallerGestion / TallerGestionOK | — | Gestión taller |
| Sep 2025 | INTELIAwarehouseMANAGER | React + inventario | Gestor almacén |
| Sep-Oct 2025 | catavic-vite, INTELIA_Catavic, INTELIA_FUSION_V3 | Vite+React | Variantes INTELIA |

**Stack INTELIA original** (Warehouse/ESCRITORIO/gestor_INTELIA):
- Backend: Flask Python / FastAPI
- Frontend: React/Vite
- DB: SQL Server → SQLite
- Requisito: Docker SQL Server 2022

**Lección de era**: Múltiples intentos de un mismo producto (gestor comercial INTELIA) — patrón de fracaso por reescritura en lugar de evolución incremental.

---

### ERA 3 — Genemaps y primeros datos complejos (Oct-Dic 2025)
**GitHub: Genemaps, genemapsv1repair, Genemaps_Regular_roots_genetics**

| Fecha | Repo | Descripción |
|-------|------|-------------|
| Oct 2025 | Genemaps | Mapas genéticos cannabis — primera versión |
| Nov 2025 | genemapsv1repair | Reparación v1 (activo hasta Feb 2026) |
| Dic 2025 | Genemaps_Regular_roots_genetics | BS4+Playwright+FastAPI+SQLite |

**Stack Genemaps final**: BeautifulSoup4 + Playwright + FastAPI + SQLite
Buscador y creador de árboles genealógicos de cannabis usando datos web scraping.

**Dic 2025**: TPV_Contabilidad empieza (Node.js fullstack), `bago_demo_full_v6` sube a GitHub.

**`bago_demo_full_v6`** — primer BAGO demo completo público en GitHub (Nov 2025)

---

### ERA 4 — Motor isométrico Python + iso_rpg (Ene-Feb 2026)
**Warehouse/AMTEC/apps/amtec-iso, AMTEC iso_rpg Kivy**

- **Enero 2026**: `MOTOR_ESTRUCTURA_Y_CODIGO_ADAPTADO.md` generado 2026-01-26
- Motor isométrico data-driven con:
  - **`engine/`** — UI Runtime + Pack Loader (Kivy)
  - **`src/`** — ECS + WorldState + IsoRenderer
  - **`games/amtec_bago/`** — contenido data-driven (packs, diálogos, mapas JSON)
- Comandos: `python3 main.py --game amtec_bago`
- Tests: pytest (`test_loop`, `test_ecs`, `test_mvp_loop`)
- Buildozer para Android (Kivy)

**Lección clave** (de esta era): Arquitectura ECS data-driven desde el principio = contenido separado del engine. "Si se puede resolver en `games/`, no parchear `src/`."

---

### ERA 5 — AMTEC Metroidvania + Motor TS (Ago 2025 → Feb 2026)
**Warehouse/ESCRITORIO/ROLES_JUEGO, ENGINE V0 BETA, BAGO_AMTEC ecosystem**

- **Agosto 2025**: Documento `bago_amtec_ecosistema_metroidvania_rpg_js_python_activado.md`
  - Fecha explícita: **26/08/2025**
  - BAGO ya tiene roles de juego: Diseñador Mecánicas, Programador 2D, IA Enemigos, Audio
  - Stack: JS (Phaser 3 + Vite, PWA) + Python (Tkinter prototipos)
  - Roadmap: Sprint 0-3 (player, habilidades, enemigos)

- **ENGINE V0 BETA**: `motor_hexen_ts_engine_hexenlike_v1_1`
  - Monorepo TypeScript (contracts, engine, ui-runtime, player, validator-cli)
  - `npm run build` → OK ✅
  - Precursor directo de DERIVA

- **Auditoría motores (2026-04-12)**: 147 ZIPs revisados, 12 `ENGINE_LIKELY`, 4 ejecutables confirmados

---

### ERA 6 — BAGO v2 (AMTEC Canon) + PANEL_ORQUESTADOR (Mar-Abr 2026)
**GitHub: PANEL_ORQUESTADOR, INTELIA_Manager_TPV, MYTHOS, microhorror**

| Fecha | Proyecto | Hito |
|-------|----------|------|
| Mar 2026 | MYTHOS_DESDE_PLAN_01 | — |
| Mar 2026 | PANEL_ORQUESTADOR | TypeScript/Electron + React 19 + Zustand + TanStack |
| Mar 2026 | microhorror-mvp | Godot GDScript horror |
| Mar 2026 | AMTEC_microterror | Godot GDScript horror v2 |
| Mar-Abr 2026 | INTELIA_Manager_TPV | POS fullstack |
| Abr 2026 | INTELIA_Manager_TPV_V0.1.0 | Sprint 1-9, tag v0.1.0, 667 tests green |

**PANEL_ORQUESTADOR stack**:
- Vite + React 19 + TypeScript + React Router + Zustand + TanStack Query
- Electron para desktop (terminal-agent embebido)
- Propósito: revisar arquitecturas, tareas y ejecuciones desde panel visual

**TPV_Contabilidad — hitos**:
- Sprint 1-5: PurchaseOrders, ReceivingIntakes, Approvals, ShippingManifests, RMA, PriceLists
- 667 tests green, cobertura backend >85%, frontend >80%
- Stack: Bull.js + Redis para job queues
- `pnpm migrate:db:dry-run` siempre antes de migraciones

**BAGO v2.2.1 (2026-04-11)**:
- `baseline_bago_amtec_2_2_1_oficial` — frozen reference
- Primera integración real de **repo-first**
- Mapa del sistema: Usuario → AGENT_START → workflow_bootstrap_repo_first → ADAPTADOR_PROYECTO → MAESTRO_BAGO → ORQUESTADOR_CENTRAL → WORKFLOW → ROLES → VALIDADOR → ESTADO

---

### ERA 7 — BAGO v2.2.2 + Pandamien + BIANCA (Abr 2026)
**GitHub: BIANCA_THE_GAME, Pandamien_Doc_Dev_amTech | Warehouse: AMTEC/BIANCA_MASTER**

**BAGO v2.2.2 (2026-04-14)**:
- Hardening: validación detecta deriva de versión, workflows no declarados, estado inconsistente
- `github_models`: backoff + rate limiting (0.5-1.0 rps) — sin limitador → 429 masivos
- 5 decisiones canónicas (DEC-001 a DEC-005)

**Pandamien (terminado 2026-04-14)**:
- 77 BLGs (Bloques de Contenido) generados
- Fases F00-F05 completadas
- `lifecycle_status: "done"` — proyecto finalizado
- BAGO v2.2.2 como herramienta operativa

**BIANCA The Game (desde Abr 2026)**:
- Narrativa: "BIANCA, La Tejedora de Universos"
- Mundos: Torre Babel, Bosque Inconclusas, Llanuras Párrafo, Página en Blanco
- 47 FX visuales + 9 SFX (sin conectar al inicio)
- Sprint 197-287+
- ISO_GAME engine (isométrico Python, pathfinding A*, chunker, autotile)

---

### ERA 8 — BAGO v3.x + bago-framework público (Abr-May 2026)
**GitHub: bago-framework (v2.5), BAGO (v3.3.0) | Warehouse: BAGO_v4_ok, BAGO_rescued**

**bago-framework GitHub (v2.5, publicado 2026-04-20)**:
- Primer BAGO público en GitHub
- 30 tools, 12 workflows, 13 CLI
- README en inglés para comunidad

**BAGO v3.3.0 (2026-05-06 → activo)**:
- 83 CLI tools
- `bago.db` — base de datos de ideas (SQLite)
- `guardian` — sistema de salud automático
- Neural Fabric integrado (SENSE→PLAN→ACT→OBSERVE→LEARN→DECIDE)
- `cosecha.py` — sistema de aprendizaje automático
- `audit_state_pointers.py` — validación de integridad de punteros

**BAGO_rescued (2026-05-06)**:
- Limpieza del disco antes de consolidación
- Material rescatado: CESAR_WOODS docs, TPV state, BAGO kits, DOS MODOS, roles v4
- Pendiente: evaluar `bago_kits` para integrar sistema de kits en v3.0

---

### ERA 9 — DERIVA RPG + Repos temáticos (May 2026)
**GitHub: BAGO_SPRITE_STUDIO, BAGO_NEURAL_FABRIC, BAGO_WALLET_TRACKER, etc.**

**DERIVA RPG (sprint 14, completado)**:
- Monorepo pnpm: TypeScript 5.6.3 + Vite 6 + React 18 + Canvas 2D
- Paquetes: contracts (Zod), engine, renderer-iso, narrative (FATE), ui-runtime
- 458 tests (15 contracts + 43 engine + 400 ui-runtime)
- Features sprint 14: i18n-es, New Game+, Achievements, Debug Overlay, PWA básico

**Repos temáticos publicados (2026-05-11)**:
- BAGO_SPRITE_STUDIO — generador sprites Pillow + HF + Codex
- BAGO_NEURAL_FABRIC — loop SENSE→PLAN→ACT→OBSERVE→LEARN→DECIDE
- BAGO_WALLET_TRACKER — TON read-only, CoinGecko, airdrop scanner
- BAGO_TELEGRAM_BOT — MiniApp, intent detection, inline keyboards
- BAGO_MUSIC_PIPELINE — score pipeline, MIDI, Ableton, Karpovich synth
- BAGO_WINDOWS_AUTOMATION — Win32 mouse, UAC, Task Scheduler
- BIANCA_THE_GAME (ya existía desde Apr)
- ISO_GAME — engine isométrico Python

---

## 🧬 EVOLUCIÓN DEL SISTEMA BAGO

```
2024-05 · BAGO v4 (instrucciones ChatGPT) — 14 roles, 5 capas
    → Sistema de gobernanza por roles para LLMs
    
2025-06 · DOS MODOS: META_BAGO + PROYECTO
    → Separación: trabajar CON BAGO vs trabajar EN BAGO
    
2025-08 · BAGO AMTEC Metroidvania
    → Roles específicos de dominio (juego, audio, IA, narrativa)
    
2025-11 · bago_demo_full_v6 (primer GitHub público)
    → BAGO empieza a ser shareable
    
2026-04 · BAGO v2.2.1 → v2.2.2 (repo-first + hardening)
    → workflow_bootstrap_repo_first: leer repo ANTES que metadocumentación
    → DEC-005: rate limiting github_models
    
2026-04 · bago-framework v2.5 (GitHub público, inglés)
    → 30 tools, 12 workflows, 13 CLI
    → Primer release para comunidad
    
2026-05 · BAGO v3.3.0 (activo)
    → 83 CLI tools, bago.db, guardian, cosecha, audit_state_pointers
    → Neural Fabric integrado
    → 65 ideas en DB, 56 sesiones, 293 checkpoints
```

---

## 🏗️ PROYECTOS POR DOMINIO (inventario histórico)

### Gestión empresarial
| Proyecto | Fecha | Estado |
|----------|-------|--------|
| INTELIA_Manager (Flask) | Jun 2025 | abandonado |
| INTELIA_Manager (SQL Server) | 2025 | abandonado |
| INTELIAwarehouseMANAGER | Sep 2025 | abandonado |
| TallerGestion | Ago 2025 | casi |
| catavic / INTELIA_Catavic | Oct 2025 | varios intentos |
| TPV_Contabilidad v0.1.0 | Mar-Abr 2026 | ✅ sprint 1-9 done |

### Genética / Ciencia
| Proyecto | Fecha | Estado |
|----------|-------|--------|
| Genemaps v1 | Oct 2025 | broken |
| genemapsv1repair | Nov 2025-Feb 2026 | reparado |
| Genemaps_Regular_roots_genetics | Dic 2025 | ✅ funcional |

### Juegos
| Proyecto | Fecha | Stack | Estado |
|----------|-------|-------|--------|
| amtec-iso (Kivy Python) | Ene-Feb 2026 | Python/Kivy/ECS | prototipo |
| microhorror-mvp | Mar 2026 | Godot GDScript | ✅ |
| AMTEC_microterror | Mar 2026 | Godot GDScript | ✅ |
| BIANCA_THE_GAME | Abr 2026 | TypeScript+Phaser+Canvas | 47+ FX |
| ISO_GAME | May 2026 | Python isométrico | ✅ |
| DERIVA RPG | Abr-May 2026 | TypeScript monorepo pnpm | sprint 14 done |
| tragaperras bot (casino) | May 2026 | Python+Telegram MiniApp | ✅ |

### Infraestructura / Herramientas
| Proyecto | Fecha | Stack |
|----------|-------|-------|
| PANEL_ORQUESTADOR | Mar 2026 | Electron+React+TypeScript |
| BAGO_SPRITE_STUDIO | May 2026 | Python Pillow+HF+Codex |
| BAGO_NEURAL_FABRIC | May 2026 | Python dot-product routing |
| BAGO_WALLET_TRACKER | May 2026 | Python TON+CoinGecko |
| BAGO_TELEGRAM_BOT | May 2026 | Python python-telegram-bot |
| BAGO_MUSIC_PIPELINE | May 2026 | Python MIDI+Ableton |
| BAGO_WINDOWS_AUTOMATION | May 2026 | Python Win32 |

---

## 🔑 LECCIONES HISTÓRICAS CROSS-ERA

### Antipatrones identificados (recurrentes)

| ID | Antipatrón | Primera aparición | Impacto |
|----|------------|------------------|---------|
| **AP-001** | Reescritura en lugar de evolución | INTELIA_Manager (v1→final→vamosintelia) | 4 repos abandonados |
| **AP-002** | Sin tests hasta que se rompe | Genemaps v1 → genemapsv1repair | Meses de deuda |
| **AP-003** | Buffer fijo canvas (960×540) | amtec-iso → BIANCA → DERIVA | Bug DPR en 3 proyectos |
| **AP-004** | Audio implementado pero sin wiring | BIANCA AudioManager | 9 SFX mudos |
| **AP-005** | github_models sin rate limit | BAGO AMTEC 2.2.1 | 429 masivos |
| **AP-006** | Frozen decisions obsoletas sin auditar | BIANCA/DERIVA | Bugs invisibles |
| **AP-007** | `ALTER TABLE` en `executescript()` | Casino DB | Crash en producción |
| **AP-008** | SQL dinámico sin whitelist de campos | Casino API | SQL injection |

### Patrones que funcionaron (replicar)

| ID | Patrón | Primera aparición | Impacto |
|----|--------|-----------------|---------|
| **PP-001** | Data-driven content (ECS + packs JSON) | amtec-iso Kivy | Engine reutilizable |
| **PP-002** | Monorepo pnpm + contratos Zod | DERIVA | 458 tests, máxima limpieza |
| **PP-003** | `workflow_bootstrap_repo_first` | BAGO v2.2.1 | Fin de documentación fantasma |
| **PP-004** | `ctx.save()/restore()` para FX | BIANCA sprint 197+ | Cero contaminaciones FX |
| **PP-005** | `setTransform(dpr,0,0,dpr,0,0)` en resize | DERIVA sprint 14 | DPR correcto siempre |
| **PP-006** | Rate limiter `dict[uid,float]+Lock+monotonic` | Casino | 0.8s/uid sin deadlock |
| **PP-007** | `PRAGMA table_info()` antes de `ALTER TABLE` | Casino DB | Migraciones idempotentes |
| **PP-008** | Trust UX sin claims de licencia | Casino MiniApp | Credibilidad honesta |
| **PP-009** | Backoff + `global_rate_limit_rps` | BAGO v2.2.2 DEC-005 | API stables |
| **PP-010** | Sprites sin espejos — cada frame individual | BIANCA | Anatomía correcta |

---

## 📊 MÉTRICAS HISTÓRICAS

| Métrica | Valor |
|---------|-------|
| Primer código en GitHub | Jun 2025 |
| Primer BAGO formal | May 2024 |
| Repos GitHub totales | 35+ |
| Instancias .bago en disco | 14 |
| Tests en proyecto más maduro (DERIVA) | 458 |
| Tests en TPV v0.1.0 | 667 |
| FX visuales en BIANCA | 47+ |
| Ideas en bago.db | 65 |
| Sesiones BAGO registradas | 59 |
| Checkpoints de sesión | 293 |
| Lecciones catalogadas | 130+ |
| Versiones BAGO (v4→v2.2.1→v2.2.2→v2.5→v3.3.0) | 5 hitos |

---

## 🗺️ MAPA DE CONOCIMIENTO DISPONIBLE

| Archivo knowledge | Cubre | Lecciones |
|------------------|-------|-----------|
| `april_2026_arc.md` | Narrativa Abr 2026 (6 proyectos) | Evolución completa v2.2→v2.5 |
| `bago_universe.md` | Master reference (9 agentes, 10 workflows, 221 tools) | Inventario v3 |
| `framework_traps.md` | 13 trampas semánticas (23 Abr) | Antipatrones BAGO |
| `engine_learnings_bianca.md` | Engine BIANCA (47 FX, ECS, BeatTimer) | Canvas 2D avanzado |
| `fx_inventory_bianca.md` | Catálogo completo 47 FX | Code references por sprint |
| `audio_integration_bianca.md` | AudioManager + MIDI + spatial | Wiring patterns |
| `toolkit_bianca.md` | Backends generación sprites (M1-M6) | Pipeline completo |
| `session_arc_bianca.md` | Arc narrativo BIANCA | Diseño de personaje |
| `image_generation_guide.md` | Guía generación imágenes | Sin API key |
| `project_patterns.md` | Patrones cross-proyecto | Reutilizables |
| `auto_patterns.md` | VALIDADOR:quick_check, ORGANIZADOR:summary | Auto-promovidos |
| `casino_miniapp_patterns.md` | 12 patrones casino (RTP, near-miss, DB) | May 2026 |
| `excavation_2026_05_13.md` | 15 lecciones EX-001..015 disco+GitHub | May 2026 |
| **`full_history.md`** (este) | Historia completa 2023→2026 | Meta-conocimiento |

---

_Historia completa documentada: 2026-05-13_
_Fuentes: 14 instancias .bago + 35 repos GitHub + Warehouse AMTEC + archivos 2023-2026_
_Método: find /Volumes + gh api + lectura directa + session_store SQL_
