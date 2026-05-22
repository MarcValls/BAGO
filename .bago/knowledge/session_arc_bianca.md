# BAGO — Arc de 7 Días: Aprendizajes del Framework
_Fecha de cierre: 2026-05-04 | Proyecto: BIANCA — El Juego_
_Sprints cubiertos: 1–218 | Checkpoints: 1–44_

---

## ÍNDICE

1. [Fase 1 — DERIVA (Abandonado)](#fase-1--deriva-abandonado)
2. [Fase 2 — BIANCA Setup y Contratos](#fase-2--bianca-setup-y-contratos)
3. [Fase 3 — Engine desde cero (Sprints 1-36)](#fase-3--engine-desde-cero-sprints-1-36)
4. [Fase 4 — FX Polish Waves (Sprints 37-218)](#fase-4--fx-polish-waves-sprints-37-218)
5. [Gaps Críticos Identificados](#gaps-críticos-identificados)
6. [Proceso BAGO — Lecciones Operativas](#proceso-bago--lecciones-operativas)
7. [Impacto en el Framework](#impacto-en-el-framework)

---

## FASE 1 — DERIVA (Abandonado)

**Checkpoints 1–20** | Proyecto: `/Volumes/Warehouse/AMTEC/DERIVA/`

### Qué se construyó

BAGO loop autónomo implementó múltiples fases de un RPG de derivación textual:
- Battle system completo (turnos, stats, animaciones)
- Sprites generados con Pillow (Python)
- Simulaciones de física narrativa
- Puzzles de lenguaje y diálogos por árbol

### Stack técnico

- **Monorepo**: pnpm workspaces
- **Frontend**: React + TypeScript
- **Rendering**: canvas transparente + CSS backgrounds con z-index estratificado
- **Generación de imágenes**: Codex CLI (sin API key, via `codex exec`)

### Bug Fatal Descubierto: El "dos juegos encima"

```
isoRenderer.render() llamaba clear() internamente.
Al dibujar fondos CSS y luego llamar render(), los fondos quedaban borrados.
Síntoma visual: "como si hubiera dos juegos encima uno del otro".
```

**Solución correcta:**
- Canvas con `clearRect` (transparente), NO `fillRect` con color de fondo
- Fondo en `<div>` CSS con `z-index: 0`
- Canvas encima con `z-index: 1`, `background: transparent`

### Regla Codex CLI (aprendida aquí, válida para siempre)

```bash
# CORRECTO — dejar correr hasta el final:
codex exec --dangerously-bypass-approvals-and-sandbox \
  -s danger-full-access \
  "$(cat prompts/mi_prompt.txt)"

# NUNCA HACER — mata el proceso mid-generation:
codex exec ... | head -N
codex exec ... > output.txt   # puede truncar antes de completar
```

### El Pivot

> Usuario: *"PARA, vamos a empezar otro juego, este no me vale"*

**BAGO respondió correctamente:** paró inmediatamente, compiló todos los assets relevantes del filesystem y comenzó estructura limpia para BIANCA.

### Lección DERIVA → pivot

Cuando el usuario hace pivot a nuevo proyecto:
1. **Parar inmediatamente** — no terminar el sprint en curso
2. **Buscar en todo el filesystem** material relacionado con el nuevo proyecto
3. **Compilar y organizar assets** antes de escribir una sola línea de código
4. **Crear estructura de directorios** completa antes de empezar a construir

---

## FASE 2 — BIANCA Setup y Contratos

**Checkpoints 21–26** | Compilación de material + contratos de producción

### Compilación de material

- Recopiló ~1.5 GB de material BIANCA disperso en el filesystem
- Creó `/Volumes/Warehouse/AMTEC/2026/MAYO_2026/BIANCA_MASTER/` con 8 subdirectorios:
  - `CONTRATOS/`, `ARTE/`, `NARRATIVA/`, `MOTOR/`, `AUDIO/`, `MECANICAS/`, `MOTORES/`, `_UNUSED/`

### Contratos de producción generados

| Contrato | Contenido |
|----------|-----------|
| `ARTE_v1` | Guías visuales: paleta, sprites, UI |
| `NARRATIVA_v1` | Lore, personajes, estructura de actos |
| `MOTOR_TECNICO_v1` | Stack, build, arquitectura del engine |
| `MECANICAS_v1` | Todas las mecánicas de juego |
| `AUDIO_v1` | SFX, música, zonas ambientales |
| `CODEX_IMAGEGEN_v1` | Workflow de generación de imágenes |

### Auditoría de coherencia — 11 problemas encontrados

**P0 — Crítico:**
- Edad hardcodeada `"19"` en múltiples contratos → **siempre usar `{{chr_bianca.age}}`**
  - Regla: nunca hardcodear datos canónicos de personaje. Usar variables de plantilla.

**P1 — Alto:**
- Archivos con nombres mojibake (caracteres no ASCII) → **usar siempre ASCII kebab-case**
  - Ejemplo correcto: `bianca-portrait-idle.png`, NO `Bianca Retrato (Idle).png`

**P2 — Medio:**
- `manifest.json` sin SHA256 → **siempre añadir hash de integridad** para verificar assets

### Infraestructura de red (aprendido aquí)

```bash
# Compartir internet WiFi → Ethernet (macOS System Preferences → Internet Sharing)
# Es la opción más rápida para conectar una PC Windows sin router

# Detectar la PC en la red:
arp -a | grep en0

# Transferir archivos al PC Windows — método más simple:
python3 -m http.server 8080
# PC accede via: http://169.254.X.X:8080/archivo.zip
# (NO usar SMB/SSH — requieren configuración adicional)
```

---

## FASE 3 — Engine desde cero (Sprints 1-36)

**Checkpoints 27–35** | Engine TypeScript/Vite isométrico

### Arquitectura del engine

```typescript
// Núcleo del engine — jerarquía de clases:
SceneManager → Scene (abstract)
  abstract onLoad(): void
  abstract update(dt: number): void
  abstract render(ctx: CanvasRenderingContext2D): void
  abstract onUnload(): void

// Cambio de escena:
game.sceneManager.changeTo('scene_id')

// Acceso global (para debug/cheats/bridges):
(window as any).game  // referencia global al GameInstance

// Sistema de diálogo:
game.ui.showDialogue(DialogueData)  // líneas + retratos
```

### Stack técnico BIANCA

| Herramienta | Versión | Nota |
|-------------|---------|------|
| TypeScript | 6.0.3 | Requiere `"ignoreDeprecations": "6.0"` en tsconfig |
| Vite | 5.x | **NO usar v7** — broken ESM en este sistema |
| Node | LTS | npm scripts estándar |
| Build | `npm run build` | `tsc && vite build`, ~3s |

### Patrón de sprint — validado 218+ veces

1. **Identificar** 1 feature concreta y acotada
2. **Implementar** cambio mínimo en el/los archivos correctos
3. **Build** → `npm run build` debe pasar ✅ antes de continuar
4. **Si falla** → leer el error exacto, fix quirúrgico, rebuild
5. **Bundle size** crece linealmente:
   - Sprint normal: ~3–5 KB
   - Sistema nuevo (mecánica completa): ~8–15 KB
   - Si crece >20 KB en un sprint: algo está mal

### Sistemas implementados — Sprints 1-36

**Scenes:**
| Scene | Descripción |
|-------|-------------|
| `PrologueScene` | 12 paneles cinematográficos |
| `PaginaEnBlancaScene` | Zona 1, mundo vacío |
| `LlanurasParrafoScene` | Zona 2, llanuras |
| `BosqueInconclusasScene` | Zona 3, bosque |
| `TorreBabelScene` | Zona 4, torre + boss |
| `SegundoActoScene` | Acto 2 (placeholder expandible) |
| `SettingsScene` | Configuración del juego |
| `CreditsScene` | Créditos dinámicos según logros |

**Entidades:**
- `BrillitoEntity`: órbita 28px, 1.8 rad/s, trail built-in en `renderAt()`
- `ElBorrador`: estados `patrol/alert/chase/retreat/stunned`, DETECT_RADIUS=4, CHASE_RADIUS=6

**Mecánicas:**
| Mecánica | Detalle |
|----------|---------|
| `InktramaMechanic` | Puzzles de gramática, 3 estados, tipos válidos: `'subject'\|'verb'\|'predicate'` |
| `ResonimoMechanic` | BeatTimer, BPMs: PEB=72, LP=90, BI=108, TB=140 |
| `SimemorfMechanic` | 4 ángulos (Q/E), 5 palabras: BANCO/CARA/PALO/COPA/SIERRA |

**Sistemas:**
- `WordInventory`: 22 palabras totales, categorías, recetas
- `DialogueChainMechanic`: proximity triggers desde JSON
- `PliegoMechanic`: pliegos de papel plegables (13 totales)
- `EcoDialogoMechanic`: ecos narrativos en zonas
- `CollectibleManager`: 15 coleccionables (3+4+3+4+1 boss_relic)
- `LoreJournalHUD`: 2 tabs — fragmentos + pliegos
- `MinimapSystem`: nodes, badges, ☠ para boss
- `GranBorrador boss`: 3 fases, enrage a HP≤2
- `SaveSystem`: slots, playtime, collectibles, pliegos, accessibility
- `AccessibilityManager`: temas, tamaños, reducir movimiento, subtítulos → localStorage
- `NarrativeState`: flags persistentes (localStorage `bianca_narrative_state_v1`)
- `AchievementSystem`: 13 logros con hooks en todos los sistemas
- `ParticleManager/ParticleEmitter`: shapes `'letter'|'word'|'dot'|'glyph'`

---

## FASE 4 — FX Polish Waves (Sprints 37-218)

**Checkpoints 36–44** | 6 oleadas de efectos visuales

### Patrón FX — reutilizable en cualquier scene

Los siguientes patrones fueron validados 180+ veces. Copiar literalmente.

#### Trail Pattern (usado en 5+ scenes)

```typescript
// Declaración:
private trailBianca: Array<{x: number, y: number, alpha: number}> = [];

// En update(dt):
this.trailBianca.push({x: biancaScreenX, y: biancaScreenY, alpha: 1.0});
if (this.trailBianca.length > 12) this.trailBianca.shift();
this.trailBianca.forEach(p => p.alpha -= dt * 2.5);

// En render() — ANTES del renderAt() de la entidad:
this.trailBianca.forEach((p, i) => {
  const a = Math.max(0, p.alpha) * (i / this.trailBianca.length);
  ctx.globalAlpha = a;
  ctx.beginPath();
  ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
  ctx.fillStyle = '#a0e8ff';
  ctx.fill();
});
ctx.globalAlpha = 1;
```

#### Fog Pattern (usado en 4 zonas)

```typescript
// Declaración:
private fogTime = 0;

// En update(dt):
this.fogTime += dt;

// En render():
const pulse = 0.08 + 0.04 * Math.sin(this.fogTime * 0.8);
const cx = W / 2 + Math.sin(this.fogTime * 0.3) * 40;
const cy = H / 2 + Math.cos(this.fogTime * 0.4) * 20;
const fog = ctx.createRadialGradient(cx, cy, 10, cx, cy, W * 0.7);
fog.addColorStop(0, `rgba(180,160,220,${pulse})`);
fog.addColorStop(1, 'rgba(180,160,220,0)');
ctx.fillStyle = fog;
ctx.fillRect(0, 0, W, H);
```

#### Shadow Ellipse Pattern (borrador con sombra oscura)

```typescript
// En render(), ANTES de dibujar el borrador:
const sx = borradorScreenX;
const sy = borradorScreenY + 18; // desplazar hacia abajo
const pulse = 0.22 + 0.08 * Math.sin(Date.now() * 0.0028);
ctx.globalAlpha = pulse;
const grad = ctx.createRadialGradient(sx, sy, 0, sx, sy, 48);
grad.addColorStop(0, 'rgba(10,4,20,0.7)');
grad.addColorStop(1, 'rgba(10,4,20,0)');
ctx.fillStyle = grad;
ctx.beginPath();
ctx.ellipse(sx, sy, 48, 22, 0, 0, Math.PI * 2);
ctx.fill();
ctx.globalAlpha = 1;
```

#### Echo Particles Pattern (glyph echoes en word pickup)

```typescript
// Declaración:
private wordEchoes: Array<{
  text: string; x: number; y: number;
  alpha: number; scale: number; vy: number;
}> = [];

// En spawn (al recoger palabra):
const glyphs = ['✦', '✧', '◈', '⊕', '✴'];
for (let i = 0; i < 3; i++) {
  this.wordEchoes.push({
    text: glyphs[Math.floor(Math.random() * glyphs.length)],
    x: pickupX + (Math.random() - 0.5) * 30,
    y: pickupY - i * 12,
    alpha: 0.9 - i * 0.2,
    scale: 1.2 - i * 0.15,
    vy: -25
  });
}

// En update(dt):
this.wordEchoes.forEach(e => {
  e.y += e.vy * dt;
  e.alpha -= dt * 1.4;
});
this.wordEchoes = this.wordEchoes.filter(e => e.alpha > 0);

// En render():
this.wordEchoes.forEach(e => {
  ctx.save();
  ctx.globalAlpha = Math.max(0, e.alpha);
  ctx.font = `${Math.round(16 * e.scale)}px serif`;
  ctx.fillStyle = '#d4b8ff';
  ctx.shadowColor = '#9060ff';
  ctx.shadowBlur = 8;
  ctx.fillText(e.text, e.x, e.y);
  ctx.restore();
});
```

### Oleada 1 — Combate y Parallax (Sprints 37-52)

- Ink splats al recibir daño (normalized coords 0–1, radial gradients)
- Boss HP lag bar: campo `bossHpLag` decayendo 0.8/s para el visual delay
- Combo pip indicators: 6 arcs, colores por nivel de combo
- Fog animado por zona (radial gradients orbitando al centro)
- Parallax backgrounds: siluetas de árboles, hills en horizonte, ink drops
- Starfield en Prologue: 70 estrellas con `phase` única por estrella (evita parpadeo sincronizado)

### Oleada 2 — Achievements + Ambient (Sprints 53-108)

- 13 hooks de logros conectados a eventos de juego via `AchievementSystem.unlock(id)`
- Word echoes ambientales en todas las zonas (texto flotante aleatorio del vocabulario)
- Ink footprints en todas las zonas (ellipses oscuras fade)
- Parallax letters en Prologue (ALPHABET descendente a velocidades distintas)
- Screen shake en TorreBabel: ±1.5px durante enrage boss

### Oleada 3 — Bonus y narrativa (Sprints 109-147)

- Bonus collectibles activados al completar zonas
- Achievement descriptions poéticas (en español, tono literario)
- Debris particles en transición enrage
- Ripple rings en Resonimo land (onBeat visual)
- Bianca glow trail en todas las zonas

### Oleada 4 — Trails y rings (Sprints 148-197)

- BrillitoEntity orbit trail en todas las zonas (trail adicional sobre el built-in)
- Resonimo land rings animados (ondas concéntricas en tiles id=4)
- Inktrama glow tiles (highlight en tiles id=3 al resolver)
- Boss color phases: idle→chase→enrage→defeated con mezcla de color progresiva

### Oleada 5 — Dark polish (Sprints 197-218)

- Dark shadow ellipses bajo borrador (LlanurasParrafo, PaginaEnBlanca)
- Fog aura oscura bajo borrador (BosqueInconclusas)
- Glyph echoes en word pickup (TorreBabel)
- Sprint 200: victory burst al derrotar al boss
- Sprint 206: panel wipe horizontal ink entre paneles del prólogo

---

## GAPS CRÍTICOS IDENTIFICADOS

### GAP 1 — AudioManager SFX sin conectar

El `AudioManager` tenía 9 funciones SFX implementadas que no estaban conectadas desde escenas en la revisión documentada:

| Función | Dónde conectar |
|---------|----------------|
| `playFootstep()` | `onMove` en cada scene |
| `playWordPickup()` | `TorreBabelScene._checkWordPickups()` |
| `playBorradorTouch()` | Todos los `onTouchBianca` callbacks |
| `playBossBeat()` | `TorreBabelScene` durante combat |
| `playResonimoLand()` | `ResonimoMechanic` landing |
| `playInktramaSolve()` | `InktramaMechanic._submit()` |
| `playDialogueBlip(pitch)` | `DialogueChainMechanic` por carácter |
| `playPerspectiveShift()` | `SimemorfMechanic.onAngleChange` |
| `playMenuSelect()` | `MenuScene` + `SettingsScene` |

> Las zonas ambientales SÍ funcionan: `SceneManager.ts` línea 99 auto-setea zona via `zoneMap`.

**Próximo sprint natural**: conectar SFX uno por uno (Sprint 219+).

### GAP 2 — BeatTimer.onBeat sin hookear

`ResonimoMechanic.BeatTimer` tiene `onBeat(beat: number)` que dispara en cada beat. Ninguna scene lo usa.

```typescript
// Ejemplo de uso pendiente:
beatTimer.onBeat = (beat) => {
  // Pulso visual sincronizado
  this.beatFlash = 1.0;
  // Spawn partícula on-beat
  particleManager.emit({x: beatX, y: beatY, count: 3, shape: 'dot'});
};
```

BPMs por zona: `PEB=72, LP=90, BI=108, TB=140` → `beatDuration = 60/bpm` segundos.

---

## PROCESO BAGO — LECCIONES OPERATIVAS

### Roles de agentes disponibles

| Agente | Rol |
|--------|-----|
| `bago-loop` / `bago-sprints-N` | Loop autónomo de sprints FX |
| `bago-organizativo` | Limpieza de archivos no usados, deduplicación |
| `bago-tester` | QA completo: TypeScript, build, checks |
| `bago-sim` | Simulaciones de engine/gameplay sin tocar código |
| `bago-sprints-219` | (activo) Continúa desde Sprint 219 |

**Regla de delegación**: siempre verificar build en el agente antes de reportar sprint completo. Un sprint no está hecho si `npm run build` no pasa en verde.

### Errores comunes de TypeScript/Vite

| Error | Causa | Fix |
|-------|-------|-----|
| `ignoreDeprecations missing` | TypeScript 6.0.3 | Añadir `"ignoreDeprecations": "6.0"` a tsconfig |
| `ParticleShape 'circle' invalid` | Shape no existe | Usar `'letter'\|'word'\|'dot'\|'glyph'` |
| `isoToScreen is not a method` | Función de módulo | Importar como función, no llamar como `this.isoToScreen()` |
| `getScreenPosition undefined` | BrillitoEntity API | Usar `brillito.getScreenPosition(sx, sy)` |
| `collectedAt not in type` | CollectedItem interfaz | No existe ese campo — usar flags en NarrativeState |
| `complement is not valid` | InktramaMechanic tipos | Válidos: `'subject'\|'verb'\|'predicate'` |
| `broken ESM` | Vite v7 | Degradar a `vite@5.x` |

### Workflow de sesión BAGO — protocolo estándar

```
ARRANQUE:
  1. Leer .bago/state/global_state.json
  2. Leer .bago/sprints/backlog.md → siguiente sprint prioritario
  3. Leer .bago/knowledge/ relevante para la tarea

EJECUCIÓN:
  4. Ejecutar sprint con cambio mínimo
  5. npm run build → verde antes de continuar
  6. Actualizar .bago/state/global_state.json
  7. Lanzar agentes background para trabajo paralelo si aplica

CONOCIMIENTO:
  8. Al aprender algo nuevo → añadir a .bago/knowledge/
  9. Al cerrar sesión → actualizar last_updated y next_sprint

PROHIBICIONES:
  - NO guardar estado en session-state de Copilot (es efímero)
  - NO usar SQL todos de Copilot para tracking de proyecto BIANCA
  - NO hardcodear datos canónicos de personajes
  - NO usar nombres de archivo con caracteres no-ASCII
```

### Datos canónicos BIANCA — reglas de producción

| Dato | Regla |
|------|-------|
| Edad de Bianca | NUNCA `"19"` → usar `{{chr_bianca.age}}` |
| Color hoodie | Verde oscuro (override sobre azul oscuro de biblia original) |
| Nombres de archivo | ASCII kebab-case únicamente |
| Documentos de contrato | Siempre SHA256 en `manifest.json` |
| Palabras InktramaMechanic | Solo `'subject'|'verb'|'predicate'` |

### Transferencia de archivos a PC Windows

```bash
# Opción más simple — HTTP server en Mac:
python3 -m http.server 8080

# PC accede via navegador:
http://169.254.X.X:8080/archivo.zip

# Detectar IP del PC en Ethernet:
arp -a | grep en0

# Compartir internet WiFi→Ethernet:
# System Preferences → Sharing → Internet Sharing
# Share from: Wi-Fi | To computers using: Ethernet (Thunderbolt Bridge)
```

---

## IMPACTO EN EL FRAMEWORK

### Qué cambia en cómo BAGO opera

**1. Protocolo de pivot es estándar:**
Cuando el usuario hace pivot a nuevo proyecto, BAGO siempre para inmediatamente, compila assets del filesystem, organiza estructura antes de construir. No negocia, no termina el sprint en curso.

**2. El patrón de sprint es la unidad mínima de trabajo:**
1 sprint = 1 feature = 1 build verde. No hay sprint sin build verde al final. Esto es invariante.

**3. Los patrones FX son primitivos reutilizables:**
Trail, Fog, Shadow Ellipse, Echo Particles — se copian literalmente entre escenas sin adaptar. Son primitivos del engine, no código ad-hoc.

**4. Regla Codex CLI es absoluta:**
Nunca pipear `codex exec` a `head`, `tail`, `>` ni nada que pueda matar el proceso antes de que termine. Es un proceso generativo que debe correr hasta completar naturalmente.

**5. La delegación a agentes es preferida para loops:**
Para sprints en loop (FX Polish, refactors masivos, auditorías), siempre lanzar agente background. El agente principal coordina, no ejecuta cada sprint.

**6. El estado vive en `.bago/`, no en Copilot:**
El session-state de Copilot es efímero. Todo estado operativo relevante va a `.bago/state/global_state.json`. Todo conocimiento técnico va a `.bago/knowledge/`. Los sprints van a `.bago/sprints/`.

**7. Los gaps son deuda técnica trackeable:**
GAP 1 (Audio SFX) y GAP 2 (BeatTimer.onBeat) son el backlog natural para los siguientes sprints. Todo gap identificado se documenta con su localización exacta y qué conectar.

**8. Build size es métrica de salud:**
- `~3-5 KB/sprint`: sprint bien hecho
- `~8-15 KB/sprint`: sistema nuevo, aceptable
- `>20 KB/sprint`: alerta — revisar qué se incluyó de más

---

_Documento generado por BAGO | Sesión: sprints-197-218-plus | 2026-05-04_
_Checkpoints procesados: 1–44 | Sprints documentados: 1–218_
