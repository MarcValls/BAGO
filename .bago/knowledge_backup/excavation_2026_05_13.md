# BAGO — Gran Excavación de Conocimiento
_Generado: 2026-05-13 | Fuente: 14 instancias .bago en disco + 10 repos GitHub MarcValls_
_Agente: Copilot CLI | Método: find /Volumes + gh api + lectura directa de archivos_

---

## 📍 Instancias .bago encontradas (14 total)

| Ubicación | Versión | Estado | Proyecto |
|-----------|---------|--------|---------|
| `/Volumes/bago_core/.bago` | 3.3.0 | ACTIVO | BAGO framework principal |
| `/Volumes/bago_core/examples/minimal/.bago` | — | minimal | Ejemplo mínimo |
| `/Volumes/Warehouse/AMTEC/DERIVA/.bago` | — | done | DERIVA RPG |
| `/Volumes/Warehouse/AMTEC/2026/ABRIL2026/Pandamien_Doc_Dev_amTech_Ordenado/.bago` | 2.2.2 | frozen | Pandamien |
| `/Volumes/Warehouse/CESAR_WOODS/.bago` | — | minimal | César Woods |
| `/Volumes/Warehouse/INTELIA_Manager_2026/Contabilidad/TPV_Contabilidad 2/.bago` | — | — | TPV Contabilidad |
| `/Users/INTELIA_Manager/bago-framework/.bago` | 2.5 | publicado | Framework público |
| `/Users/INTELIA_Manager/Desktop/BAGO.V4.PLANO/BAGO_AMTEC_V2_2_1_OFICIAL_utf8/.bago` | 2.2.1 | frozen | AMTEC canónico |
| `/Users/INTELIA_Manager/Desktop/BAGO.V4.PLANO/WORCK01/.bago` | 2.2.2 | frozen | AMTEC revisión |
| `/Users/INTELIA_Manager/Desktop/BAGO.V4.PLANO/WORCK01/BAGO_AMTEC_V2_2_2_OFICIAL_utf8/.bago` | 2.2.2 | frozen | AMTEC 2.2.2 UTF8 |
| `/Users/INTELIA_Manager/Desktop/BAGO.V4.PLANO/WORCK01/BAGO_OFICIAL_LIMPIO_2_3_CLEAN/.bago` | 2.3 | frozen | AMTEC 2.3 clean |
| `/Users/INTELIA_Manager/.bago` | — | global | Sesiones globales |
| `/Users/INTELIA_Manager/BAGO/.bago` | 3.x | CLI v3 | BAGO CLI v3 full |
| `/Volumes/Warehouse/AMTEC/2026/MAYO_2026/BIANCA_MASTER/MOTORES/bianca_engine_paperdoll/.bago` | — | done | BIANCA engine |

---

## 🎮 BLOQUE A — Canvas 2D FX (DERIVA RPG / BIANCA)
_Fuente: `/Volumes/Warehouse/AMTEC/DERIVA/.bago/knowledge/learned_lessons.md`_

### Reglas críticas de Canvas

| ID | Regla | Error que previene |
|----|-------|--------------------|
| **C-001** | `canvas.width` es físico — para coordenadas lógicas usar `canvas.width / devicePixelRatio` | Mapa aparece como parche en borde derecho |
| **C-002** | `ctx.scale()` es ACUMULATIVO — en resize usar `ctx.setTransform(dpr,0,0,dpr,0,0)` (idempotente) | Zoom×4 al escalar dos veces |
| **C-003** | Buffer fijo 960×540 causa letterboxing — usar `Math.round(canvas.clientWidth * dpr)` | Marcos negros en resoluciones distintas |
| **C-004** | Para pantalla completa: `Math.max(cw/W, ch/H)` (cover). Para barras negras: `Math.min(...)` (letterbox) | Juego con espacios en blanco laterales |
| **C-005** | Factor 0.92 en zoom = dead code → condición camera-follow nunca activa | Feature rota silenciosamente |
| **C-006** | Camera-follow por eje INDEPENDIENTE: `fitsX = mapW*zoom <= cw`, `fitsY = mapH*zoom <= ch` (no &&) | Follow falla si solo un eje tiene overflow |

### Reglas FX (Canvas 2D)

```
SIEMPRE después de cualquier bloque FX:
  ctx.shadowBlur = 0;         // shadow contamina renders posteriores
  ctx.globalAlpha = 1;        // alpha contamina renders posteriores
  ctx.save() / ctx.restore()  // cuando modificas 3+ propiedades

NUNCA:
  ctx.scale() acumulativo → usar setTransform()
  zoom *= 0.92 → dead code
  camera-follow con && → chequear por eje
```

---

## 🎯 BLOQUE B — BIANCA Engine (47 FX catalogados)
_Fuente: `BIANCA_MASTER/MOTORES/bianca_engine_paperdoll/.bago/knowledge/`_

