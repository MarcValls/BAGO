# BAGO — Catálogo de Secuencias de Comandos
**Versión:** 1.0  
**Creado:** 2026-05-05  
**Fuente:** Absorción multi-disco (SistemaSSD · Warehouse · bago_fw)  
**Propósito:** Aprender secuencias concretas y ordenadas para tareas reales, con perspectivas de cada almacenamiento.

---

## PERSPECTIVAS POR DISCO

Cada disco aporta un ángulo distinto al uso de BAGO:

| Disco | Contenidos clave | Perspectiva |
|-------|-----------------|-------------|
| **SistemaSSD** `~/bago-framework`, `Desktop/BAGO_CAJAFISICA` | CLI 36 comandos, testing, extensiones, ideas JSON | Herramienta operativa, laboratorio |
| **Warehouse** `DERIVA`, `CESAR_WOODS`, `TPV`, `ABRIL2026` | Proyectos reales multi-dominio, supervisor GUIA_VERTICE, repo_context_guard | Producción, referencia congelada, metacontrol |
| **bago_fw** `/Volumes/bago_fw` | Framework portable + 6 knowledge bases BIANCA + CI real | Transporte, autodistribución, entorno limpio |

---

## SECUENCIAS

---

### SEQ-01 · BOOT FRÍO
**Cuándo:** Primer contacto con un repositorio desconocido. Sin estado previo.  
**Origen:** W1_COLD_START + `inspect_workflow.py` (TPV/Warehouse)  
**Tiempo estimado:** ≤ 10 min

```bash
# 1. Verificar integridad del pack BAGO
bago validate

# 2. Crear/actualizar fingerprint del repo (evita bucles de contexto heredado)
python3 .bago/tools/repo_context_guard.py record

# 3. Mapear estructura real del repo
bago map

# 4. Detectar estado y señales de contexto
bago detector

# 5. Consultar workflow apropiado
bago workflow --select W1

# 6. Revisar salud inicial
bago health --json
```

**Criterio de salida:** Objetivo técnico inicial + restricciones visibles + siguiente paso claro sin ambigüedad.  
**Nota de campo (TPV):** Si `repo_context_guard` detecta cambio de repo → ejecutar W1 antes de cualquier otro workflow. Bloqueador de seguridad.

---

### SEQ-02 · WARM START
**Cuándo:** Retomar sesión interrumpida. El contexto ya existe pero puede estar obsoleto.  
**Origen:** W7_FOCO_SESION + `launch_workflow_maestro.sh` (TPV)  
**Tiempo estimado:** ≤ 5 min

```bash
# 1. Verificar que el contexto es del repo actual (no arrastrado de otro)
python3 .bago/tools/repo_context_guard.py check

# 2. Ver qué cambió desde la última sesión
bago git

# 3. Detectar señal de contexto actual
bago detector

# 4. Recargar objetivo y tareas pendientes
bago task

# 5. Seleccionar workflow táctico apropiado
bash .bago/tools/launch_workflow_maestro.sh --tactical W2
# (o W3/W4/W5 según señal del detector)
```

**Criterio de salida:** Objetivo vigente recuperado + siguiente paso inmediato definido.  
**Nota de campo (DERIVA):** Sprint activo → `bago git` muestra el último commit. Combinar con lectura de `global_state.json` para ver `active_workflow`.

---

### SEQ-03 · HARVEST / CIERRE
**Cuándo:** Al finalizar una sesión de trabajo, exploración libre, o antes de cambiar de proyecto.  
**Origen:** W5_CIERRE + W9_COSECHA + `cosecha.py`  
**Tiempo estimado:** ≤ 5 min

```bash
# 1. Verificar señal de cosecha (si devuelve HARVEST → proceder)
python3 .bago/tools/context_detector.py

# 2. Ejecutar cosecha interactiva (3 preguntas: decisión / descartado / próximo paso)
bago cosecha

# 3. Checklist de cierre v2
bago v2

# 4. Revisar estado git
bago git

# 5. Evaluar preparación para commit
bago commit --all

# 6. Generar informe de cierre de sesión
bago session_close
```

**Criterio de salida:** Decisiones capturadas, estado actualizado, próximo paso registrado en `global_state.json`.  
**Nota de campo (BAGO_CAJAFISICA):** La cosecha JSON de ideas (formato `caos_game_ideas.json`) es el artefacto más valioso. Guardar en `.bago/ideas/` o `.bago/state/`.

---

### SEQ-04 · AUDIT FULL
**Cuándo:** Antes de un release, tras un sprint largo, o cuando hay sospecha de drift/deuda.  
**Origen:** CI workflow real + `bago_consistency_check.py` + audit findings  
**Tiempo estimado:** ≤ 15 min

