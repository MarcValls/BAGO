# BAGO Toolkit — Herramientas Disponibles
_Última actualización: 2026-05-05 | Proyecto: BIANCA — El Juego_

---

## ÍNDICE RÁPIDO

| Categoría | Herramienta | Disponible ahora | Requiere |
|-----------|------------|-------------------|----------|
| **Generación** | Codex (M6) | ✅ a las 02:42 | Nada — usa terminal abierto |
| **Generación** | Perchance Brave CDP (M1) | ✅ Inmediato | Brave corriendo |
| **Generación** | Perchance Motion (M5) | ✅ Inmediato | Brave corriendo |
| **Generación** | HF Space Gradio | ✅ Sin key | — |
| **Generación** | OpenAI gpt-image-1 (M3) | 🔑 Key | OPENAI_API_KEY |
| **Generación** | HF Inference API | 🔑 Key | HF_TOKEN |
| **Generación** | Replicate FLUX | 🔑 Key | REPLICATE_API_KEY |
| **Generación** | Diffusers Local | 📦 Setup | pip + 4GB descarga |
| **Generación** | ComfyUI | 🖥️ Servidor | ComfyUI running |
| **Generación** | A1111 | 🖥️ Servidor | A1111 running |
| **Generación** | Imagen 3 (Google) | 🔑 Key | GEMINI_API_KEY |
| **Pipeline** | Autorun codex | ✅ Activo PID 27570 | — |
| **Pipeline** | Perchance pipeline | ✅ | Brave |
| **Pipeline** | Bash sprite runner | ✅ | — |
| **Validación** | Direction Detector | ✅ | PIL |
| **Ensamblado** | Spritesheet 1024×1536 | ✅ | PIL |
| **Engine** | FX System (47 efectos) | ✅ | — |
| **Engine** | AudioManager (9 SFX) | ✅ | — |

---

## 1. MÉTODOS DE GENERACIÓN DE IMÁGENES

### M6 — Codex (método activo)
```bash
# Un frame solo
~/.nvm/versions/node/v22.18.0/bin/codex exec \
  --json --color never --dangerously-bypass-approvals-and-sandbox \
  "Generate PNG sprite: [prompt]"

# Autorun completo (28 frames, espera 02:42)
python3 .bago/scripts/run_bianca_autorun.py
```
- **Status**: ✅ PID 27570 activo, espera 02:42
- **Output**: `.bago/prompts/frames_m6/bianca_DIR_PHASE.png`
- **Calidad**: ~1.3MB por frame, calidad alta
- **Límite**: Reset diario a 02:42 AM
- **Regla**: SIN espejos — cada frame se genera individualmente

---

### M1 — Perchance vía Brave CDP (verificado)
```bash
# Script completo con retry y validación
python3 .bago/scripts/bianca_perchance_auto.py

# Capture manual de un frame
python3 ~/Desktop/BAGO_CAJAFISICA/TEST_BAGO_03\(IMG\)/perchance_playwright_capture.py
```
- **Status**: ✅ Funciona solo para S, SE, SW (bias frontal)
- **Genera**: Imágenes ~270-550KB
- **Limitación crítica**: Modelo `y06fzf5rev` tiene bias frontal — NO genera E/W/NW/N/NE correctos
- **Cloudflare**: Bypasado con perfil Brave real en `/tmp/brave_bianca_cdp`
- **Prompts**: `prompts_v3_optimized_32.csv` (VIEW FIRST + anatomical anchors + negations)

---

### M5 — Motion Sequences vía Brave CDP
```python
# Archivo: ~/Desktop/BAGO_CAJAFISICA/TEST_BAGO_03(IMG)/methods/m5_motion_generator.py
# Secuencias: walk, run, jump, attack, idle, crouch, hurt
from methods.motion_sequences import WALK_SEQUENCE, get_frame_prompt
```
- **Status**: ✅ Disponible — biomechanics-aware walk cycles
- **Extiende**: M1 con secuencias coherentes por animación

---

### M3 — OpenAI gpt-image-1
```bash
export OPENAI_API_KEY="sk-..."
python3 ~/Desktop/BAGO_CAJAFISICA/TEST_BAGO_03\(IMG\)/methods/m3_openai_api.py
```
- **Status**: 🔑 Necesita key activa
- **Costo**: ~$0.04/imagen
- **Calidad anime**: ⭐⭐⭐⭐⭐