### Catálogo FX por escena

| Escena | FX | Sprints |
|--------|-----|---------|
| TorreBabelScene | 11 (+2 retroactivos) | 197-258, 261, 269 |
| BosqueInconclusasScene | 8 (+2 retroactivos) | 202-257, 263, 273 |
| LlanurasParrafoScene | 7 (+2 retroactivos) | 198-256, 262, 271 |
| PaginaEnBlancaScene | 5 (+2 retroactivos) | 201-260, 266, 272 |
| PrologueScene | 4 (+2 retroactivos) | 206-255, 264, 270 |
| CreditsScene | 4 | 203-259 |
| SegundoActoScene | 4 (+2 retroactivos) | 204-254, 265, 274 |
| SettingsScene | 4 | 199-253 |
| **TOTAL** | **47+ confirmados** | sprints 197-287 |

### FX reutilizables (patrones Python)

```python
# Partículas flotantes (bioSpores)
spores = []
sporeTimer = 0
# update(dt): sporeTimer+=dt; if>0.3 spawn; forEach decay alpha-=dt*0.4; filter alpha>0
# render(): ctx.globalAlpha=s.alpha; arc; ctx.shadowBlur=8; fill; reset

# Aurora/gradiente animado
auroraTime = 0
# update(dt): auroraTime+=dt
# render(): for 4 bandas: createLinearGradient; hue=160+i*30+sin(t*0.3)*20; fillRect

# Lightning entre puntos
bolts = []
# update(dt): if timer>0.8 spawn bolt; alpha-=dt*3; filter alpha>0
# render(): zigzag 2-3 segmentos punto medio random; ctx.shadowBlur=6; reset
```

### AudioManager (9 SFX sin conectar — patrón de deuda)

Gap detectado en BIANCA (según análisis de historial): AudioManager implementado pero aparentemente sin conexión en call sites de escenas al momento del análisis.
Lección: **siempre verificar 2 lados: implementación + wiring en call sites**.

| SFX | Call site correcto |
|-----|--------------------|
| `playFootstep()` | `onMove` en todas las escenas |
| `playWordPickup()` | `_checkWordPickups()` en TorreBabel |
| `playDialogueBlip(pitch)` | cada carácter renderizado |
| `playMenuSelect()` | selección en Settings |

### BeatTimer.onBeat — patrón FX rítmico

```typescript
// BPMs por zona: PEB=72, LP=90, BI=108, TB=140
// BeatTimer.onBeat(beat) hookear para:
// - Pulsos visuales sincronizados
// - Spawn partículas on-beat
// - Flash HUD al ritmo
// BeatTimer.isOnBeat(tolerance=0.15) → true si ±15% del beat
```

---

## 🧠 BLOQUE C — BAGO Neural Fabric
_Fuente: `gh api /repos/MarcValls/BAGO_NEURAL_FABRIC/readme`_

Arquitectura SENSE → PLAN → ACT → OBSERVE → LEARN → DECIDE:

| Componente | Función |
|------------|---------|
| `neural_toolbox.py` | Dot-product scoring: contexto vs perfiles de herramienta |
| Intent routing | Free-text intent → cadena de herramientas correcta |
| Multi-tool orchestration | Workflows secuenciales/condicionales |
| Feedback loops | Pesos de herramientas actualizados por outcomes |
| Autonomous loop | Ciclo SENSE/ACT/LEARN persistente con cross-platform lock |

**Patrón de activación neural**: vector de contexto × dot-product contra capability profiles → herramienta con mayor score se activa primero.

---

## 🎰 BLOQUE D — BAGO Telegram Bot (patrones MiniApp)
_Fuente: `gh api /repos/MarcValls/BAGO_TELEGRAM_BOT/readme`_

| Feature | Implementación |
|---------|----------------|
| Intent detection | Free-text → acción bot sin comandos explícitos |
| Inline keyboards | Menús interactivos con botones de acción |
| MiniApp | Web UI vía `/app` — integración Telegram WebApp API |
| Multi-channel notify | Notificaciones a múltiples canales simultáneos |

**Reutilizable para**: cualquier bot que necesite UI embedded (Mini App pattern).

---

## 💰 BLOQUE E — BAGO Wallet Tracker (patrones cripto read-only)
_Fuente: `gh api /repos/MarcValls/BAGO_WALLET_TRACKER/readme`_

| Patrón | Implementación |
|--------|----------------|
| Portfolio live | CoinGecko API — free, no auth, precios en tiempo real |
| TON scanner | Jetton balances + NFTs + eventos recientes |
| Airdrop detection | Passive vs active claim — catalog JSON |
| Zero custody | Nunca private keys; TonConnect para claim proposals |

**Principio clave**: `read-only first` — leer blockchain sin custodiar = sin riesgo legal.

---

