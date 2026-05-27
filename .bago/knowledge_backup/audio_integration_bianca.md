# Audio Integration Guide — BIANCA Engine
_GAP CRÍTICO: AudioManager tiene 9 SFX implementados pero nunca llamados_
_Generado por agente de soporte BAGO | 2026-05-04_

---

## Estado actual

- **`src/engine/AudioManager.ts`** — ✅ Completamente implementado (Web Audio API pura, sin archivos externos)
- **`src/main.ts` línea 1722** — ✅ Inicializado: `(window as any).game.audio = audioManager`
- **`src/main.ts` línea 1727** — ✅ `audioManager.init()` llamado en primer click del usuario
- **Zonas ambientales** — ✅ Funcionan vía `SceneManager.ts` línea 99 (`zoneMap` auto-setea zona)
- **SFX de eventos** — ❌ **0 de 9 métodos SFX llamados desde ninguna escena**

**Import necesario en cada escena:**
```typescript
import { audioManager } from '../engine/AudioManager';
```

---

## Los 9 Métodos SFX — Firmas TypeScript

```typescript
// Firmas completas extraídas de src/engine/AudioManager.ts

audioManager.playFootstep(): void
// Kick suave 80→40Hz, duración 80ms. Llamar en cada paso de Bianca.

audioManager.playWordPickup(): void
// Arpegio ascendente 440→550→660Hz (3 notas), duración total ~350ms.

audioManager.playDialogueBlip(pitch: number = 600): void
// Square wave a `pitch` Hz, duración 50ms. Pitch varía por personaje.

audioManager.playInktramaSolve(): void
// Acorde mayor Do-Mi-Sol (261→329→392Hz), duración ~600ms. Resolución armónica.

audioManager.playBorradorTouch(): void
// Ruido bandpass 200Hz + tono sawtooth 120→40Hz descendente. Sonido áspero/peligroso.

audioManager.playPerspectiveShift(): void
// Sine 300→600→450Hz (sweep), duración 350ms. Efecto de cambio dimensional.

audioManager.playBossBeat(): void
// Kick drum sintético 150→30Hz, duración 200ms. Para impactos de boss.

audioManager.playMenuSelect(): void
// Square wave 880Hz, duración 100ms. Beep limpio de UI.

audioManager.playResonimoLand(): void
// Sine C5 (523.25Hz), duración 200ms. Nota musical limpia.
```

---

## Dónde llamar cada método (por escena + línea aproximada)

### 1. `playFootstep()` — todas las escenas de juego
Llamar en el método que mueve a Bianca, justo después de validar que el movimiento es válido.

**Patrón a buscar:** función que asigna `biancaTileX`/`biancaTileY` y empuja a `inkFootprints`.

```typescript
// PaginaEnBlancaScene.ts ~línea 1059 (después de: this.biancaTileX = nx)
// LlanurasParrafoScene.ts — mismo patrón
// BosqueInconclusasScene.ts — mismo patrón
// TorreBabelScene.ts — mismo patrón

// Template de inserción:
const nx = this.biancaTileX + dx;
const ny = this.biancaTileY + dy;
if (/* tile walkable */) {
  // ... inkFootprints push ...
  this.biancaTileX = nx;
  this.biancaTileY = ny;
  audioManager.playFootstep(); // ← INSERTAR AQUÍ
}
```

**Riesgo**: Muy bajo. Sin efectos secundarios. Agregar todas las escenas en un solo sprint.

---

### 2. `playWordPickup()` — TorreBabelScene
Llamar dentro de `_checkWordPickups()` cuando se recoge una palabra.

```typescript
// TorreBabelScene.ts ~línea 1915 (_checkWordPickups)
private _checkWordPickups(): void {
  // ... lógica de colisión ...
  if (/* palabra en rango && no recogida */) {
    this.wordInventory.addWord(word);
    audioManager.playWordPickup(); // ← INSERTAR AQUÍ
    // ... spawn glyph echoes ...
  }
}
```

