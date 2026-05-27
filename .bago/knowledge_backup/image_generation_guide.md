# Image Generation Guide — macOS M1

> **Contexto:** Guía técnica completa para generación de imágenes T2I en macOS M1 (sin GPU CUDA)
> **Proyecto objetivo:** BIANCA sprites y assets visuales
> **Validado:** TEST_BAGO_03 — Apr 23-24, 2026
> **Scripts:** `/Users/INTELIA_Manager/Desktop/BAGO_CAJAFISICA/TEST_BAGO_03(IMG)/methods/`

---

## Resumen de métodos disponibles

| Método | API Key | Costo | Velocidad | Calidad Anime | Estado |
|--------|---------|-------|-----------|----------------|--------|
| Codex CLI | ❌ No | Gratis | ~30-60s | ⭐⭐⭐⭐ | ✅ **MEJOR OPCIÓN SIN KEY** |
| HF Space Gradio | ❌ No | Gratis | 30-300s | ⭐⭐⭐ | ✅ Fallback estable |
| HF Inference API | 🔑 HF_TOKEN | Gratis (1k/mes) | 15-45s | ⭐⭐⭐⭐⭐ | 🔑 Mejor ratio gratis |
| OpenAI DALL-E 3 | 🔑 OPENAI_KEY | $0.04/img | 8-20s | ⭐⭐⭐⭐⭐ | 🔑 Más rápido paid |
| Replicate FLUX | 🔑 REPLICATE | $0.002/img | 5-15s | ⭐⭐⭐⭐ | 🔑 Más barato paid |
| Diffusers Local | ❌ No | Gratis | 30-120s | ⭐⭐⭐⭐⭐ | 📦 Requiere 4GB setup |
| ComfyUI API | ❌ No | Gratis | 20-60s | ⭐⭐⭐⭐⭐ | 🖥️ Servidor local requerido |
| A1111 API | ❌ No | Gratis | 30-120s | ⭐⭐⭐⭐ | 🖥️ Servidor local requerido |

---

## MÉTODO 1 — Codex CLI (PRINCIPAL para BAGO)

**Por qué es el principal:** Sin API key, calidad ⭐⭐⭐⭐, integrado en flujo BAGO.

### Comando correcto

```bash
# FORMA CORRECTA — siempre así:
codex exec --dangerously-bypass-approvals-and-sandbox -s danger-full-access "$(cat prompts/mi_prompt.txt)"

# También válido con prompt inline:
codex exec --dangerously-bypass-approvals-and-sandbox -s danger-full-access \
  "Generate a 256x512 anime character sprite: blue hoodie, white hair, standing pose"
```

### Reglas críticas

```bash
# ❌ NUNCA hacer esto — MATA EL PROCESO:
codex exec ... | head -N
codex exec ... | grep algo
codex exec ... | tee archivo

# ❌ NUNCA redirigir salida — PUEDE TRUNCAR:
codex exec ... > file.txt
codex exec ... >> log.txt

# ✅ SIEMPRE dejar correr en terminal limpia
# ✅ Las imágenes se guardan automáticamente en:
~/.codex/generated_images/{session_id}/
```

### Workflow completo con Codex

```bash
# 1. Inicializar sesión (si no hay sesión activa)
bash init_codex_session.sh

# 2. Preparar prompt en archivo (evitar shell escaping):
cat > prompts/bianca_sprite.txt << 'EOF'
Create a 256x512 pixel anime character sprite. Character: BIANCA.
Features: white/silver hair, blue hoodie (dark green override), pale skin.
Pose: standing, facing forward, arms relaxed at sides.
Style: clean anime illustration, cel-shading, transparent background.
Color palette: blue #4da8ff, gold #f7d774, red #ff6b6b accents.
EOF

# 3. Ejecutar (NO pipear):
codex exec --dangerously-bypass-approvals-and-sandbox -s danger-full-access "$(cat prompts/bianca_sprite.txt)"

# 4. Buscar la imagen generada:
ls -lt ~/.codex/generated_images/ | head -5

# 5. Post-proceso con PIL:
python3 post_process.py --src ~/.codex/generated_images/{session_id}/output.png --dest sprites/bianca_stand.png
```

### Post-proceso con PIL