## 🎵 BLOQUE F — BAGO Music Pipeline (patrones audio)
_Fuente: `gh api /repos/MarcValls/BAGO_MUSIC_PIPELINE/readme`_

| Herramienta | Función |
|-------------|---------|
| Score pipeline | PDF/imagen/MusicXML/MIDI/MuseScore → notación estructurada |
| Transposición | Selección de partes y cambio de tono |
| Synthesis | Patrones synth Karpovich + Disc Superstar |
| Ableton integration | MIDI tracks, gestión de sets, keyboard reference |
| Virtual MIDI | BAGO como dispositivo MIDI virtual |

---

## 🪟 BLOQUE G — BAGO Windows Automation
_Fuente: `gh api /repos/MarcValls/BAGO_WINDOWS_AUTOMATION/readme` + guías en repo_

Guías disponibles:
- `windows_mouse_automation.md` — clase `BAGOMouse`, Win32 `mouse_event`, detección ventanas, automatización Ableton
- `windows_execution_patterns.md` — UAC auto-elevation, Task Scheduler, `runas`
- `windows_background_automation.md` — tareas background sin bloqueo de UI
- `windows_audio_setup.md` — setup audio Windows para producción

---

## 🎮 BLOQUE H — BIANCA Sprite Studio (generación de sprites)
_Fuente: `gh api /repos/MarcValls/BAGO_SPRITE_STUDIO/readme` + `BIANCA_MASTER/MOTORES/.bago/knowledge/toolkit.md`_

### Backends de generación (por prioridad)

| Backend | Disponibilidad | Calidad | Notas |
|---------|---------------|---------|-------|
| GitHub Copilot Codex CLI | Reset 02:42 AM | Alta (~1.3 MB/frame) | Sin key, mejor calidad |
| Perchance vía Brave CDP | Inmediato | Variable | Bias frontal en modelo y06fzf5rev — solo S/SE/SW |
| HF Space Gradio | Sin key | Variable | Siempre disponible |
| OpenAI gpt-image-1 | OPENAI_API_KEY | Muy alta | Requiere key |
| Replicate FLUX | REPLICATE_API_KEY | Alta | Requiere key |
| Diffusers (local) | pip + 4GB | Alta | Offline |

### Regla crítica BIANCA sprites
```
SIN ESPEJOS — cada frame direccional se genera individualmente.
No usar hflip de PIL para frames E/W — genera anatomía incorrecta.
```

### Prompt template BIANCA
```
anime game sprite, character BIANCA, female, white/silver hair,
dark green hoodie, pale skin, standing pose, full body,
transparent background, clean cel-shading,
color accents: blue #4da8ff, gold #f7d774
```

### Pipeline Perchance CDP (anti-Cloudflare)
```python
# Perfil Brave real → /tmp/brave_bianca_cdp
# Prompts: prompts_v3_optimized_32.csv (VIEW FIRST + anatomical anchors + negations)
# Script: bianca_perchance_auto.py
```

---

## 🏗️ BLOQUE I — BAGO Versiones (línea de evolución)

| Versión | Estado | Características clave |
|---------|--------|-----------------------|
| 2.2.1 | frozen | Primera integración repo-first oficial |
| 2.2.2 | frozen | Hardening validación + stress github_models con backoff |
| 2.3 | frozen | AMTEC clean |
| 2.5 | público GitHub | 30 tools, 12 workflows, 13 CLI |
| 3.0 | — | CLI v3, BAGO Tablet |
| 3.3.0 | ACTIVO | 83 CLI tools, bago.db, guardian, neural fabric |

### DEC-005 (versión 2.2.2 — lección permanente)
Para `github_models`, NO usar ráfaga libre. Usar:
- Backoff con reintentos ante `429` y `5xx`
- Limitador global `global_rate_limit_rps`
- Presets: `safe=0.5 rps`, `balanced=1.0 rps`
- Sin limitador: `10×30` → masivos 429, `error_rate` alto

---

## 📋 BLOQUE J — WORCK01 GLOSARIO CANÓNICO
_Fuente: `/Users/INTELIA_Manager/Desktop/BAGO.V4.PLANO/WORCK01/.bago/docs/GLOSARIO.md`_

| Término | Definición canónica |
|---------|---------------------|
| **Repo-first** | Priorizar leer el repo real antes de sobredocumentar metaestructura |
| **Arranque suficiente** | Carga mínima necesaria para operar con criterio |
| **Activación mínima suficiente** | Solo activar los roles necesarios para la tarea actual |
| **Deriva** | Desplazamiento no controlado entre función declarada y uso real |
| **Reserva** | Hallazgo que no invalida el sistema pero impide considerarlo cerrado |
| **GO con reservas** | Valida uso operativo pero obliga a dejar constancia de deuda |
| **Prompt operativo** | Prompt ejecutable con poco retrabajo, objetivo y formato claros |
| **Frozen decision** | Decisión congelada que puede obsoletarse — auditar cada sprint |

