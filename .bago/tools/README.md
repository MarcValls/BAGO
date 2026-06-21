# BAGO 4.1.5 — Herramientas portadas (`.bago/tools/`)

Utilidades **standalone** recuperadas de BAGO 3.x y adaptadas a 4.1.5.
Son scripts ejecutables directamente (no están cableados al `ToolRegistry`
del runtime, por lo que no afectan a los contratos del chat).

> **`bago_utils.py` es el keystone.** Es un helper de solo-stdlib (resolución de
> rutas, I/O de JSON, timestamps y reconfiguración de stdout a UTF-8). Ya está
> pensado para esta estructura (`get_bago_root()` = `parent.parent`), así que
> **portarlo desbloquea decenas de tools 3.x** que solo dependían de él.

## Disponibles

### `bago_security_audit.py` — Auditoría forense de seguridad
Escanea el repo (o una ruta) buscando tokens/credenciales expuestos y revisa
configuración de git y ficheros de secretos.

```bash
python .bago/tools/bago_security_audit.py                 # escanea el repo
python .bago/tools/bago_security_audit.py --home          # también el HOME
python .bago/tools/bago_security_audit.py --output report.json
```

### `agent_router.py` — Router de agente para tareas
Enruta una tarea al mejor agente disponible según señales locales, fallback
determinista y, si existe, clasificador Ollama.

```bash
python .bago/tools/agent_router.py --task "implement multi-file auth"
python .bago/tools/agent_router.py --history --json
bago agent route --task "review this PR"
```

### `secret_scan.py` — Escáner de secretos hardcodeados
Recorre código fuente buscando contraseñas/API keys/tokens/PEM/strings de
conexión hardcodeados (AWS, GitHub, OpenAI, Stripe, MongoDB…). Ofusca el valor
sensible en la salida y descarta placeholders de documentación.

```bash
python .bago/tools/secret_scan.py                 # escanea ./
python .bago/tools/secret_scan.py .bago\core --severity error
python .bago/tools/secret_scan.py . --json
python .bago/tools/secret_scan.py --test          # 6/6 self-tests
```

### `dep_audit.py` — Auditoría de seguridad de dependencias
Analiza `requirements*.txt` / `pyproject.toml` y detecta versiones sin pinear,
rangos abiertos, duplicados y paquetes con CVEs conocidos (lista offline).
Opcionalmente invoca `pip-audit` si está instalado.

```bash
python .bago/tools/dep_audit.py                   # busca ficheros de deps en ./
python .bago/tools/dep_audit.py requirements.txt --format md --out report.md
python .bago/tools/dep_audit.py . --pip-audit
python .bago/tools/dep_audit.py --test            # 6/6 self-tests
```

### `forced_dependency_scan.py` — Detector de dependencias forzadas
Busca instalaciones directas, pins raros, `sys.path.insert`, overrides,
resolutions y rutas `file:` / `link:` / `workspace:` que fuerzan dependencias.

```bash
python .bago/tools/forced_dependency_scan.py
python .bago/tools/forced_dependency_scan.py . --format md
python .bago/tools/forced_dependency_scan.py --test

O desde el CLI:

```bash
bago scan --root . forced
```
```

Las tres herramientas comparten `bago_utils.py` y son ASCII/UTF-8 safe en
consolas Windows. Verificadas: self-tests al 100% + ejecución funcional sobre el
repo limpio.

Adaptaciones respecto a la versión 3.x:
- Raíz parametrizable (`--root`), por defecto la raíz del repo (antes escaneaba
  todo el HOME y `E:/bago_fw` hardcodeado).
- Sin identidades git hardcodeadas (la 3.x reescribía nombre/email del usuario).
- Salida ASCII-safe (sin emojis) para consolas Windows.
- Filtros anti falso-positivo: descarta placeholders de documentación y solo
  marca como "secreto rastreado por git" ficheros de datos (`.json`/`.env`/…),
  no código fuente (p. ej. `credential_manager.py`).

Verificado: 100/100 contra el repo limpio; detecta tokens plantados (test positivo).

## Roadmap — "ases en la manga" para el lanzamiento

Curaduría de las piezas 3.x más estratégicas a portar (preservadas en
`~/.bago/legacy-pieces/bago_true-3.x/.bago/tools/`), agrupadas por el valor que
aportan en un lanzamiento. Las marcadas con keystone solo dependen de
`bago_utils.py` (ya portado) → portado trivial.

**A. Seguridad y confianza** (demo-killer, generan confianza inmediata)
- [x] `bago_security_audit` — auditoría forense.
- [x] `secret_scan` — secretos hardcodeados. *(keystone)*
- [x] `dep_audit` — CVEs en dependencias. *(keystone)*
- [ ] `token_rotation_guard` — escanea tokens + `--fix`. *(solo stdlib)*
- [ ] `bago_canary` — honeytokens/señuelos con credenciales falsas; detecta
      accesos no autorizados. *(solo stdlib, diferenciador "wow")*

**B. Autodiagnóstico y autoreparación** (narrativa "BAGO se cura solo";
alineado con la preferencia de "culpa técnica")
- [ ] `doctor` — diagnóstico integral del pack. *(keystone)*
- [ ] `auto_heal` / `bago_selfrepair` — detección y reparación automática.
- [ ] `preflight_engine` — checks fail-closed antes de ejecutar.

**C. Calidad de código** (valor inmediato para devs)
- [ ] `dead_code`, `code_metrics`, `naming_check`, `todo_scan`. *(keystone)*

**D. Inteligencia / memoria** (diferenciador IA local-first)
- [ ] `bago_advisor` — advisor LLM contextual (qué hacer ahora).
- [ ] `insights` — insights accionables desde datos de sesión. *(keystone)*
- [ ] `project_memory` — memoria distribuida por proyecto. *(keystone)*
- [x] `bago_inventory` — cataloga capacidades reutilizables. *(solo stdlib)*

**E. Resiliencia / portabilidad**
- [ ] `bago_portable` — instalación/sync en pen drive. *(keystone)*
- [ ] `bago_backup_vault` — backups rotados (engine/memory).

El resto de las ~546 herramientas 3.x siguen preservadas. Las grandes
(`agent_router`, `spiral_agent`, `toolsmith`, `neural_toolbox`) arrastran el
ecosistema 3.x (`tool_registry`, `bago.ollama_runtime`, `harmony_gate`, `numpy`,
`rich`) y requieren portado individual + wrapping al `ToolRegistry` 4.1.5.