```python
from PIL import Image

def normalize_sprite(src_path: str, dest_path: str, width: int = 256, height: int = 512):
    """Normaliza sprite BIANCA al tamaño canónico."""
    img = Image.open(src_path)
    
    # Convertir a RGBA si no lo es (preservar transparencia)
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Resize con máxima calidad
    img = img.resize((width, height), Image.LANCZOS)
    
    # Guardar optimizado
    img.save(dest_path, optimize=True, quality=88)
    print(f"✅ Sprite guardado: {dest_path} ({width}x{height})")

# Para hojas de animación:
def normalize_sprite_sheet(src_path: str, dest_path: str):
    """Normaliza hoja de animación 256x1024."""
    normalize_sprite(src_path, dest_path, width=256, height=1024)
```

---

## MÉTODO 2 — HF Inference API (mejor gratis con key)

```python
import requests, os, base64

HF_TOKEN = os.environ["HF_TOKEN"]
API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"

def generate_hf(prompt: str, output_path: str) -> bool:
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "negative_prompt": "lowres, bad anatomy, bad hands, text, error",
            "num_inference_steps": 30,
            "guidance_scale": 7.5,
            "width": 512,
            "height": 512,
        }
    }
    response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
    if response.status_code == 200:
        with open(output_path, 'wb') as f:
            f.write(response.content)
        return True
    return False
```

---

## MÉTODO 3 — HF Space Gradio (sin key, fallback)

```python
from gradio_client import Client

# Endpoint público — sin key requerida
client = Client("prodia/sdxl-stable-diffusion-xl")

result = client.predict(
    prompt="anime character, white hair, blue hoodie, standing pose",
    negative_prompt="lowres, bad quality, blurry",
    model="anythingXL_xl.safetensors",
    steps=20,
    fn_index=0
)
# result[0] = ruta al archivo generado en /tmp/
```

**Notas:**
- Cola pública: puede tardar 2-10 min en hora punta
- No requiere API key ni instalación local
- Endpoint alternativo: `https://prodia-sdxl-stable-diffusion-xl.hf.space/api/predict`

---

## MÉTODO 4 — Diffusers Local (sin key, máxima calidad)

### Setup inicial (~4GB, una vez)

```bash
pip install torch torchvision diffusers transformers accelerate safetensors

# En macOS M1, el device es MPS (Metal) — se detecta automáticamente
python3 -c "import torch; print(torch.backends.mps.is_available())"  # debe ser True
```

### Uso con modelo anime

```python
import torch
from diffusers import StableDiffusionPipeline

# Modelo recomendado para sprites anime:
MODEL_ID = "Linaqruf/anything-v3.0"

# Device M1: MPS automático
device = "mps" if torch.backends.mps.is_available() else "cpu"

pipe = StableDiffusionPipeline.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.float16,
    safety_checker=None,  # para sprites de personajes
)
pipe = pipe.to(device)

prompt = "masterpiece, best quality, 1girl, white hair, blue hoodie, standing, anime style"
negative = "lowres, bad anatomy, bad hands, text, error, worst quality"

image = pipe(
    prompt=prompt,
    negative_prompt=negative,
    num_inference_steps=30,
    guidance_scale=7.5,
    width=256,
    height=512,
).images[0]

image.save("sprite_bianca.png")
```

---

## MÉTODO 5 — OpenAI DALL-E 3 ($0.04/imagen)

```python
from openai import OpenAI
import base64, os

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

response = client.images.generate(
    model="dall-e-3",
    prompt="Anime character sprite, BIANCA: white hair, dark green hoodie, standing pose, transparent background, 256x512 pixel art style",
    size="1024x1024",  # DALL-E 3 no acepta tamaños menores
    quality="standard",
    n=1,
    response_format="b64_json"
)

img_data = base64.b64decode(response.data[0].b64_json)
with open("bianca_dalle3.png", "wb") as f:
    f.write(img_data)
# Post-proceso PIL para resize a 256x512
```

---

## MÉTODO 6 — Replicate FLUX ($0.002/imagen)

```python
import replicate, os

output = replicate.run(
    "black-forest-labs/flux-schnell",
    input={
        "prompt": "anime sprite, BIANCA character, white hair, blue hoodie, standing",
        "width": 512,
        "height": 512,
        "num_inference_steps": 4,
        "guidance": 3.5,
    }
)
# output es una URL — descargar con requests
```

---

## Normalización de sprites — anchor point consistente