```bash
# 1. Guard anti-drift (CI, preflight, README, badge)
bago consistency

# 2. Validación estructural del pack
bago validate

# 3. Auditoría completa (findings JSON)
bago audit --json > bago-findings.json

# 4. Health score
bago health --json > bago-health.json

# 5. Sincerity check (detecta sycophancy en docs .md)
bago sincerity

# 6. Stale detector (tools obsoletas)
bago stale --json

# 7. Informe consolidado Markdown
bago report

# 8. Evaluación de commit readiness
bago commit --all
```

**Criterio de salida:** 0 errores críticos en `bago-findings.json`. README y registry en sync.  
**Nota de campo (pendrive fix):** El guard `bago consistency` bloquea CI si hay drift. Siempre ejecutar primero.

---

### SEQ-05 · QUALITY SWEEP
**Cuándo:** Antes de mergear un PR o después de refactoring significativo.  
**Origen:** W3_REFACTOR + code-quality orchestrator  
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

# 5. Orquestador de calidad (agentes especializados)
bago code-quality . --format json

# 6. Reglas BAGO aplicables
bago rules
```

**Criterio de salida:** No quedan hallazgos críticos de naming/types/deps; `code-quality` debe registrarse con salida revisada.  
**Nota de campo (CESAR_WOODS):** Esta secuencia es la que usaba la baseline v2.2.1 para validaciones de referencia. Solo lectura, sin modificar código.

---

### SEQ-06 · RELEASE PREP
**Cuándo:** Preparar una versión estable para distribución o commit final de sprint.  
**Origen:** `bago sync` + `ci_generator.py` + DERIVA sprint pattern  
**Tiempo estimado:** ≤ 10 min

```bash
# 1. Guard de consistencia (README, CI, registry en sync)
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
bago health --json

# 7. Banner de estado
bago banner
```

**Criterio de salida:** `bago consistency --json` retorna `{"status": "ok", "errors": 0, "warnings": 0}`.  
**Nota de campo (DERIVA):** `build_status: green` + tests passing + `bago commit --all` sin críticos = release ready.

---

### SEQ-07 · CONTEXT SCAN (cross-disk)
**Cuándo:** Orientarse en el ecosistema completo de discos. Antes de decidir en qué proyecto trabajar.  
**Origen:** Esta sesión — absorción multi-disco  
**Tiempo estimado:** ≤ 5 min

```bash
# 1. Listar volumes disponibles
ls /Volumes/

# 2. Encontrar todos los .bago activos en Warehouse
find /Volumes/Warehouse -name ".bago" -maxdepth 5 2>/dev/null

# 3. Leer estado de cada proyecto relevante
for d in /Volumes/Warehouse/AMTEC/DERIVA /Volumes/Warehouse/CESAR_WOODS; do
  echo "=== $d ===" && cat "$d/.bago/state/global_state.json" 2>/dev/null \
    | python3 -c "import json,sys; d=json.load(sys.stdin); \
      print('project:', d.get('project','?'), '| mode:', d.get('mode','?'), \
            '| workflow:', d.get('active_workflow','?'))"
done

# 4. Estado del pendrive
cat /Volumes/bago_fw/bago-framework/.bago/state/ESTADO_BAGO_ACTUAL.md 2>/dev/null | head -30

# 5. Verificar framework local
bago dashboard
```

**Criterio de salida:** Mapa mental claro de qué proyecto está activo en cada disco y su estado.  
**Perspectivas encontradas:**
- Warehouse/DERIVA → proyecto de producción, sprint tracking, tests
- Warehouse/CESAR_WOODS → baseline congelada v2.2.1, solo referencia
- Warehouse/TPV → dominio empresa/contabilidad con launcher maestro
- Warehouse/ABRIL2026 → GUIA_VERTICE (supervisión evolutiva)
- bago_fw → framework portable + knowledge bases BIANCA

---

### SEQ-08 · IDEAS SPRINT
**Cuándo:** Sesión de exploración libre / ideación sin estructura rígida (modo W8/W6).  
**Origen:** W6_IDEACION + W8_EXPLORACION + `caos_game_ideas.json` (BAGO_CAJAFISICA)  
**Tiempo estimado:** abierto

```bash
# 1. Detectar si hay contexto maduro para explorar (señal EXPLORE o FREE)
python3 .bago/tools/context_detector.py

# 2. Mapa de contexto actual (qué existe, qué falta)
bago map

# 3. Generador de ideas W2 (emite ideas concretas con alcance)
bago ideas

# 4. Gabinete BAGO (orquesta agentes en paralelo, informe unificado)
bago cabinet

# 5. Router lenguaje natural → tool adecuada
bago ask "¿qué herramienta uso para [objetivo]?"