---

### HF Space Gradio (sin key)
```python
# ~/Desktop/BAGO_CAJAFISICA/TEST_BAGO_03(IMG)/methods/hf_space_t2i.py
python3 methods/hf_space_t2i.py --prompt "..." --output "frame.png"
```
- **Status**: ✅ Sin key, gratis
- **Velocidad**: 30-300s (cola pública)
- **Calidad**: ⭐⭐⭐

---

### HF Inference API (con key)
```bash
export HF_TOKEN="hf_..."
python3 methods/hf_inference_t2i.py
# Modelo: Animagine-XL — mejor calidad anime
```
- **Status**: 🔑 Key HF
- **Modelo recomendado**: `cagliostrolab/animagine-xl-3.1`
- **Calidad**: ⭐⭐⭐⭐⭐

---

### Imagen 3 — Google (próximo sprint)
```bash
export GEMINI_API_KEY="..."
python3 .bago/prompts/generate_sprites_imagen3.py
```
- **Status**: 🔑 Pendiente key — sprint 288 prep
- **Modelo**: `imagen-3.0-generate-002`
- **Output dir**: `.bago/prompts/frames_v2/`
- **Calidad**: ⭐⭐⭐⭐⭐ (mejor disponible)

---

### Diffusers Local (M1 MPS)
```bash
pip install torch torchvision diffusers transformers accelerate
python3 methods/diffusers_local_t2i.py
# Usa MPS (Metal) en M1 — sin GPU CUDA necesaria
```
- **Status**: 📦 4GB descarga, sin key
- **Velocidad**: 30-120s en M1
- **Calidad**: ⭐⭐⭐⭐⭐

---

### ComfyUI Local
```bash
git clone https://github.com/comfyanonymous/ComfyUI
pip install -r requirements.txt
python main.py --force-fp16 --listen  # Servidor en localhost:8188
python3 methods/comfyui_api_t2i.py   # Cliente
```
- **Status**: 🖥️ Requiere servidor running
- **Ventaja**: LoRA, ControlNet, workflows customizados

---

## 2. SCRIPTS DE PIPELINE Y ORQUESTACIÓN

### Autorun Principal (activo)
```bash
# Ubicación correcta — dentro del proyecto
python3 .bago/scripts/run_bianca_autorun.py
# PID actual: 27570 | Espera 02:42 AM
# Log: .bago/logs/bianca_sprites_gen.log
```
- Lee prompts de `prompts_v3_optimized_32.csv`
- Salta los 4 frames válidos (E_0, E_1, E_3, SE_0)
- Genera 28 frames únicos, sin espejos
- Manejo automático de rate limit (espera reset)
- Ensambla spritesheet al completar 32 frames

---

### Pipeline Perchance con retry
```bash
python3 .bago/scripts/bianca_perchance_auto.py
# Configuración clave:
PERCHANCE_SKIP_DIRS = {"NW","N","NE"}  # Direct codex fallback
MAX_RETRIES = 3
# Solo válido para S, SE, SW
```

---

### Bash runner (batches)
```bash
./run_bianca_sprites.sh
# Procesa 4 batches (E_SE / S_SW / W_NW / N_NE) x 8 frames
# Maneja rate limit con wait_for_reset()
```

---

### Monitor post-autorun
```bash
bash ~/Desktop/BAGO_CAJAFISICA/TEST_BAGO_03\(IMG\)/post_autorun_monitor.sh
# Vigila el directorio y reporta frames completados en tiempo real
```

---

## 3. SCRIPTS DE VALIDACIÓN Y ANÁLISIS

### Direction Detector
```bash
# Un frame
python3 scripts/bianca_direction_detector.py --frame <img.png> --expected E

# Batch completo
python3 scripts/bianca_direction_detector.py --batch .bago/prompts/frames_m6 out.csv
```
- Algoritmos: background removal → bounding box → head zone → skin position → contour bumpiness
- Regla hard: N/NW/NE con `has_face=True` → RECHAZADO siempre
- Limitación: Confianza baja en E/W (bias frontal del modelo)

---