```python
# normalize_anchor.py — mantiene anchor point consistente entre frames
from PIL import Image
import numpy as np

def normalize_anchor(
    sprite_path: str,
    output_path: str,
    canvas_size: tuple = (256, 512),
    anchor_y_pct: float = 0.95  # pie del personaje al 95% del canvas
) -> None:
    """
    Coloca el personaje con el anchor point (pie) en posición consistente.
    Fundamental para animaciones sin 'jumping' entre frames.
    """
    img = Image.open(sprite_path).convert("RGBA")
    
    # Detectar bounding box del personaje (pixels no-transparentes)
    arr = np.array(img)
    non_transparent = arr[:, :, 3] > 10
    rows = np.any(non_transparent, axis=1)
    cols = np.any(non_transparent, axis=0)
    
    if not rows.any():
        raise ValueError(f"Sprite sin pixeles visibles: {sprite_path}")
    
    ymin, ymax = np.where(rows)[0][[0, -1]]
    xmin, xmax = np.where(cols)[0][[0, -1]]
    
    # Recortar personaje
    character = img.crop((xmin, ymin, xmax + 1, ymax + 1))
    
    # Crear canvas y colocar con anchor
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    char_h = character.height
    char_w = character.width
    
    target_y = int(canvas_size[1] * anchor_y_pct) - char_h
    target_x = (canvas_size[0] - char_w) // 2
    
    canvas.paste(character, (target_x, target_y), character)
    canvas.save(output_path, optimize=True)
    print(f"✅ Anchor normalizado: {output_path}")
```

---

## Contrato de arte BIANCA para generación

```yaml
# bianca_art_contract.yaml
character: BIANCA
palette:
  azul_lecturia: "#4da8ff"
  oro_arcana:    "#f7d774"
  rojo_energia:  "#ff6b6b"
  hoodie_color:  "dark green"  # override sobre biblia original (que era azul)

sprite_sizes:
  standard: [256, 512]     # personaje standing/idle
  sheet:    [256, 1024]    # hoja de animación (2 frames verticales)

image_format:
  mode: RGBA               # siempre con transparencia
  resize_filter: LANCZOS   # máxima calidad
  quality: 88              # optimizado sin pérdida visible

negative_prompts:
  - lowres
  - bad anatomy
  - bad hands
  - extra fingers
  - text
  - watermark
  - blurry
  - worst quality

anchor_point: 0.95         # pie del personaje al 95% del canvas
```

---

## Scripts disponibles

```
/Users/INTELIA_Manager/Desktop/BAGO_CAJAFISICA/TEST_BAGO_03(IMG)/methods/
├── method_01_codex_cli.py       → Codex CLI (PRINCIPAL)
├── method_02_hf_inference.py    → HF Inference API
├── method_03_hf_space.py        → HF Space Gradio
├── method_04_diffusers.py       → Diffusers local
├── method_05_dalle3.py          → OpenAI DALL-E 3
├── method_06_replicate.py       → Replicate FLUX
├── method_07_comfyui.py         → ComfyUI API local
├── method_08_a1111.py           → A1111 API local
├── method_09_stablepy.py        → StablePy wrapper
├── normalize_anchor.py          → Normalización anchor point
├── post_process.py              → Post-proceso PIL
├── frame_quality_report.html    → Reporte visual de calidad de frames
├── init_codex_session.sh        → Inicializar sesión Codex
└── post_autorun_monitor.sh      → Monitor post-generación
```

---

## Decision tree — qué método usar

```
¿Tienes API key?
├─ NO → ¿Tienes servidor local (ComfyUI/A1111)?
│        ├─ NO → ¿Quieres instalar 4GB de modelos?
│        │        ├─ SÍ → Diffusers local (mejor calidad)
│        │        └─ NO → Codex CLI (primera opción) → HF Space (fallback)
│        └─ SÍ → ComfyUI API o A1111 API
└─ SÍ  → ¿Cuál?
          ├─ HF_TOKEN (gratis 1k/mes) → HF Inference API ⭐⭐⭐⭐⭐
          ├─ OPENAI_KEY              → DALL-E 3 (más rápido)
          └─ REPLICATE_KEY          → FLUX schnell (más barato)
```

---

*Validado en TEST_BAGO_03 · Apr 23-24, 2026*
*Compilado por BAGO MAESTRO · 2026-05-04*
