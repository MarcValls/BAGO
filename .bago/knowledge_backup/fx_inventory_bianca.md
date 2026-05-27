# FX Inventory — BIANCA Engine
_Actualizado por agente de soporte BAGO | 2026-05-04_
_Fuente: `.bago/state/global_state.json` + comentarios `// Sprint NNN` en `src/scenes/*.ts` + directiva de sesión_

> 🔴 **ALERTA DE TAMAÑO**: bundle en **323.39 KB** — límite de referencia 325 KB. Margen restante: ~1.6 KB (~2-3 sprints FX ligeros). Priorizar sprints de audio (sin coste de bundle) antes de nuevos FX.

---

## PrologueScene

| Sprint | Efecto | Estado en código |
|--------|--------|-----------------|
| 206 | `panelWipe` — transición horizontal ink entre paneles | Confirmado en `engine_learnings.md` |
| 215 | `sparkles` — partículas glyph en todos los paneles | Confirmado en `engine_learnings.md` |
| 241 | `ecoRings` — ondas de eco concéntricas al avanzar de panel | Confirmado en global_state |
| 255 | `pageShards` — fragmentos de página volando (book-page shards) | **`// Sprint 255` en línea 160, 289, 556** |
| 264 | `glitchStatic` — estática de glitch, caracteres corruptos parpadeando | Retroactivo — sin comentario en código |
| 270 | `binaryRain` — lluvia binaria (0/1) cayendo en cascada detrás del texto | Retroactivo — sin comentario en código |

---

## PaginaEnBlancaScene

| Sprint | Efecto | Estado en código |
|--------|--------|-----------------|
| 201 | `fogDrift` — niebla reactiva al movimiento de Bianca | Confirmado en `engine_learnings.md` |
| 210 | `brillitoTrail` — light trail de brillito | Confirmado en `engine_learnings.md` |
| 244 | `inkVolatileParticles` — partículas de tinta volátiles por paso | Confirmado en global_state |
| 249 | `writePulseRings` — anillos de pulso de escritura alrededor de Bianca | **`// Sprint 249` en líneas 129, 502, 704** |
| 260 | `inkSpillBloom` — derrame de tinta bloom en tiles de tinta | **`// Sprint 260` en línea 132** |
| 266 | `ghostWriting` — escritura fantasma: frases latentes que aparecen y se desvanecen | Retroactivo — sin comentario en código |
| 272 | `inkFractals` — fractales de tinta ramificados brotando y desvaneciendo | Retroactivo — sin comentario en código |

---

## LlanurasParrafoScene

| Sprint | Efecto | Estado en código |
|--------|--------|-----------------|
| 198 | `biancaGlow` — glow pulsante bajo Bianca | Confirmado en `engine_learnings.md` |
| 207 | `brillitoTrail` — light trail de brillito | Confirmado en `engine_learnings.md` |
| 211 | `collectibleAura` — aura dorada de proximidad a coleccionable | Confirmado en `engine_learnings.md` |
| 216 | `borradorShadow` — sombra oscura bajo borrador | Confirmado en `engine_learnings.md` |
| 239 | `wordAura` — aura de palabras en Bianca (azul→rojo según inventario) | Confirmado en global_state |
| 248 | `punctuationRain` — lluvia de signos de puntuación | **`// Sprint 248` en líneas 89, 501, 899** |
| 256 | `glyphStream` — corriente de glifos en el río de tinta (tile id=5) | **`// Sprint 256` en líneas 92, 521, 914** |
| 262 | `wordDust` — polvo de palabras arrastrado por el viento (frases flotando horizontal) | Retroactivo — sin comentario en código |
| 271 | `paperButterflies` — mariposas de papel flotando con movimiento senoidal | Retroactivo — sin comentario en código |

---

## BosqueInconclusasScene

| Sprint | Efecto | Estado en código |
|--------|--------|-----------------|
| 202 | `resonimoGlows` — glow al pisar tiles id=4 | Confirmado en `engine_learnings.md` |
| 209 | `ecoRings` — anillos al trigger eco | Confirmado en `engine_learnings.md` |
| 213 | `brillitoTrail` — light trail de brillito | Confirmado en `engine_learnings.md` |
| 218 | `borradorFogAura` — aura de niebla oscura bajo borrador | Confirmado en `engine_learnings.md` |
| 237 | `puddleRings` — anillos de charcos durante windSweep | Confirmado en global_state |
| 246 | `fireflyHalo` — halo dorado en luciérnagas | Confirmado en global_state |
| 252 | `bioSpores` — esporas bioluminiscentes ascendentes | **`// Sprint 252` en líneas 99, 523, 668** |
| 257 | `earthVeins` — venas de luz bioluminiscente en la tierra | **`// Sprint 257` en líneas 102, 533, 646** |
| 263 | `lightWeb` — telaraña de luz entre puntos del bosque (filamentos verdes pulsantes) | Retroactivo — sin comentario en código |
| 273 | `forestWordShadows` — sombras de palabras forestales flotando entre los árboles | Retroactivo — sin comentario en código |

---

## TorreBabelScene