# 6. Si las ideas están maduras → cosecha
bago cosecha
```

**Criterio de salida:** Al menos 1 decisión y 1 opción descartada con razón. Formato JSON en `.bago/ideas/`.  
**Nota de campo (CAoS project):** Guardar ideas en formato estructurado: `{id, title, category, priority, status, description, implementation, files, effort}`. Reutilizable como backlog.

---

### SEQ-09 · SUPERVISIÓN EVOLUTIVA
**Cuándo:** Detectar drift silencioso en el ecosistema BAGO. Salud a largo plazo.  
**Origen:** GUIA_VERTICE (ABRIL2026/Warehouse) — rol de metacontrol  
**Tiempo estimado:** ≤ 20 min

```bash
# 1. Audit completo del framework
bago audit --json > supervision-audit.json

# 2. Sincerity check (detecta documentación sycophantic/inflada)
bago sincerity

# 3. Guard de consistencia
bago consistency --json

# 4. Eficiencia inter-versiones
bago efficiency

# 5. Stale tools
bago stale --json

# 6. Revisar si el modo actual del sistema es coherente con el objetivo
# (GUIA_VERTICE pregunta: ¿el sistema opera como fue diseñado?)
bago rules | grep -E "REGLA|CRÍTICO"

# 7. Reporte consolidado
bago report > supervision-report.md
```

**Criterio de salida:** Sin incoherencias silenciosas entre diseño ↔ contexto ↔ comportamiento.  
**Rol clave:** GUIA_VERTICE (`.bago/supervision/GUIA_VERTICE.md`) — no ejecuta, supervisa. Vigila rigidez, deriva, pérdida de trazabilidad.  
**Nota de campo:** Ejecutar esta secuencia periódicamente, no solo cuando algo falla.

---

### SEQ-10 · TRANSFER / BOOTSTRAP NUEVO ENTORNO
**Cuándo:** Llevar BAGO a un disco nuevo, máquina nueva, o proyecto desde cero.  
**Origen:** Transferencia a `/Volumes/bago_fw` de esta sesión  
**Tiempo estimado:** ≤ 15 min

```bash
# 1. Verificar destino y espacio
df -h /Volumes/<DESTINO>

# 2. Copiar framework completo
cp -r ~/bago-framework/ /Volumes/<DESTINO>/bago-framework/

# 3. Hacer visibles archivos ocultos en el destino (macOS)
chflags nohidden /Volumes/<DESTINO>
chflags nohidden /Volumes/<DESTINO>/bago-framework/.bago
defaults write com.apple.finder AppleShowAllFiles -bool true
kill -HUP $(pgrep -x Finder)