### Verify frames
```bash
# Verifica todos los frames generados
python3 ~/Desktop/BAGO_CAJAFISICA/TEST_BAGO_03\(IMG\)/verify_codex_frames.py
python3 ~/Desktop/BAGO_CAJAFISICA/TEST_BAGO_03\(IMG\)/verify_frames.py
```

---

### Repair failed frames
```bash
python3 ~/Desktop/BAGO_CAJAFISICA/TEST_BAGO_03\(IMG\)/repair_failed_frames.py
# Lee failed_frames.txt y regenera solo los fallidos
```

---

## 4. ENSAMBLADO DE SPRITESHEET

```bash
python3 scripts/assemble_bianca_spritesheet.py \
    .bago/prompts/frames_m6 \
    public/assets/sprites/char_bianca_walk_4x8.png

# Spec: 1024×1536 | 4cols × 8rows | 256×192 por cell
# Orden filas: E, SE, S, SW, W, NW, N, NE
# Orden cols: idle(0), step1(1), stride(2), step2(3)
# Frames faltantes → celda transparente (graceful degradation)
```

---

## 5. PROMPTS V3 — ESTRUCTURA ÓPTIMA

```
[VIEW CONSTRAINT PRIMERO] + [ANATOMICAL ANCHORS] + [CHAR DESCRIPTION] + [NEGATIONS]
```

| Dirección | Clave del prompt |
|-----------|-----------------|
| **E** (derecha) | `pure side profile facing RIGHT, only right eye visible, nose as right-facing bump` |
| **W** (izquierda) | `pure side profile facing LEFT, only left eye visible, nose as left-facing bump` |
| **SE** | `3/4 view facing right-forward, both eyes visible but right more prominent` |
| **SW** | `3/4 view facing left-forward, both eyes visible but left more prominent` |
| **S** | `full frontal facing camera, both eyes centered, full face visible` |
| **N** | `FULL BACK VIEW, ZERO face, ZERO eyes, twin buns from behind` |
| **NW** | `back-left 3/4 view, no face, back of head left side` |
| **NE** | `back-right 3/4 view, no face, back of head right side` |

**CSV con 32 prompts completos:**
```
~/Desktop/BAGO_CAJAFISICA/TEST_BAGO_03(IMG)/prompts_v3_optimized_32.csv
```

---

## 6. ENGINE BIANCA — FX Y AUDIO

### Estado de FX por escena
| Escena | FX implementados | Bundle contrib |
|--------|-----------------|----------------|
| TorreBabelScene | 14 efectos | ~50KB |
| BosqueInconclusasScene | 9 efectos | ~40KB |
| LlanurasParrafoScene | 8 efectos | ~35KB |
| PaginaEnBlancaScene | 6 efectos | ~28KB |
| PrologueScene | 6 efectos | ~25KB |
| CreditsScene | 5 efectos | ~22KB |
| SegundoActoScene | 5 efectos | ~22KB |
| SettingsScene | 5 efectos | ~20KB |

**Bundle actual**: 326.47 KB (límite referencia: 325 KB)

---

### AudioManager — 9 SFX disponibles
```typescript
import { audioManager } from '../engine/AudioManager';

audioManager.playFootstep()        // Kick 80→40Hz, 80ms
audioManager.playWordPickup()      // Chime ascendente 440→880Hz
audioManager.playBorradorTouch()   // Swoosh + reverb
audioManager.playBossBeat()        // Impacto grave 60Hz
audioManager.playPerspectiveShift() // Whoosh de desfase
audioManager.playResonimoLand()    // Resonancia suave
audioManager.playMenuSelect()      // Click limpio 800Hz
audioManager.playInktramaSolve()   // Fanfarria micro
audioManager.playDialogueBlip(freq: number) // Blip configurable
```

---

### Beat Sync (pendiente explotar)
```typescript
// BeatTimer.onBeat — callback NUNCA usado aún
// Oportunidad: spawn de partículas, pulsos, glow en sync con BPM
// TorreBabelScene: 140 BPM | PaginaEnBlancaScene: 72 BPM | LlanurasParrafoScene: 90 BPM
```

---

## 7. DIRECTORIO DE ARCHIVOS CLAVE

