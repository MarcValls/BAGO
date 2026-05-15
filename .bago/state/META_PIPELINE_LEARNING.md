# META-PIPELINE: Aprendizaje de Construccion de Pipelines BAGO

## Contexto
Construido: 2026-05-15
Pipeline: BAGO Orchestrator 4-fases (Router -> Ejecutor -> Reviewer -> Consenso)
Dominio: Orquestacion de modelos LLM para tareas arbitrarias

---

## 0. FASE CERO: DESCUBRIR ANTES DE DISENAR

**Principio:** Nunca disenar un pipeline sin saber primero que ya existe.

### 0.1 Inventario automatico
Antes de cualquier decision, ejecutar:
```bash
python .bago/tools/bago_inventory.py --suggest {task_type}
```

Esto devuelve:
- Herramientas existentes que coinciden con keywords del task_type
- Workflows previos que resuelven problemas similares
- Agentes y roles con capabilities relevantes
- Modelos optimos para ese dominio

### 0.2 Jerarquia de reutilizacion (orden de preferencia)
1. **Workflow existente** — si hay un workflow `.md` o `.json` que resuelve el problema, reusarlo
2. **Tool module existente** — si hay funciones en `.bago/tools/` que hacen lo pedido, importarlas
3. **Agent role existente** — si hay un rol en `.bago/roles/` o `.bago/mcp/` con las tools necesarias, asignarlo
4. **Fragmento de pipeline** — si una fase de otro pipeline sirve (ej: router, reviewer), importarla
5. **Crear nuevo** — solo si nada de lo anterior cubre el caso

### 0.3 Reglas de decision
| Si encuentras... | Entonces... |
|------------------|-------------|
| Workflow completo | Reusar workflow, no crear pipeline nuevo |
| Tool + contrato | Integrar tool en pipeline existente, no reescribir |
| Rol con tools | Asignar rol al agente ejecutor, no crear rol nuevo |
| Modelo optimo para tarea | Usar modelo del catalogo, no buscar externo |
| Nada relevante | Crear pipeline nuevo con fases genericas |

### 0.4 Ejemplo real (musica)
Task: "transponer partitura de Mi mayor a Re mayor"
```
$ bago_inventory.py --suggest music

[tool] bago_music.py              -> reutilizar: interval_to_semitones
[tool] musicxml_transpose.py     -> reutilizar: transpose_file
[tool] musicxml_validate.py      -> reutilizar: validate
[tool] musicxml_render.py        -> reutilizar: render_score
[workflow] music-score-transposition.md -> existe workflow documentado
[role] GENERADOR_Contenido (mcp) -> asignar para tareas music
[model] gpt-5.3-codex (codex)    -> usar para complejas, qwen25-mini para simples
```
Decision: No crear pipeline de musica desde cero. Extender workflow existente con exportador PDF.


### 0.5 Proyectos fuera del arbol BAGO
BAGO debe poder ejecutarse sobre proyectos que NO esten en `BAGO\projects\`.
El locator detecta `.bago\` en el CWD; si no existe, actua como framework puro
sobre el directorio actual sin depender de estar dentro del arbol BAGO.

## 1. PROCESO DE CONSTRUCCION (Como se llego aqui)

### Fase A: Exploracion y descubrimiento
1. **Auditar codigo existente**: Revisar `.bago/tools/` para ver que piezas ya existen
2. **Leer handoff**: Si hay un handoff de otro agente, usarlo como punto de partida
3. **Identificar gaps**: Que falta para que funcione? (ej: `Invoke-BagoPipeline` no estaba implementado)

### Fase B: Diseno del pipeline
**Principio**: Dividir en fases independientes que puedan reutilizarse

| Fase | Input | Output | Reutilizable? |
|------|-------|--------|---------------|
| Router | tarea (str) | agente, modelo, tipo | SI -> `bago_dynamic_router.py` |
| Ejecutor | agente, modelo, prompt | output, exit_code | SI -> `_execute()` + `_run_gh_copilot()` + `_run_ollama()` |
| Reviewer | output, tarea | review_text | SI -> `_review()` |
| Consenso | output, review, contrato | resultado validado | SI -> `_validate_contract()` |

### Fase C: Implementacion
**Regla**: Implementar primero en Python (logica compleja), luego wrapper en PowerShell (interfaz usuario)

1. Crear motor Python (`bago_pipeline.py`) con:
   - Fases como funciones independientes
   - Timeouts adaptativos por tipo de tarea
   - Fallback automatico si fase falla
   - Registro de ejecuciones para aprendizaje

2. Crear wrapper PowerShell (`bago.ps1`) con:
   - Pre-router rapido para calcular timeout del job
   - `Start-Job` para no bloquear terminal
   - Parseo de resultado JSON
   - Visualizacion bonita de fases

### Fase D: Adaptacion (motor B/A)
**Principio**: No hardcodear timeouts ni agentes fijos

- `bago_adaptive_engine.py` registra cada ejecucion
- Calcula percentil 80 de duraciones por (tipo, agente)
- Ajusta timeouts automaticamente
- Penaliza agentes con fallos consecutivos

### Fase E: Validacion
- Tests unitarios: `test_bago_brutal.py` (10/10)
- Tests de integracion: `test_music_integration.py` (9/9)
- Pruebas manuales con tareas reales

---

## 2. PATRONES REUTILIZABLES

### Patron 1: "Pipeline como DAG lineal"
```
tarea -> [F1] -> [F2] -> [F3] -> [F4] -> resultado
        Router   Ejecutor  Reviewer  Consenso