# 4. Inyectar knowledge bases del proyecto activo
cp ~/.bago_knowledge/*.md /Volumes/<DESTINO>/bago-framework/.bago/knowledge/ 2>/dev/null || true

# 5. Escribir estado de transferencia
cat > /Volumes/<DESTINO>/bago-framework/.bago/state/ESTADO_BAGO_ACTUAL.md << 'EOF'
# Estado BAGO — Transferencia
- Origen: [ORIGEN]
- Destino: [DESTINO]
- Fecha: [FECHA]
- Framework: 2.5-stable
- Knowledge bases transferidas: [LISTA]
EOF

# 6. Verificar integridad en destino
cd /Volumes/<DESTINO>/bago-framework && python3 bago validate

# 7. Consistency check final
cd /Volumes/<DESTINO>/bago-framework && python3 .bago/tools/bago_consistency_check.py
```

**Criterio de salida:** `bago validate` OK + `bago consistency` 0 errors en el nuevo entorno.  
**Nota de campo:** El pendrive `/Volumes/bago_fw` usa este patrón. El `play.command` (si existe) permite auto-arranque sin instalación.

---

## MAPA DE DECISIÓN: ¿QUÉ SECUENCIA USAR?

```
¿Primer contacto con repo?
  → SEQ-01 BOOT FRÍO

¿Retomar sesión anterior?
  → SEQ-02 WARM START

¿Terminar sesión / ir a otro proyecto?
  → SEQ-03 HARVEST / CIERRE

¿Auditoría antes de release o tras sprint?
  → SEQ-04 AUDIT FULL

¿Mejorar calidad de código?
  → SEQ-05 QUALITY SWEEP

¿Preparar commit final o versión?
  → SEQ-06 RELEASE PREP

¿No sé en qué estado están todos mis proyectos?
  → SEQ-07 CONTEXT SCAN

¿Sesión creativa / exploración libre?
  → SEQ-08 IDEAS SPRINT

¿El framework lleva tiempo funcionando y quiero chequear deriva?
  → SEQ-09 SUPERVISIÓN EVOLUTIVA

¿Necesito BAGO en un sitio nuevo?
  → SEQ-10 TRANSFER
```

---

## HERRAMIENTAS ÚNICAS POR DISCO

### Warehouse — herramientas no presentes en framework base

| Herramienta | Ruta | Función |
|------------|------|---------|
| `repo_context_guard.py` | TPV/.bago/tools/ | Fingerprint de repo, detecta cambio de contexto |
| `launch_workflow_maestro.sh` | TPV/.bago/tools/ | Lanzador con validación canónica + `--tactical W1..W6` |
| `inspect_workflow.py` | TPV/.bago/tools/ | Guía interactiva de workflows con preguntas clave |
| `generate_bago_evolution_report.py` | TPV/.bago/tools/ | Reporte de evolución del framework |
| `stability_summary.py` | TPV/.bago/tools/ | Resumen de estabilidad |
| `GUIA_VERTICE.md` | ABRIL2026/.bago/supervision/ | Rol de supervisión evolutiva |

### SistemaSSD — patrones locales

| Artefacto | Ruta | Función |
|-----------|------|---------|
| `caos_game_ideas.json` | BAGO_CAJAFISICA/.bago/ideas/ | Formato JSON de ideas con backlog estructurado |
| `bash-runner` extension | BAGO_CAJAFISICA/.bago/extensions/ | Extensión CLI custom |

### bago_fw — knowledge bases portables

| Documento | Función |
|-----------|---------|
| `bago_universe.md` | Catálogo de 26 instancias BAGO (13 agentes, 16 workflows, 80+ tools) |
| `toolkit_bianca.md` | Métodos de generación de sprites M1–M6 |
| `sequences_catalog.md` | **Este documento** |
| `engine_learnings_bianca.md` | Learnings del motor paperdoll |
| `fx_inventory_bianca.md` | Inventario de efectos visuales |
| `audio_integration_bianca.md` | Integración de audio |
| `session_arc_bianca.md` | Arco de sesiones del proyecto |

---

## PATRONES DE COMANDO REUTILIZABLES

### Patrón: Pipeline de validación encadenada
```bash
bago validate && bago consistency && bago audit --json | python3 -c \
  "import json,sys; d=json.load(sys.stdin); \
   crits=[f for f in d.get('findings',[]) if f.get('severity') in ('critical','error')]; \
   print(f'{len(crits)} críticos'); sys.exit(1 if crits else 0)"
```

### Patrón: Contexto multi-proyecto en una línea
```bash
find /Volumes -name "global_state.json" -maxdepth 7 2>/dev/null | \
  xargs -I{} python3 -c \
  "import json,sys; d=json.load(open('{}'));print('{}: ', d.get('project','?'), d.get('mode','?'))" \
  2>/dev/null
```

### Patrón: Warm start rápido con resumen
```bash
bago git && bago detector && bago task && echo "Ready."
```

### Patrón: Ideas → backlog JSON
```bash
bago ideas | python3 -c "
import sys, json, datetime
ideas = sys.stdin.read()
entry = {'ts': datetime.datetime.now().isoformat()[:10], 'raw': ideas}
existing = json.loads(open('.bago/ideas/backlog.json').read()) if __import__('os').path.exists('.bago/ideas/backlog.json') else []
existing.append(entry)
json.dump(existing, open('.bago/ideas/backlog.json','w'), indent=2, ensure_ascii=False)
print('Guardado en .bago/ideas/backlog.json')
"
```

---

## NOTAS DE CAMPO CROSS-DISCO

1. **Repo context guard (TPV):** Antes de cualquier workflow en un nuevo repo, ejecutar `repo_context_guard.py record`. Si ya hay estado y cambia el repo → `check` detecta mismatch y fuerza W1.

2. **Baseline congelada (CESAR_WOODS):** v2.2.1 es la referencia de comparación. Si algo en el framework actual se comporta raro, comparar contra CESAR_WOODS. Solo tiene `validate_*.py` — no modifica nada.

3. **Sprint tracking (DERIVA):** El campo `completed_interventions[]` en `global_state.json` es el historial de sprint. Cada sesión añade entradas con prefijo `--- SPRINT N ---`. Patrón replicable.

4. **Ideas estructuradas (BAGO_CAJAFISICA):** El formato `{id, title, category, priority, status, description, implementation, files, effort}` es el más completo para backlog de ideas. Reutilizar para cualquier proyecto.

5. **GUIA_VERTICE (ABRIL2026):** No es un agente operativo — es un supervisor. No ejecuta código. Analiza si el sistema opera como fue diseñado. Activar periódicamente (SEQ-09).

6. **bago_fw como fuente de verdad portable:** Si hay conflicto entre versiones de .bago en distintos discos, el framework en `/Volumes/bago_fw` es el más reciente y auditado (2.5-stable + todos los fixes).