---

## 🔄 BLOQUE K — Pandamien / AMTEC (estado Pandamien project)
_Fuente: `/Volumes/Warehouse/AMTEC/2026/ABRIL2026/Pandamien_Doc_Dev_amTech_Ordenado/.bago/`_

Estado proyecto al 2026-04-14:
- 77 BLGs generados (Fases F00-F05 completadas)
- BAGO v2.2.2 en estado lifecycle_status: "done"
- `corpus: GO_WITH_RESERVATIONS` — funcional pero con deuda residual
- 4 sesiones + 1 change + 1 evidence en inventario

**Ciclo de trabajo AMTEC (lección operativa)**:
```
bago ideas → implementa → bago health (≥80%) → bago task --done
```

---

## 🌐 BLOQUE L — Glosario de repos GitHub MarcValls (inventario completo)

| Repo | Tipo | Conocimiento clave |
|------|------|--------------------|
| BAGO | Framework | CLI principal, 83 tools, bago.db |
| BIANCA_THE_GAME | Game engine | 47 FX, TypeScript + Python, ISO_GAME |
| BAGO_WINDOWS_AUTOMATION | Automation | Win32 mouse, UAC, Task Scheduler |
| BAGO_NEURAL_FABRIC | AI | SENSE→PLAN→ACT loop, dot-product routing |
| BAGO_WALLET_TRACKER | Cripto | TON readonly, CoinGecko, airdrop patterns |
| BAGO_SPRITE_STUDIO | Imagen | Pillow + HF + Codex sprite pipeline |
| BAGO_TELEGRAM_BOT | Bot | MiniApp, intent detection, inline keyboards |
| BAGO_MUSIC_PIPELINE | Audio | Score pipeline, MIDI, Ableton, Karpovich |
| ISO_GAME | Engine | Isometric Python engine, pathfinding A*, chunker |
| BAGO_NEURAL_FABRIC | AI | Dynamic orchestration, feedback loops |
| bago-framework | Framework | v2.5 público — entrada oficial para Copilot |
| INTELIA_Manager_TPV | POS | TypeScript POS, Sprint 1-9, facturación |
| Genemaps_Regular_roots_genetics | Scraper | BS4+Playwright+FastAPI+SQLite |
| PANEL_ORQUESTADOR | Orquestador | TypeScript/Electron, agent REST, propose-tasks |
| AMTEC_microterror | Game | Godot GDScript, horror |
| BIANCA_THE_GAME_FRAGMENTS | Narrativa | Biblia del universo BIANCA, personajes |

---

## ✅ RESUMEN DE NUEVAS LECCIONES (sesión excavación)

| ID | Lección | Fuente |
|----|---------|--------|
| EX-001 | `ctx.setTransform(dpr,0,0,dpr,0,0)` en resize, no `scale()` | DERIVA LL-002 |
| EX-002 | Camera-follow por eje independiente (no &&) | DERIVA LL-006 |
| EX-003 | `Math.max` para cover, `Math.min` para letterbox | DERIVA LL-004 |
| EX-004 | FX siempre: shadowBlur=0, globalAlpha=1, save/restore | DERIVA LL-008/009/010 |
| EX-005 | AudioManager: verificar SIEMPRE los 2 lados (impl + wiring) | BIANCA engine |
| EX-006 | BeatTimer.onBeat → hook para FX visuales rítmicos sincronizados | BIANCA engine |
| EX-007 | Sprites: SIN espejos — cada frame direccional se genera solo | BIANCA toolkit |
| EX-008 | Perchance CDP: modelo y06fzf5rev tiene bias frontal (S/SE/SW) | BIANCA toolkit |
| EX-009 | BAGO Neural: dot-product context→tools para routing de intención | Neural Fabric |
| EX-010 | github_models: rate limit global 0.5-1.0 rps o 429 masivos | WORCK01 DEC-005 |
| EX-011 | Frozen decisions se obsoletan — auditar cada sprint con grep | DERIVA LL-007 |
| EX-012 | TON read-only: CoinGecko (sin auth) + toncenter.com (sin key) | Wallet Tracker |
| EX-013 | 14 instancias .bago activas en discos de MarcValls | Excavación 2026-05-13 |
| EX-014 | Arranque suficiente: leer solo lo necesario, no sobredocumentar | WORCK01 GLOSARIO |
| EX-015 | Pandamien completado: 77 BLGs, F00-F05 done, lifecycle="done" | Pandamien state |

---

_Cross-learning completado: 2026-05-13 | 14 instancias .bago + 10 repos GitHub_
_Instancias absorbidas: DERIVA, Pandamien, BIANCA_MASTER, WORCK01, bago-framework, BAGO CLI v3_