**Riesgo**: Muy bajo.

---

### 3. `playBorradorTouch()` — todas las escenas con ElBorrador
Llamar dentro del callback `onTouchBianca` de cada borrador.

```typescript
// PaginaEnBlancaScene.ts ~línea 1316
// LlanurasParrafoScene.ts ~línea 161
// BosqueInconclusasScene.ts ~línea 160
// TorreBabelScene.ts ~línea 408 (borrador normal) y ~línea 412 (gran borrador)

// Template:
this.borrador.onTouchBianca = () => {
  audioManager.playBorradorTouch(); // ← INSERTAR AL INICIO DEL CALLBACK
  // ... lógica de daño/screen shake ...
};
```

**Riesgo**: Muy bajo.

---

### 4. `playBossBeat()` — TorreBabelScene
Llamar al infligir daño al Gran Borrador y/o al recibir hit de boss.

```typescript
// TorreBabelScene.ts — buscar `bossHp` asignaciones de daño
// y/o en _onBorradorTouch('gran')

// Template:
if (/* hit confirmado en boss */) {
  this.granBorrador.bossHp -= dmg;
  audioManager.playBossBeat(); // ← AL INFLIGIR DAÑO
}

// También al recibir hit del boss:
this.granBorrador.onTouchBianca = () => {
  audioManager.playBossBeat(); // ← ADEMÁS de playBorradorTouch
  // ...
};
```

**Riesgo**: Bajo. Dos calls en TorreBabelScene.

---

### 5. `playPerspectiveShift()` — BosqueInconclusasScene
Llamar dentro del callback `onAngleChange` del PerspectiveManager.

```typescript
// BosqueInconclusasScene.ts ~línea 208

this.perspectiveManager.onAngleChange = (angle) => {
  audioManager.playPerspectiveShift(); // ← INSERTAR AL INICIO
  // ... lógica de cambio de perspectiva de SimemorfMechanic ...
};
```

**Riesgo**: Muy bajo.

---

### 6. `playResonimoLand()` — todas las escenas con tiles Resonimo
Llamar cuando Bianca aterriza en tile id=4 o id=5 (en el movimiento válido).

```typescript
// Integrar en el patrón de movimiento de cada escena con resonimo tiles:
// PaginaEnBlancaScene, LlanurasParrafoScene, BosqueInconclusasScene, TorreBabelScene

// Template (en la sección de movimiento, tras actualizar posición):
const tileId = this.mapData.tiles[ny]?.[nx];
if (tileId === 4 || tileId === 5) {
  audioManager.playResonimoLand(); // ← INSERTAR AQUÍ
}
```

**Riesgo**: Bajo. Verificar que `mapData.tiles` es accesible en el scope.

---

### 7. `playMenuSelect()` — SettingsScene
Llamar cuando el usuario confirma una opción (Enter/Space) o navega entre opciones (ArrowUp/Down).

```typescript
// SettingsScene.ts ~línea 456-465

// Al navegar (ArrowUp/Down):
if (e.code === 'ArrowUp' || e.code === 'KeyW') {
  this.selectedIndex = (this.selectedIndex - 1 + ...) % ...;
  audioManager.playMenuSelect(); // ← AL CAMBIAR SELECCIÓN
}
if (e.code === 'ArrowDown' || e.code === 'KeyS') {
  this.selectedIndex = (this.selectedIndex + 1) % ...;
  audioManager.playMenuSelect(); // ← AL CAMBIAR SELECCIÓN
}

// Al confirmar (Enter/Space): ya se llama onActivate(), no añadir doble sonido.
```

**Riesgo**: Muy bajo.

---

### 8. `playDialogueBlip(pitch)` — sistema de diálogo (DialogueChainMechanic)
Llamar por cada carácter renderizado en el typewriter de diálogos.

