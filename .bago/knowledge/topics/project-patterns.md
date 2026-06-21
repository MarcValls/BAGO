# Project Patterns

## Objetivo

Guardar patrones extraídos de proyectos para reutilizarlos en el framework.

## Estructura mínima de cada patrón

- contexto
- problema
- solución
- evidencia
- límites
- versión

## Regla

Si un patrón no puede aplicarse dos veces, aún no merece vivir aquí.



---

# CONTENIDO FUSIONADO DESDE RAÍZ (project_patterns.md)


# Project Patterns — BAGO Knowledge

> **Período:** Abril-Mayo 2026
> **Fuente:** Proyectos PANDAMIEN, BIANCA, NIGHTFRAME, TEST_BAGO_03, TPV, BAGO Framework
> **Compilado:** 2026-05-04

---

## PATRÓN: CANON DE DATOS

**Origen:** PANDAMIEN (Apr 14, 2026) — P0 fix de datos hardcodeados

### Regla fundamental

```
NUNCA hardcodear datos de personajes o datos canónicos que aparezcan
en más de un lugar del proyecto.
```

### Implementación

```python
# ❌ MAL — datos hardcodeados en el corpus:
"Tiene 17 años, vive en Madrid, mide 1.68m"
"La chica de 17 años"

# ✅ BIEN — referencias canónicas:
"Tiene {{chr_bianca.age}} años, vive en {{chr_bianca.city}}, mide {{chr_bianca.height}}"
"La chica de {{chr_bianca.age}} años"
```

### Estructura canónica recomendada

```
proyecto/
├── docs/
│   ├── characters.json      ← datos de personajes (SoT)
│   ├── canon_numbers.json   ← fechas, medidas, versiones (SoT)
│   └── manifest.json        ← SHA256 para verificar integridad
```

```json
// characters.json
{
  "chr_bianca": {
    "age": 17,
    "city": "Madrid",
    "height": "1.68m",
    "hoodie_color": "dark green",
    "hair_color": "white/silver"
  }
}
```

### Regla de auditoría

Si un dato numérico o de descripción aparece hardcodeado en más de un archivo → **P0 inmediato**.
Trigger de `workflow_validacion` automático.

### Nomenclatura de archivos

```
✅ kebab-case-ascii.md        ← siempre
✅ bianca_sprite_stand.png    ← underscore también válido en assets
❌ "Bianca Stand 2.png"       ← espacios → riesgo de mojibake
❌ "BIANCA_FINAL_v3(2).png"   ← caracteres especiales → fail en paths
```

---

## PATRÓN: TRANSFERENCIA DE ARCHIVOS (Mac → PC Windows)

**Origen:** BIANCA PREP — compartir assets ~1.5GB con PC en red local

### Método más simple: HTTP server en Mac

```bash
# Mac (servidor):
cd /directorio/con/archivos
python3 -m http.server 8080

# PC Windows (cliente — en navegador o PowerShell):
# http://169.254.X.X:8080/archivo.zip
# (link-local si DHCP no asignó IP)

# Detectar IP del Mac en Ethernet:
ifconfig en0 | grep "inet "    # en0 = Ethernet en Mac
arp -a | grep en0              # tabla ARP para ver dispositivos conectados
```

### Jerarquía de métodos por simplicidad

```
1. python3 -m http.server  ← más simple, siempre disponible
2. SMB/Samba              ← más robusto pero requiere configuración
3. SSH/SCP                ← potente pero puede no estar disponible en Windows
4. USB/pendrive           ← fallback físico
```

### Diagnóstico si el PC no ve el servidor

```bash
# Verificar que el firewall de Mac no bloquea:
sudo pfctl -s all | grep 8080

# Si Firewall Windows bloquea → poner el servidor en Mac, descargar desde PC
# (el PC inicia la conexión → Firewall Windows lo permite)

# Detectar PC en la red local:
arp -a | grep en0
ping 169.254.1.1  # probar link-local

# Verificar conectividad Ethernet:
networksetup -getinfo Ethernet
```

---

## PATRÓN: INTERNET SHARING macOS

**Origen:** BIANCA PREP — compartir WiFi con PC via Ethernet

### Activación GUI (única opción confiable)