```
bianca_engine_paperdoll/
├── .bago/
│   ├── knowledge/
│   │   ├── toolkit.md              ← ESTE ARCHIVO
│   │   ├── engine_learnings.md     ← FX inventory, sprints
│   │   ├── fx_inventory.md         ← Catálogo FX por escena
│   │   ├── audio_integration_guide.md ← 9 SFX + firmas
│   │   └── session_arc_7days.md    ← Historia del proyecto
│   ├── logs/
│   │   ├── bianca_sprites_gen.log  ← Log del autorun
│   │   └── bianca_perchance_auto.log
│   ├── prompts/
│   │   ├── frames_m6/              ← Frames Method 6 (4 válidos ahora)
│   │   ├── frames/                 ← Frames FLUX sprint 287 (completos, con mirrors)
│   │   └── frames_v2/              ← Futuro Imagen 3
│   ├── scripts/
│   │   ├── run_bianca_autorun.py   ← AUTORUN PRINCIPAL (PID 27570)
│   │   └── bianca_perchance_auto.py ← Pipeline Perchance
│   ├── state/
│   │   ├── global_state.json       ← Estado BAGO completo
│   │   └── sprint_state.json
│   └── sprints/
│       ├── sprint_log.md           ← Log de 72+ sprints
│       └── backlog.md              ← Pendientes
├── scripts/
│   ├── assemble_bianca_spritesheet.py ← Ensamblado 1024×1536
│   ├── bianca_direction_detector.py   ← Validación PIL
│   └── generate_bianca_walk_pillow.py ← Generación PIL pura
├── run_bianca_sprites.sh           ← Bash runner
├── public/assets/sprites/
│   └── char_bianca_walk_4x8.png    ← Spritesheet en uso (FLUX, con mirrors)
└── ~/Desktop/BAGO_CAJAFISICA/TEST_BAGO_03(IMG)/
    ├── prompts_v3_optimized_32.csv ← 32 prompts optimizados
    ├── methods/                    ← M1-M5 + comparativas
    │   ├── m1_brave_cdp.py         ← ✅ Perchance via Brave
    │   ├── m3_openai_api.py        ← 🔑 OpenAI gpt-image-1
    │   ├── m5_motion_generator.py  ← ✅ Walk cycles coherentes
    │   ├── hf_space_t2i.py         ← ✅ Sin key
    │   ├── hf_inference_t2i.py     ← 🔑 HF token
    │   └── diffusers_local_t2i.py  ← 📦 Setup local
    ├── verify_codex_frames.py
    ├── repair_failed_frames.py
    └── post_autorun_monitor.sh
```

---

## 8. ESTADO ACTUAL DEL SPRITESHEET

| Frame | Archivo | Status |
|-------|---------|--------|
| E_0 | `bianca_E_0.png` (1349KB) | ✅ Codex original |
| E_1 | `bianca_E_1.png` (1349KB) | ✅ Codex original |
| E_2 | — | ⬜ Pendiente (02:42) |
| E_3 | `bianca_E_3.png` (1357KB) | ✅ Codex original |
| SE_0 | `bianca_SE_0.png` (1332KB) | ✅ Codex original |
| SE_1-3 | — | ⬜ Pendiente (02:42) |
| S_0-3 | — | ⬜ Pendiente (02:42) |
| SW_0-3 | — | ⬜ Pendiente (02:42) |
| W_0-3 | — | ⬜ Pendiente (02:42) |
| NW_0-3 | — | ⬜ Pendiente (02:42) |
| N_0-3 | — | ⬜ Pendiente (02:42) |
| NE_0-3 | — | ⬜ Pendiente (02:42) |

**Total**: 4/32 ✅ | 28 pendientes → autorun a las 02:42

---

## 9. COMANDOS DE ESTADO RÁPIDO

```bash
# Ver frames generados
ls -lh .bago/prompts/frames_m6/bianca_*.png

# Ver log en tiempo real
tail -f .bago/logs/bianca_sprites_gen.log

# Ver si el autorun sigue vivo
ps aux | grep run_bianca_autorun | grep -v grep

# Ensamblar cuando estén los 32
python3 scripts/assemble_bianca_spritesheet.py \
    .bago/prompts/frames_m6 \
    public/assets/sprites/char_bianca_walk_4x8.png

# Validar dirección de un frame
python3 scripts/bianca_direction_detector.py --frame .bago/prompts/frames_m6/bianca_E_0.png --expected E
```