```typescript
// Buscar en engine/DialogueChainMechanic.ts o en el método de render de diálogos
// donde se avanza el índice de caracteres visibles.

// Template (en el loop de typewriter):
if (this.charTimer >= this.charDelay) {
  this.visibleChars++;
  this.charTimer = 0;
  audioManager.playDialogueBlip(600); // pitch 600Hz por defecto
  // Para voces distintas, variar pitch: Bianca=600, Brillito=800, Borrador=300
}
```

**Riesgo**: Medio. Verificar que no se llama en cada frame sino solo al avanzar un char. Usar `lastCharIndex` para throttle si es necesario.

---

### 9. `playInktramaSolve()` — InktramaMechanic
Llamar cuando se completa correctamente un puzzle Inktrama.

```typescript
// Buscar en engine/InktramaMechanic.ts el método _submit() o equivalente.
// Llamar solo cuando el resultado es correcto (no en error).

// Template:
private _submit(): void {
  if (this._isCorrect()) {
    audioManager.playInktramaSolve(); // ← SOLO EN ÉXITO
    this.state = 'solved';
    // ... callbacks de éxito ...
  } else {
    // error — no reproducir
  }
}
```

**Riesgo**: Muy bajo.

---

## Orden de implementación recomendado (menor riesgo primero)

| Prioridad | Sprint | SFX | Escenas afectadas | Riesgo |
|-----------|--------|-----|------------------|--------|
| 1 | 261 | `playMenuSelect` | SettingsScene únicamente | 🟢 Muy bajo |
| 2 | 262 | `playPerspectiveShift` | BosqueInconclusasScene únicamente | 🟢 Muy bajo |
| 3 | 263 | `playWordPickup` | TorreBabelScene únicamente | 🟢 Muy bajo |
| 4 | 264 | `playInktramaSolve` | engine/InktramaMechanic (1 punto) | 🟢 Muy bajo |
| 5 | 265 | `playResonimoLand` | 4 escenas (detección tile id=4/5) | 🟡 Bajo |
| 6 | 266 | `playBorradorTouch` | 4 escenas (onTouchBianca callbacks) | 🟡 Bajo |
| 7 | 267 | `playBossBeat` | TorreBabelScene (2 puntos) | 🟡 Bajo |
| 8 | 268 | `playFootstep` | 4 escenas (bucle de movimiento) | 🟡 Bajo |
| 9 | 269 | `playDialogueBlip` | engine/DialogueChainMechanic | 🟠 Medio (throttle necesario) |

**Rationale**: Empezar por escenas simples (Settings, Bosque) para validar el patrón de import + call antes de hacer cambios en 4 escenas simultáneamente. El dialogue blip es el último porque necesita cuidado con el throttle (no spamear audio en cada frame).

---

## Template completo de sprint de audio

```typescript
// PASO 1: Añadir import al inicio del archivo (si no existe)
import { audioManager } from '../engine/AudioManager';

// PASO 2: Localizar el punto de inserción exacto (ver tabla arriba)

// PASO 3: Insertar la llamada
audioManager.playNombreDelMetodo();

// PASO 4: Build de verificación
// npm run build → objetivo esperado; guardar log si falla
// Bundle size: esperar incremento <1 KB (solo una línea de código)
```

---

## Notas técnicas

- **AudioContext requiere interacción del usuario**: `audioManager.init()` ya se llama en el primer click (main.ts). Los SFX funcionarán automáticamente después de ese primer click.
- **Throttle en footstep**: Si Bianca se mueve por tiles rápidamente, el footstep ya tiene duración corta (80ms). No es necesario throttle adicional.
- **Acceso global**: `audioManager` está exportado como singleton. Importar directamente, no via `window.game.audio`.
- **Mute respetado**: Todos los métodos hacen `this._resumeContext()` interno. Si está muteado, `masterGain.gain.value = 0` silencia todo automáticamente.

_Última actualización: 2026-05-04_
