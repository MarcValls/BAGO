# BAGO — Catálogo de Secuencias

> Recetas de comandos ordenados para cada situación real.  
> Fuente: absorción de 26 instancias `.bago` · compilado 2026-05-05/08

---

## Mapa de decisión rápida

```
¿Primer contacto con un repo?         → SEQ-01  BOOT FRÍO
¿Retomar sesión interrumpida?          → SEQ-02  WARM START
¿Terminar sesión / cambiar proyecto?   → SEQ-03  HARVEST / CIERRE
¿Auditoría antes de release?           → SEQ-04  AUDIT FULL
¿Mejorar calidad de código?            → SEQ-05  QUALITY SWEEP
¿Preparar commit final / versión?      → SEQ-06  RELEASE PREP
¿Ver estado de todos mis proyectos?    → SEQ-07  CONTEXT SCAN
¿Sesión creativa / ideación libre?     → SEQ-08  IDEAS SPRINT
¿Detectar deriva a largo plazo?        → SEQ-09  SUPERVISIÓN EVOLUTIVA
¿Llevar BAGO a un sitio nuevo?         → SEQ-10  TRANSFER / BOOTSTRAP
```

---

## SEQ-01 · BOOT FRÍO
**Cuándo:** Primer contacto con un repositorio desconocido. Sin estado previo.  
**Tiempo estimado:** ≤ 10 min

```bash
# 1. Verificar integridad del pack BAGO
bago validate

# 2. Mapear estructura real del repo
bago map

# 3. Detectar estado y señales de contexto
bago detector

# 4. Consultar workflow apropiado
bago workflow --select W1

# 5. Revisar salud inicial
bago health
```

**Criterio de salida:** Objetivo técnico inicial + restricciones visibles + siguiente paso claro.  
**Nota:** Si `bago detector` retorna señal CONTEXT_MISMATCH → ejecutar W1 antes de cualquier otro workflow.

---

## SEQ-02 · WARM START
**Cuándo:** Retomar sesión interrumpida. El contexto ya existe pero puede estar obsoleto.  
**Tiempo estimado:** ≤ 5 min

```bash
# 1. Ver qué cambió desde la última sesión
bago git

# 2. Detectar señal de contexto actual
bago detector

# 3. Recargar objetivo y tareas pendientes
bago task

# 4. Seleccionar workflow táctico apropiado
bago workflow --select W7
# (W2/W3/W4 según señal del detector)
```

**Criterio de salida:** Objetivo vigente recuperado + siguiente paso inmediato definido.  
**Atajo:** `bago git && bago detector && bago task && echo "Ready."`

---

## SEQ-03 · HARVEST / CIERRE
**Cuándo:** Al finalizar una sesión de trabajo o antes de cambiar de proyecto.  
**Tiempo estimado:** ≤ 5 min

```bash
# 1. Ejecutar cosecha (3 preguntas: decisión / descartado / próximo paso)
bago cosecha

# 2. Revisar estado git
bago git

# 3. Evaluar preparación para commit
bago commit --all
```

**Criterio de salida:** Decisiones capturadas, estado actualizado, próximo paso en `global_state.json`.  
**Regla:** Nunca terminar una sesión productiva sin ejecutar `bago cosecha`. Es lo que construye la memoria acumulada.

---

## SEQ-04 · AUDIT FULL
**Cuándo:** Antes de un release, tras un sprint largo, o cuando hay sospecha de deuda/deriva.  
**Tiempo estimado:** ≤ 15 min

```bash
# 1. Guard anti-drift
bago consistency

# 2. Validación estructural del pack
bago validate

# 3. Auditoría completa (findings JSON)
bago audit --json > bago-findings.json

# 4. Health score
bago health

# 5. Sincerity check (detecta documentación inflada o "ALL PASS" sin evidencia)
bago sincerity

# 6. Stale detector (tools/archivos obsoletos)
bago stale

# 7. Informe consolidado
bago report
```

**Criterio de salida:** 0 errores críticos en findings. README y registry en sync.  
**Nota:** `bago sincerity` es el guardián más importante — detecta cuando el sistema reporta éxito sin evidencia real.

---

## SEQ-05 · QUALITY SWEEP
**Cuándo:** Antes de mergear un PR o después de refactoring significativo.  
**Tiempo estimado:** ≤ 10 min

```bash
# 1. Check de pureza estática
bago check

# 2. Convenciones de nombres
bago naming

# 3. Tipos estáticos
bago types

# 4. Auditoría de dependencias
bago deps

# 5. Orquestador de calidad
bago code-quality . --format json

# 6. Reglas BAGO aplicables
bago rules
```

**Criterio de salida:** Sin hallazgos críticos de naming/types/deps.

---

## SEQ-06 · RELEASE PREP
**Cuándo:** Preparar una versión estable para distribución o commit final de sprint.  
**Tiempo estimado:** ≤ 10 min

```bash
# 1. Guard de consistencia
bago consistency --fix-readme

# 2. Doctor con autofix
bago doctor --fix

# 3. Estabilidad del pack
bago stability

# 4. Regenerar TREE.txt y CHECKSUMS
bago sync

# 5. Evaluación de commit readiness completa
bago commit --all

# 6. Health score final
bago health

# 7. Banner de estado
bago banner
```