```
**Aplicable cuando**: Una tarea se puede descomponer en pasos secuenciales con validacion entre medias.

### Patron 2: "Executor con fallback"
```python
def ejecutar(agente, modelo, prompt):
    result = ejecutor_principal(agente, modelo, prompt)
    if not result.success:
        result = ejecutor_fallback("copilot", "claude-sonnet", prompt)
    return result
```
**Aplicable cuando**: Hay multiples proveedores que pueden hacer lo mismo pero con distinta fiabilidad/coste.

### Patron 3: "Reviewer cruzado"
```python
def revisar(output, tarea):
    reviewer = "copilot" if ejecutor != "copilot" else "ollama"
    return ejecutar(reviewer, modelo_reviewer, prompt_revision)
```
**Aplicable cuando**: Se necesita validacion independiente del resultado.

### Patron 4: "Contrato de validacion"
```python
def validar_contra_contrato(resultado, contract_file):
    contract = json.load(contract_file)
    for field in contract.required:
        assert field in resultado
```
**Aplicable cuando**: Se define un esquema de resultado que debe cumplirse.

### Patron 5: "Wrapper silencioso de CLI"
```python
def run_silently(cmd, timeout, env=None):
    out = tempfile()
    err = tempfile()
    proc = subprocess.Popen(cmd, stdout=out, stderr=err)
    proc.wait(timeout)
    return {"output": read(out), "error": read(err), "exit_code": proc.returncode}