| Sprint | Efecto | Estado en código |
|--------|--------|-----------------|
| 197 | `enrageFlash` — overlay rojo-naranja en enrage | Confirmado en `engine_learnings.md` |
| 200 | `victoryBurst` — burst de partículas al derrotar al boss | Confirmado en `engine_learnings.md` |
| 205 | `bossHpFlash` — flash al recibir daño el boss | Confirmado en `engine_learnings.md` |
| 208 | `hudWordsJitter` — jitter en palabras del HUD durante enrage | Confirmado en `engine_learnings.md` |
| 212 | `resonimoRipples` — ripples durante chase/enrage | Confirmado en `engine_learnings.md` |
| 217 | `glyphEchoes` — ecos de glyph al recoger palabras | Confirmado en `engine_learnings.md` |
| 236 | `attackBurst` — burst isométrico al atacar (elipse expansiva) | Confirmado en global_state |
| 242 | `inkExplosion` — explosión de tinta + inkSplats en derrota del boss | Confirmado en global_state |
| 245 | `enrageShockwave` — onda de choque roja concéntrica al enrage | Confirmado en global_state |
| 250 | `vocabLightning` — relámpagos de vocabulario entre torretas | **`// Sprint 250` en líneas 365, 826, 899** |
| 258 | `inkTides` — mareas de tinta en el suelo (ondas sinusoidales) | **`// Sprint 258` en líneas 368, 850, 1161** |
| 261 | `iceCrystals` — cristales de hielo orbitando la arena del jefe (diamantes rotantes en elipse) | Retroactivo — sin comentario en código |
| 269 | `chaosRuneSpiral` — espiral de runas caóticas rotando alrededor de la arena del jefe | Retroactivo — sin comentario en código |

---

## SegundoActoScene

| Sprint | Efecto | Estado en código |
|--------|--------|-----------------|
| 204 | `starTwinkle` — twinkle animado por estrella individual | Confirmado en `engine_learnings.md` |
| 238 | `nebulaFlares` — destellos de nebulosa en extinción de meteoros | Confirmado en global_state |
| 247 | `lineFlash` — flash horizontal al aparecer cada línea | Confirmado en global_state |
| 254 | `auroraBorealis` — aurora boreal pulsante | **`// Sprint 254` en líneas 50, 168** |
| 265 | `goldenStarDust` — polvo de estrellas doradas flotando hacia arriba con drift sinusoidal | Retroactivo — sin comentario en código |
| 274 | `charVortex` — vórtice de caracteres girando alrededor del centro de escena | Retroactivo — sin comentario en código |

---

## SettingsScene

| Sprint | Efecto | Estado en código |
|--------|--------|-----------------|
| 199 | `cursorGlow` — cursor ◈ pulsante con glow | Confirmado en `engine_learnings.md` |
| 214 | `vignetteBreath` — vignette animada que respira lento | Confirmado en `engine_learnings.md` |
| 243 | `optionLightTrace` — trazo luminoso lateral en opción seleccionada | Confirmado en global_state |
| 253 | `audioEqualizer` — ecualizador de ondas sonoras detrás del menú | **`// Sprint 253` en líneas 43, 231** |
| 267 | `voiceWaves` — ondas concéntricas de voz expandiéndose desde el centro del menú | Retroactivo — sin comentario en código |
| 275 | `dataStreamBg` — franjas de datos (SYS:, 0xFF, ERR:) cayendo en el fondo | Retroactivo — sin comentario en código |

---

## CreditsScene

| Sprint | Efecto | Estado en código |
|--------|--------|-----------------|
| 203 | `actoShimmer` — shimmer en centro del scroll en texto ACTO | Confirmado en `engine_learnings.md` |
| 240 | `horizontalFlares` — destellos horizontales en scroll | Confirmado en global_state |
| 251 | `orbitLetterRings` — anillos de letras orbitando el centro | **`// Sprint 251` en líneas 113, 255, 558** |
| 259 | `letterConstellations` — constelaciones de letras titilantes con líneas | **`// Sprint 259` en líneas 116, 581** |
| 268 | `letterMeteors` — meteoros de letras cruzando la pantalla con estela y carácter luminoso | Retroactivo — sin comentario en código |
| 276 | `letterKaleidoscope` — caleidoscopio de glifos simétricos: 6 brazos × 3 anillos | Retroactivo — sin comentario en código |

---

## Resumen por escena

| Escena | Total FX implementados | Sprints destacados |
|--------|----------------------|--------------------|
| TorreBabelScene | 14 | …250,258,261,**269** + retroac.222,225 |
| BosqueInconclusasScene | 11 | …252,257,263,**273** + retroac.226 |
| LlanurasParrafoScene | 10 | …248,256,262,**271** + retroac.221,228 |
| PaginaEnBlancaScene | 8 | …249,260,266,**272** + retroac.219 |
| PrologueScene | 7 | …241,255,264,**270** + retroac.224 |
| CreditsScene | 7 | …251,259,268,**276** + retroac.223 |
| SegundoActoScene | 7 | …247,254,265,**274** + retroac.227 |
| SettingsScene | 7 | …243,253,267,**275** + retroac.220 |
| **TOTAL** | **~71 FX** | **sprints 197–276** |

> Los retroactivos 219-228 tienen descripción desde `backlog.md`. Los sprints 229-235 existen pero sin descripción registrada.
> 🔴 **Bundle: 323.39 KB — margen ~1.6 KB hasta límite 325 KB.** Próximos sprints: audio SFX (sin coste de bundle).

---

## ✅ Gap 219-235 — resuelto como retroactivos

Los sprints 219-235 fueron **implementados en una sesión anterior sin añadir comentarios `// Sprint NNN` en el código**. Build estimada ~296 KB.

- **219-228**: descripciones recuperadas desde `.bago/sprints/backlog.md`
- **229-235**: implementados pero sin descripción registrada en ninguna fuente disponible

Para verificar: buscar manualmente en las escenas correspondientes los bloques añadidos entre los sprints 218 y 236.

_Última actualización: 2026-05-04 — sprints 269-276 añadidos, alerta bundle size activada_