```
1. Abrir: x-apple.systempreferences:com.apple.sharing
   (o: System Settings → General → Sharing)
2. Click en ⓘ junto a "Internet Sharing"
3. "Share your connection from": WiFi (en1)
4. "To computers using": ✅ Ethernet (en0 o USB)
5. Activar toggle "Internet Sharing"
6. Confirmar en el diálogo de advertencia
```

### Verificar que está activo

```bash
sysctl net.inet.ip.forwarding   # debe devolver: net.inet.ip.forwarding: 1
ifconfig bridge0                # debe existir si Internet Sharing está activo
```

### Limitación crítica

```
NOTA: sudo NO puede activar Internet Sharing programáticamente.
Requiere GUI o AppleScript con user interaction.
No intentar hacerlo desde terminal — no funciona.
```

---

## PATRÓN: GESTIÓN DE PROYECTOS BAGO (pivot seguro)

**Origen:** BIANCA PREP — transición desde PANDAMIEN

### Secuencia de pivot seguro

```
1. COMPILAR todos los assets antes de pivotar
   find /Volumes /Users -name "*BIANCA*" -o -name "*bianca*" 2>/dev/null
   Crear: PROYECTO_MASTER/assets_raw/

2. AUDITORÍA de material existente
   ls -la PROYECTO_MASTER/
   Identificar: qué existe, qué falta, qué es obsoleto

3. ESTRUCTURA canónica antes de escribir código
   PROYECTO_MASTER/
   ├── assets_raw/        ← todo lo compilado
   ├── assets_processed/  ← assets listos para usar
   ├── docs/              ← contratos, biblias, canon
   ├── src/               ← código
   └── _UNUSED/           ← archivos obsoletos (no borrar aún)

4. CONTRATOS DE PRODUCCIÓN antes de código
   - Generar 6+ contratos antes de abrir editor
   - Auditoría P0/P1/P2 de coherencia entre contratos
   - Solo declarar contratos listos tras auditoría

5. VERIFICAR BUILD antes de declarar sprint completo
```

---

## PATRÓN: SPRINT DISCIPLINE (validado 218 veces en BIANCA)

**Origen:** BIANCA engine development

### Reglas del sprint

```
1 sprint = 1 feature concreta (no varias)
Verificar build ANTES de reportar sprint completo
Build command: npm run build → tsc && vite build (~3s)
Bundle crece: ~3-5KB por sprint FX, ~8-15KB por sistema nuevo
```

### Chequeo pre-report

```bash
# ANTES de reportar sprint completo:
npm run build           # ← OBLIGATORIO
# Si falla → no reportar, arreglar primero
# Si pasa → bundle size check
ls -la dist/assets/*.js | awk '{print $5, $9}'
# Documentar delta de bundle en el sprint report
```

### Sprint report template

```markdown
## Sprint N — [Feature Name]
**Status:** ✅ BUILD VERIFIED
**Bundle delta:** +4.2KB (assets/index-abc123.js: 156KB → 160.2KB)
**Changes:**
- [descripción concisa del cambio]
**Tests:** [qué se verificó manualmente]
```

---

## PATRÓN: AGENTES EN PARALELO

**Origen:** BIANCA engine development — aceleración con multi-agent

### Agentes validados en Abril 2026

| Agente | Función | Cuándo usarlo |
|--------|---------|----------------|
| `bago-loop` | Sprints FX autónomos en background | Features de efectos visuales |
| `bago-organizativo` | Limpieza de archivos no usados | Tras sessions largas (107 archivos removidos) |
| `bago-tester` | QA completo del build | Antes de milestone/release |
| `bago-sim` | Simulaciones del engine | Validar física/comportamiento sin build completo |

### Reglas de coordinación

```
1. Cada agente tiene scope exclusivo — no solapar
2. Verificar build en agente antes de reportar completado
3. Agente organizativo: NUNCA borrar — solo mover a _UNUSED/
4. Agente loop: máximo 1 feature por ciclo
5. Sincronizar con main branch antes de iniciar agente
```

---

## PATRÓN: macOS RESOURCE FORKS

**Origen:** BIANCA — archivos `._*` causando ruido en el build

### El problema