```
**Aplicable cuando**: Se necesita ejecutar una herramienta CLI en segundo plano sin ventanas.

### Patron 6: "Pre-router rapido"
```powershell
$taskType = python -c "from router import dynamic_route; print(dynamic_route('$task')['task_type'])"
$timeout = switch ($taskType) { "music" { 90 } "code" { 50 } default { 40 } }
```
**Aplicable cuando**: El wrapper necesita saber el timeout antes de lanzar el job.

---

## 3. FRAGMENTOS DE HERRAMIENTAS REUTILIZABLES

### 3.1 Ejecutor silencioso (gh copilot)
- Ubicacion: `bago_pipeline.py::_run_gh_copilot()`
- Fragmentos: `tempfile`, `subprocess.Popen`, `proc.wait(timeout)`, cleanup
- Reusable para: Cualquier CLI que necesite ejecutarse sin ventana

### 3.2 Ejecutor silencioso (ollama)
- Ubicacion: `bago_pipeline.py::_run_ollama()`
- Mismo patron que 3.1 pero con comando diferente

### 3.3 Motor adaptativo
- Ubicacion: `bago_adaptive_engine.py`
- Fragmentos: `_load_history()`, `_save_event()`, `adaptive_timeout()`, `agent_score()`
- Reusable para: Cualquier pipeline que necesite ajustar timeouts o elegir agentes basado en historial

### 3.4 Router dinamico
- Ubicacion: `bago_dynamic_router.py`
- Fragmentos: `_task_type()`, `_match_rule()`, `_agent_role()`
- Reusable para: Cualquier pipeline que clasifique tareas y asigne roles

---

## 4. ERRORES Y SOLUCIONES (Aprendizaje por fallo)

| Error | Causa | Solucion | Patron extraido |
|-------|-------|----------|-----------------|
| `Invoke-BagoPipeline` rompia `bago.ps1` | SyntaxError en PowerShell por escaping de `$` | Guardar script temporal, leer con `Get-Content`, reensamblar | **Patron: "Escritura atomica"** — no modificar archivos grandes inline, escribir bloques completos |
| gh copilot timeout (12s) | Comando interactivo no puede usar `Start-Process` con stdin | Usar `Start-Job` de PowerShell como wrapper | **Patron: "Job como proxy"** — cuando un proceso necesita stdin interactivo, usar job de PS |
| UnicodeEncodeError en Python | Consola Windows usa cp1252, no UTF-8 | `sys.stdout.reconfigure(encoding="utf-8")` al inicio del archivo | **Patron: "UTF-8 primero"** |
| gh copilot devolvia error "too many arguments" | `-p` espera string con espacios como un solo arg | Quitar comillas internas, pasar prompt como arg simple | **Patron: "Escaping minimalista"** — no over-escapar argumentos CLI |
| Partituras cortadas en PDF | Un solo SVG con todos los compases | Dividir en divs separados con `page-break-inside: avoid` | **Patron: "Contenedor atomico"** — cada unidad visual en su propio contenedor para evitar cortes |

---

## 5. COMO CONSTRUIR UN NUEVO PIPELINE (Checklist)

### Paso -1: Descubrir (antes de decidir)
- Ejecutar `bago_inventory.py --suggest {task_type}`
- Revisar workflows existentes en `.bago/workflows/`
- Revisar tools en `.bago/tools/` que coincidan con keywords
- Revisar roles en `.bago/roles/` y `.bago/mcp/`
- Revisar modelos en `.bago/state/model_providers.json`
- **Decision:** reutilizar workflow completo / extender tool / crear nuevo

### Paso 0: Definir contrato
- Crear `NUEVO_contract.json` con schema de entrada/salida
- Definir que campos son required en el resultado
- Verificar si ya existe un contrato compatible en `.bago/agents/`

### Paso 1: Disenar fases (solo si se crea nuevo)
- Cuantas fases necesita la tarea?
- Para cada fase: que herramienta la ejecuta? cual es el fallback?
- Importar fases de otros pipelines si son genericas (router, reviewer)

### Paso 2: Disenar fases
- Cuantas fases necesita la tarea?
- Para cada fase: que herramienta la ejecuta? cual es el fallback?

### Paso 3: Implementar motor Python
- Crear `NUEVO_pipeline.py`
- Importar fragmentos reutilizables del motor existente
- Implementar fases como funciones independientes

### Paso 4: Integrar motor B/A
- Importar `adaptive_timeout`, `record_execution`
- Definir timeouts base por tipo de tarea en `_get_timeouts()`

### Paso 5: Crear wrapper PowerShell
- Pre-router para calcular timeout del job
- `Start-Job` para ejecucion en segundo plano
- Parseo y visualizacion de resultado

### Paso 6: Validar
- Tests unitarios en `tests/test_NUEVO.py`
- Tests con fixtures de prueba
- Pruebas manuales con tareas reales

---

## 6. META-APRENDIZAJE: Como BAGO aprende a construir pipelines

### Regla 1: Composicion sobre creacion
Cuando se pide un nuevo pipeline, BAGO debe:
1. Listar herramientas existentes en `.bago/tools/`
2. Buscar fragmentos que encajen (router, ejecutor, validador)
3. Componer antes que crear desde cero

### Regla 2: Contrato antes que codigo
Siempre definir el schema de entrada/salida antes de implementar. Esto permite:
- Validar automaticamente el resultado
- Conectar con otros pipelines (output de uno = input de otro)

### Regla 3: Fase independiente = funcion pura
Cada fase debe ser una funcion con:
- Input claro (tipos definidos)
- Output claro (dict con `success`, `output`, `error`, `duration_ms`)
- Sin side effects (excepto registro en historial)

### Regla 4: Fallback es obligatorio
Toda fase que dependa de un agente externo debe tener fallback a otro agente disponible.

### Regla 5: Historial es oro
Registrar cada ejecucion permite:
- Ajustar timeouts (no adivinar)
- Penalizar agentes inestables
- Recomendar mejores agentes para tipo de tarea

---

## 7. APLICACION A OTROS DOMINIOS

| Dominio | Fases reutilizables | Nuevas fases necesarias |
|---------|--------------------|-------------------------|
| **Musica** (ya construido) | Router, Ejecutor, Consenso | Renderer VexFlow, Exportador PDF |
| **Codigo** | Router (type=code), Ejecutor, Reviewer | Linter, Tests, Diff checker |
| **Documentacion** | Router (type=content), Ejecutor | Markdown renderer, Link checker |
| **Seguridad** | Router (type=quality), Ejecutor | SARIF parser, Severity scorer |
| **Deploy** | Router (type=coordination), Ejecutor | Health check, Rollback trigger |

---

## 8. ARCHIVOS CLAVE DEL PIPELINE ACTUAL

- `BAGO\.bago\tools\bago_pipeline.py` — motor de orquestacion
- `BAGO\.bago\tools\bago_dynamic_router.py` — clasificador de tareas
- `BAGO\.bago\tools\bago_orchestrator.py` — selector de modelo
- `BAGO\.bago\tools\bago_adaptive_engine.py` — motor B/A (Balanceado Adaptativo)
- `BAGO\.bago\agents\agent_contract.json` — schema de contrato
- `BAGO\bago.ps1` — wrapper PowerShell con job en segundo plano
- `BAGO\tests\test_bago_brutal.py` — tests de validacion


---

## 7. BUILD MULTIPLATAFORMA: De Web a Nativo

**Principio:** Cada proyecto web/BAGO debe poder generar artefactos nativos sin reescribir codigo.

### 7.1 APK Android (Trusted Web Activity)

**Herramienta:** `.bago/tools/bago_apk_builder.py`
**Tecnica:** Bubblewrap CLI genera un contenedor Android que carga la PWA en un Chrome Custom Tab sin barras de navegacion.

**Pipeline:**
```
PWA (manifest.json + service worker + iconos)
  → bago_apk_builder.py --url https://app.com --name "App" --package com.app
    → bubblewrap init --manifest manifest.json
    → bubblewrap build
      → app-release.apk
      → app-release.aab (para Play Store)
