# workflow_cross_learning · Transferencia de Conocimiento Entre Proyectos

**Versión:** 1.0  
**Creado:** 2026-05-05  
**Origen:** Sesión BIANCA sprint 288 — resolución de canvas fullscreen con lección de DERIVA  
**Clasificación:** `[A] Adaptativo` → `[G] Generativo` → `[O] Organizativo`

---

## 1. Para qué sirve

Transfiere conocimiento operativo (soluciones, anti-patrones, arquitecturas) desde un proyecto
donde se resolvió un problema hacia otro proyecto que enfrenta el mismo síntoma.

**Problema que resuelve:**
> Un agente puede pasar horas resolviendo un problema que ya fue resuelto en otro proyecto
> bajo el mismo framework. Sin cross-learning activo, ese conocimiento se pierde entre sesiones.

**Cuándo activar:**
- Síntoma conocido que recuerda una solución de otro proyecto
- Problema de infraestructura (canvas, audio, routing, build) — no lógica de dominio
- Llevas >2 intentos sin solución en el proyecto actual
- El problema tiene "firma técnica" reconocible

**Cuándo NO activar:**
- Lógica específica de dominio (FX de una escena concreta)
- Datos, narrativa o canon de un proyecto específico
- Decisiones arquitectónicas ya congeladas en el proyecto actual

---

## 2. Protocolo de ejecución

### Fase 1 — [B] Identificar la firma técnica

```
1. Formular el síntoma en términos técnicos neutrales (sin nombres de proyecto)
   Ejemplo: "canvas no ocupa toda la pantalla" → firma: "canvas fullscreen"

2. Buscar en knowledge/ del BAGO core:
   grep -r "firma_técnica" /Volumes/bago_core/.bago/knowledge/
   
3. Buscar en el proyecto fuente potencial:
   find /ruta/otro_proyecto/.bago/knowledge/ -name "*.md" | xargs grep -l "firma"
```

### Fase 2 — [A] Verificar compatibilidad arquitectónica

**CRÍTICO:** La misma sintomatología puede tener soluciones OPUESTAS según la arquitectura.

```
Checklist de compatibilidad:
□ ¿El modelo de renderizado es el mismo? (fixed vs. DPR-aware, CSS vs. canvas.width)
□ ¿El sistema de coordenadas es compatible?
□ ¿Las dependencias de framework son las mismas?
□ ¿Las frozen decisions del proyecto destino permiten este cambio?

Si alguna caja es ❌ → adaptar, no copiar directamente
```

### Fase 3 — [G] Aplicar la solución adaptada

```
1. Implementar con los parámetros del proyecto DESTINO, no del origen
2. Build inmediato de verificación (build roto = adaptación incorrecta)
3. Si el build falla → revisar la diferencia arquitectónica que se pasó por alto
```

### Fase 4 — [O] Codificar el aprendizaje

```
# Añadir a knowledge/ del BAGO core:
# - El caso resuelto (firma, origen, destino, solución adaptada)
# - La diferencia arquitectónica clave
# - Lo que NO se debe copiar directamente

# Actualizar global_state.json:
# - knowledge_base.last_harvest con la fecha actual
# - notes con resumen de la transferencia
```

---

## 3. Caso validado (2026-05-05)

| Dimensión | Valor |
|-----------|-------|
| Firma técnica | "canvas no ocupa toda la pantalla" |
| Proyecto origen | DERIVA |
| Proyecto destino | BIANCA |
| Síntoma | Márgenes blancos alrededor del canvas |
| Intento inicial (incorrecto) | Refactorizar a DPR-aware (copiando patrón DERIVA) |
| Solución correcta para BIANCA | CSS `width:100vw; height:100vh; image-rendering:pixelated` + meta viewport |
| Por qué son diferentes | BIANCA: resolución lógica fija 1920×1080. DERIVA: dinámica DPR-aware |
| Build resultado | ✅ Sprint 288 — 323.29 KB |

**Lección clave:** Mismo síntoma → soluciones OPUESTAS. El cross-learning siempre requiere
verificar compatibilidad arquitectónica antes de aplicar la solución del proyecto origen.

---

## 4. Tabla de compatibilidad BIANCA vs DERIVA

| Aspecto | BIANCA | DERIVA | ¿Transferible? |
|---------|--------|--------|---------------|
| Canvas model | Fixed 1920×1080 | DPR-aware dinámico | ❌ NO |
| Fullscreen | CSS `100vw/100vh` | `canvas.width = clientWidth * dpr` | ❌ NO |
| Input coords | `clientX * W / rect.width` | `clientX / dpr` | ❌ NO |
| Nitidez | `image-rendering: pixelated` | `ctx.setTransform(dpr,0,0,dpr,0,0)` | ❌ NO |
| FX contratos ctx | `globalAlpha=1`, `shadowBlur=0` al cerrar | Mismos contratos | ✅ SÍ |
| BAGO state | `global_state.json` + sprints | Mismo esquema | ✅ SÍ |
| Edit safety | Build tras edit estructural | Build tras edit estructural | ✅ SÍ |

---

## 5. Relación con otros workflows

| Workflow | Relación |
|----------|----------|
| `W9_COSECHA.md` | Cross-learning puede activarse después de W9 (post-harvest) |
| `W1_COLD_START.md` | Cold start de un nuevo proyecto debe revisar knowledge/ primero |
| `W10_AUDITORIA_SINCERIDAD.md` | Cross-learning debe incluir auditoría de FDs del proyecto destino |
| `workflow_ejecucion.md` | La aplicación de la solución sigue el flujo de ejecución estándar |