```bash
ls -la | grep "^\._"
# ._bianca_sprite_stand.png
# ._app.tsx
# etc.

# Son resource forks creados automáticamente por:
# - Finder (copiar/mover archivos)
# - macOS extended attributes
# - Operaciones de Time Machine
```

### Limpieza periódica

```bash
# Limpiar todos los resource forks en el proyecto:
find . -name "._*" -delete

# Verificar que no hay en assets:
find . -name "._*" | wc -l  # debe ser 0

# Prevenir en copias desde externa:
cp -X archivo.png dest/   # -X no copia extended attributes
rsync -a --exclude="._*" src/ dest/
```

### Política BAGO

```
Agente organizativo: mueve ._* a _UNUSED/  (no borrar)
Limpieza semanal: find . -name "._*" -delete  (tras confirmar _UNUSED/)
.gitignore debe incluir: ._*
```

---

## PATRÓN: CANVAS + CSS ARCHITECTURE

**Origen:** DERIVA/BIANCA — bug de superposición doble — Apr 2026

### El bug

```typescript
// ❌ ERROR que causó el bug:
class IsometricRenderer {
  clear() {
    // Esto borraba el background CSS DESPUÉS de dibujarlo
    ctx.fillRect(0, 0, width, height);  // ← fillRect con color sólido
    // Resultado: canvas tapaba el background → parecía "dos juegos"
  }
}
```

### La solución correcta

```typescript
// ✅ CORRECTO: canvas transparente + CSS background

// IsometricRenderer:
class IsometricRenderer {
  clear() {
    ctx.clearRect(0, 0, width, height);  // ← clearRect (TRANSPARENTE)
    // No fillRect, no color sólido
  }
}

// App.tsx:
const App = () => (
  <div style={{ position: 'relative', width: '100%', height: '100%' }}>
    {/* Background en CSS, detrás del canvas */}
    <div style={{
      position: 'absolute',
      backgroundImage: 'url(/assets/bg.jpg)',
      backgroundSize: 'cover',
      zIndex: 0,
      width: '100%',
      height: '100%'
    }} />
    {/* Canvas transparente encima */}
    <canvas style={{
      position: 'absolute',
      zIndex: 1,
      background: 'transparent'  // ← CRÍTICO
    }} />
  </div>
);
```

### Regla

```
Canvas = transparente siempre
Background = CSS layer debajo del canvas
clear() = clearRect, NUNCA fillRect
```

---

## PATRÓN: TYPESCRIPT 6.0 en macOS M1

**Origen:** BIANCA engine — configuración de build validada Apr 2026

### Stack validado

```
Node:        v22.18.0 ✅
TypeScript:  6.0.x ✅
Vite:        5.x ✅ (NO vite@7 — broken ESM en este sistema)
```

### tsconfig.json requerido para TypeScript 6.0

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "ignoreDeprecations": "6.0",  // ← REQUERIDO para TS 6.0
    "jsx": "react-jsx",
    "outDir": "./dist",
    "rootDir": "./src"
  }
}
```

### vite.config.ts recomendado

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    target: 'es2022',
    chunkSizeWarningLimit: 500,  // KB
  }
})
```

### Diagnóstico de build failures

```bash
# Si tsc falla con errores de "deprecated" en TS 6.0:
# → Añadir "ignoreDeprecations": "6.0" en tsconfig.json

# Si vite@7 falla con ESM errors:
npm install vite@5 --save-dev  # ← downgrade a v5

# Si node_modules tiene conflictos:
rm -rf node_modules package-lock.json
npm install

# Build limpio:
npm run build 2>&1 | tail -20
```

---

## PATRÓN: WORKFLOW_VALIDACION para corpus

**Origen:** PANDAMIEN — validación de corpus narrativo de horror

### Cuándo usar `workflow_validacion`

```
✅ Corpus narrativo (biblias, capítulos, fichas de personaje)
✅ Contratos de producción (coherencia entre contratos)
✅ Datos canónicos distribuidos en múltiples archivos
✅ Assets multimedia (verificar integridad de manifest)
✅ Código con contratos BAGO
```

### Comando

```bash
python3 .bago/tools/workflow_selector.py --workflow validacion

# O directamente:
python3 .bago/tools/validate_manifest.py --corpus docs/
```