```

**Requisitos:**
- Node.js + npm
- JDK 17 (auto-descargable por Bubblewrap)
- Android SDK (auto-descargable)
- PWA con manifest valido, icons 512x512, start_url, display: standalone

**Feature gates:**
- Free: APK generado, firma de debug
- Pro/Studio: Firma de release, AAB para Play Store, asset links

### 7.2 App de Escritorio (Electron)

**Herramienta:** `.bago/tools/bago_electron_packager.py`
**Tecnica:** Electron empaqueta Chromium + Node.js con la web app cargada via loadURL().

**Pipeline:**
```
Web app / PWA
  → bago_electron_packager.py --url https://app.com --name "App"
    → scaffold: package.json + main.js + preload.js
    → npm install electron electron-builder
    → npm run dist:dir
      → win-unpacked/App.exe
      → mac/App.dmg (si build en macOS)
      → linux/App.AppImage
```

**Requisitos:**
- Node.js + npm
- electron-builder (auto-instala)

**Optimizaciones:**
- Preload.js para seguridad (contextIsolation, no nodeIntegration)
- Icono PNG/ICO en carpeta del proyecto
- Auto-updater via electron-updater (cloud)

### 7.3 Docker Container

**Uso:** Backend BAGO como servicio auto-contenido
**Pipeline:**
```
Dockerfile (python:3.11-slim + uvicorn + app)
  → docker build -t bago-music .
  → docker run -p 7430:7430 bago-music
```

**Config:**
- `render.yaml` para Render.com
- `docker-compose.yml` para local/orquestacion
- `.env` para secrets (Stripe, Telegram tokens)

### 7.4 Checklist de Build Universal

Antes de cualquier build, verificar:
- [ ] `manifest.json` valido (name, short_name, icons, start_url, display)
- [ ] `service-worker.js` para offline
- [ ] Iconos en 192x192 y 512x512
- [ ] API base configurable (no localhost hardcodeado)
- [ ] Tokens en variables de entorno, no en codigo
- [ ] CORS configurado para dominio de produccion

**Comando universal:**
```bash
BAGO build --target apk|electron|docker|all --url https://app.com
```