**Criterio de salida:** `bago consistency` retorna `{"status": "ok", "errors": 0, "warnings": 0}`.  
**Señal de GO:** `build_status: green` + tests passing + `bago commit --all` sin críticos.

---

## SEQ-07 · CONTEXT SCAN
**Cuándo:** Orientarse en el ecosistema completo. Antes de decidir en qué proyecto trabajar.  
**Tiempo estimado:** ≤ 5 min

```bash
# 1. Listar volumes disponibles
ls /Volumes/

# 2. Encontrar todos los .bago activos
find /Volumes -name ".bago" -maxdepth 5 2>/dev/null

# 3. Leer estado de cada proyecto relevante
for d in /Volumes/Warehouse/AMTEC/DERIVA ~/BAGO; do
  echo "=== $d ===" && cat "$d/.bago/state/global_state.json" 2>/dev/null \
    | python3 -c "import json,sys; d=json.load(sys.stdin); \
      print('project:', d.get('project','?'), '| mode:', d.get('mode','?'))"
done

# 4. Estado del pendrive
bago hello --quick   # desde /Volumes/bago_core
```

**Criterio de salida:** Mapa mental claro de qué proyecto está activo en cada disco.

---

## SEQ-08 · IDEAS SPRINT
**Cuándo:** Sesión de exploración libre / ideación sin estructura rígida.  
**Tiempo estimado:** abierto

```bash
# 1. Detectar señal de contexto
bago detector

# 2. Mapa de contexto actual
bago map

# 3. Generador de ideas (priorizado por contexto)
bago ideas

# 4. Gabinete BAGO (orquesta agentes en paralelo)
bago cabinet

# 5. Si las ideas están maduras → cosecha
bago cosecha
```

**Criterio de salida:** Al menos 1 decisión tomada y 1 opción descartada con razón.  
**Formato de idea útil:** `{objetivo, categoría, prioridad, siguiente paso, esfuerzo estimado}`

---

## SEQ-09 · SUPERVISIÓN EVOLUTIVA
**Cuándo:** Detectar deriva silenciosa en el ecosistema BAGO. Salud a largo plazo.  
**Tiempo estimado:** ≤ 20 min

```bash
# 1. Audit completo del framework
bago audit --json > supervision-audit.json

# 2. Sincerity check
bago sincerity

# 3. Guard de consistencia
bago consistency

# 4. Eficiencia inter-versiones
bago efficiency

# 5. Stale tools
bago stale

# 6. Revisar coherencia entre diseño y comportamiento real
bago rules | grep -E "REGLA|CRÍTICO"

# 7. Reporte consolidado
bago report > supervision-report.md
```

**Criterio de salida:** Sin incoherencias silenciosas entre diseño ↔ contexto ↔ comportamiento.  
**Cuándo ejecutar:** Periódicamente — no solo cuando algo falla. La deriva silenciosa es peor que el error evidente.

---

## SEQ-10 · TRANSFER / BOOTSTRAP NUEVO ENTORNO
**Cuándo:** Llevar BAGO a un disco nuevo, máquina nueva, o proyecto desde cero.  
**Tiempo estimado:** ≤ 15 min

```bash
# 1. Verificar destino y espacio
df -h /Volumes/<DESTINO>

# 2. Copiar framework completo
cp -r ~/BAGO/ /Volumes/<DESTINO>/BAGO/

# 3. En macOS — hacer visibles archivos ocultos en el destino
chflags nohidden /Volumes/<DESTINO>/BAGO/.bago
defaults write com.apple.finder AppleShowAllFiles -bool true && killall Finder

# 4. Inyectar knowledge bases
cp ~/.bago/knowledge/*.md /Volumes/<DESTINO>/BAGO/.bago/knowledge/ 2>/dev/null || true

# 5. Verificar integridad en destino
cd /Volumes/<DESTINO>/BAGO && python3 bago validate

# 6. Consistency check final
cd /Volumes/<DESTINO>/BAGO && python3 bago consistency
```

**Criterio de salida:** `bago validate` OK + `bago consistency` 0 errors en el nuevo entorno.  
**Nota pendrive:** El pendrive `/Volumes/BAGO` + `/Volumes/bago_core` usa este patrón. El `INICIAR_BAGO.command` permite arranque sin instalación.

---

## Patrones de comando reutilizables

### Validación encadenada (pipeline completo)
```bash
bago validate && bago consistency && bago audit --json | python3 -c \
  "import json,sys; d=json.load(sys.stdin); \
   crits=[f for f in d.get('findings',[]) if f.get('severity') in ('critical','error')]; \
   print(f'{len(crits)} críticos'); sys.exit(1 if crits else 0)"
```

### Warm start rápido
```bash
bago git && bago detector && bago task && echo "Ready."
```

### Diagnóstico de salud completo
```bash
bago health && bago sincerity && bago stale
```

---

*Fuente: sequences_catalog.md (knowledge base GitHub) · Adaptado para BAGO v3.3.0 · 2026-05-08*