### Output esperado

```
[GO]  characters.json     → sin referencias hardcodeadas
[GO]  chapters/*.md       → todas las referencias usan {{chr_X.campo}}
[WARN] chapter_03.md:47  → "la chica de 17 años" → reemplazar con {{chr_bianca.age}}
[FAIL] canon_numbers.json → SHA256 no coincide con manifest
```

---

*Compilado por BAGO MAESTRO · 2026-05-04*
*Proyectos fuente: PANDAMIEN, BIANCA, NIGHTFRAME, TEST_BAGO_03, TPV, BAGO Framework*

---

## PATRÓN: CROSS-LEARNING BIDIRECCIONAL ENTRE PROYECTOS

**Origen:** Sesión 2026-05-05 — BIANCA sprint 288 (canvas fullscreen) resuelto con lección de DERIVA

### Regla fundamental

```
Antes de resolver un problema técnico recurrente, revisar si otro proyecto
bajo el mismo framework BAGO ya lo resolvió. La solución puede estar a un
grep de distancia.
```

### Cuándo activar el cross-learning

```
SEÑALES de que cross-learning es necesario:
  - Mismo síntoma que recuerdas haber visto en otro proyecto
  - Problema de infraestructura (canvas, audio, routing) ≠ lógica de negocio
  - Llevas >2 intentos sin solución en el proyecto actual
  - El problema tiene una "firma técnica" reconocible (ej: canvas no ocupa pantalla)

NO activar para:
  - Lógica específica de dominio (FX de una escena concreta)
  - Datos o narrativa de proyecto
  - Decisiones arquitectónicas ya congeladas en el proyecto
```

### Protocolo

```bash
# 1. Formular la "firma técnica" del problema
FIRMA="canvas fullscreen pixel art"

# 2. Buscar en el knowledge base si otro proyecto lo resolvió
grep -r "$FIRMA" /Volumes/bago_core/.bago/knowledge/
grep -r "$FIRMA" /path/otro_proyecto/.bago/

# 3. Si hay match → leer la solución completa antes de implementar
# 4. Adaptar la solución al contexto del proyecto actual
# 5. Registrar la transferencia en knowledge/
```

### Caso validado: DERIVE→BIANCA (canvas fullscreen)

```
PROBLEMA en BIANCA: canvas no ocupaba toda la pantalla; había márgenes blancos.
INTENTO inicial: refactorizar a DPR-aware (copiando patrón de DERIVA).
RESULTADO: ❌ Enfoque incorrecto — BIANCA usa pixel art con resolución lógica fija.

CROSS-LEARNING:
  - DERIVA: canvas dinámico DPR (`canvas.width = clientWidth * dpr`)
  - BIANCA: resolución lógica fija 1920×1080, fullscreen via CSS puro
  - Solución correcta BIANCA: `width:100vw; height:100vh; image-rendering:pixelated`
    Sin tocar canvas.width. Meta viewport para móvil.

LECCIÓN: El mismo síntoma (canvas no fullscreen) tiene soluciones OPUESTAS
según la arquitectura del proyecto. Cross-learning debe incluir verificación
de que la arquitectura de origen es compatible con la de destino.
```

### Verificación de compatibilidad arquitectónica

| Dimensión | BIANCA | DERIVA | Compatible |
|-----------|--------|--------|-----------|
| Canvas model | Fixed 1920×1080 | DPR-aware | ❌ NO copiar |
| Input coords | `clientX * canvas.width / rect.width` | `clientX / dpr` | ❌ NO copiar |
| CSS approach | `100vw/100vh` + `pixelated` | Sin CSS especial | ❌ NO copiar |
| FX patterns | `ctx.globalAlpha / shadowBlur` | Mismos contratos | ✅ SÍ copiar |
| BAGO state | `.bago/state/global_state.json` | `.bago/state/global_state.json` | ✅ SÍ copiar |
- [2026-05-05] [test_project] Las entidades fantasma deben usar caching de 200ms para evitar flicker
- [2026-05-19] [unknown] --help
- [2026-05-19] [unknown] --help
- [2026-05-19] [unknown] --help
- [2026-05-19] [unknown] --help
