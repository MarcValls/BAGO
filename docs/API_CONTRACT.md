# BAGO — Contrato Público de API

> **Versión**: 3.4.0b1 · Actualizado: Mayo 2026  
> Este documento describe la interfaz de referencia de BAGO: comandos CLI
> con estabilidad `core` y endpoints JSON del launcher.
> Los elementos marcados ⚠️ requieren flags explícitos.

---

## 1. Comandos CLI — Estabilidad Core

Los 38 comandos con `stability = "core"` en `.bago/tools/tool_registry.py`
constituyen la interfaz pública estable del sistema. El registry es la fuente de
verdad; `docs/COMMANDS.md` y el README deben derivarse o validarse contra él.

Core actual:

`advisor`, `ask`, `audit`, `context`, `dashboard`, `devmode`, `diff`,
`doc-agent`, `docs`, `flow`, `goals`, `health`, `ideas`, `launch`, `menu`,
`next`, `orphans`, `pack-cache`, `project`, `recent-projects`, `review`,
`risk`, `route`, `scope`, `secrets`, `self`, `session`, `setup`, `snapshot`,
`sprint`, `status`, `sync`, `task`, `validate`, `version`, `why`, `workflow`,
`workspace-select`.

El contrato no promete estabilidad de salida byte-a-byte: sí promete nombre del
comando, semántica principal, exit codes razonables y que el comando resuelva por
el dispatcher sin rutas rotas.

### Exit codes de referencia (comportamiento observado)

| Código | Significado |
|--------|-------------|
| `0` | Proceso terminó normalmente |
| `1` | Error lógico (validación fallida, estado inválido) |
| `2` | Error de uso (argumento no reconocido) |
| `130` | Interrumpido por el usuario (Ctrl+C) |

---

## 2. Comandos peligrosos — Requieren confirmación explícita

Los 8 comandos `dangerous` requieren la flag `--yes` o `--unsafe` para ejecutarse.
Sin ella, muestran una advertencia y salen con código `1`.

| Comando | Acción peligrosa | Flag requerida |
|---------|-----------------|----------------|
| `bago autonomous` | Loop autónomo SENSE→PLAN→ACT→LEARN | `--yes` o `--unsafe` |
| `bago auto` | Modo automático con evaluación y acción | `--yes` o `--unsafe` |
| `bago db` | Gestión de bago.db (reset / init destructivo) | `--yes` o `--unsafe` |
| `bago install` | Auto-lanzamiento al insertar pendrive | `--yes` o `--unsafe` |
| `bago cabinet` | Orquestación de agentes en paralelo | `--yes` o `--unsafe` |
| `bago orchestrate` | Workflows multi-tool en secuencia | `--yes` o `--unsafe` |
| `bago peer` | Comunicación P2P LAN | `--yes` o `--unsafe` |
| `bago spiral` | Bucle espiral de auto-redescripción | `--yes` o `--unsafe` |

---

## 3. Comandos experimentales — Estabilidad no core

Los 80 comandos `experimental` pueden cambiar, renombrarse o eliminarse entre versiones.
No se incluyen en la interfaz de referencia. Ver `docs/COMMANDS.md` para la lista completa.

Para usarlos:
```bash
bago <comando>      # funcionan normalmente
bago help --all     # lista todos incluyendo experimental
```

---

## 4. Launcher HTTP API — Endpoints JSON

El launcher (`launcher/server.py`) expone una API HTTP local en `http://localhost:7430`
(puerto configurable con `BAGO_PORT`).

### Autenticación

- **GET endpoints**: sin autenticación (solo lectura, datos locales)
- **POST endpoints**: requieren header `X-BAGO-Token: <token>` si `BAGO_TOKEN` está definido en el entorno. Si no está definido, el token se ignora (modo desarrollo).

```bash
export BAGO_TOKEN=mi-token-secreto   # activar auth
BAGO_TOKEN=mi-token python3 launcher/server.py
```

### GET /api/status

```json
{
  "version": "3.4.0b1",
  "mode": "autonomous",
  "health": 100,
  "active_flow": "ninguno",
  "ideas_count": 30,
  "last_w2": "título del último workflow",
  "last_session": "2026-05-13T00:00:00+00:00",
  "project": "bago-core"
}
```

### GET /api/agents

```json
[
  {
    "id": "ollama",
    "name": "Ollama",
    "available": true,
    "models": ["qwen2.5-coder:7b"],
    "active_model": "qwen2.5-coder:7b",
    "icon": "🦙",
    "subtitle": "LLM local",
    "color": "#3ecf8e",
    "reason": null,
    "install_url": "https://ollama.ai"
  }
]
```

### GET /api/routing-history

```json
[
  {
    "task": "implementar login",
    "agent": "copilot",
    "confidence": 85,
    "timestamp": "2026-05-13T10:30:00",
    "decision_source": "local_classifier"
  }
]
```

### GET /api/sessions

```json
[
  {
    "_file": "SES-001.json",
    "title": "Título de la sesión",
    "started": "2026-05-13T10:00:00",
    "status": "closed"
  }
]
```

### GET /api/ideas

```json
[
  {
    "title": "Título de la idea implementada",
    "done_at": "2026-05-07T15:12:09",
    "slot": null
  }
]
```

### GET /api/task

```json
{
  "status": "pending",
  "title": "Título de la tarea W2",
  "task": "descripción"
}
```

Cuando no hay tarea activa: `{ "status": "none" }`

### GET /api/llm/status

```json
{
  "engine": "ollama",
  "active_model": "qwen2.5-coder:7b",
  "server_url": "http://127.0.0.1:11434",
  "ollama_available": true,
  "ollama_models": ["qwen2.5-coder:7b"],
  "ollama_error": null
}
```

### POST /api/launch

**Request:**
```json
{ "agent": "ollama", "model": "qwen2.5-coder:7b", "task": "implementar login" }
```

**Response (éxito):**
```json
{ "ok": true, "agent": "ollama", "model": "qwen2.5-coder:7b" }
```

**Response (error):**
```json
{ "ok": false, "error": "descripción del error" }
```

### POST /api/route

**Request:**
```json
{ "task": "revisar PR y detectar bugs" }
```

**Response:**
```json
{
  "agent": "copilot",
  "agent_name": "GitHub Copilot",
  "agent_icon": "🤖",
  "confidence": 88,
  "model": "copilot",
  "reason": "revisión de código",
  "decision_source": "local_classifier",
  "fallback_chain": ["ollama"]
}
```

### POST /api/llm/chat

**Request:**
```json
{ "message": "¿Qué es BAGO?", "model": "qwen2.5-coder:7b" }
```

**Response (éxito):**
```json
{ "ok": true, "response": "BAGO es…", "model": "qwen2.5-coder:7b" }
```

**Response (error):**
```json
{ "ok": false, "error": "No se puede conectar a Ollama: …" }
```

### POST /api/bago/run

Ejecuta un sub-comando `bago` en el servidor.

**Request:**
```json
{ "command": "validate", "confirmed": false }
```

**Response normal:**
```json
{ "ok": true, "stdout": "GO manifest\nGO state\nGO pack\n", "stderr": "", "returncode": 0 }
```

**Response (comando sensible sin confirmar):**
```json
{
  "ok": false,
  "requires_confirmation": true,
  "command": "db reset",
  "warning": "Esta acción puede modificar el sistema de forma irreversible."
}
```

**Response (JSON malformado en request):**
```
HTTP 400: { "error": "JSON inválido" }
```

---

## 5. Separación lectura / mutación

| Tipo | Endpoints | Efecto |
|------|-----------|--------|
| **Lectura** | GET /api/* | Solo lectura de ficheros locales, sin side effects |
| **Mutación** | POST /api/launch, /api/bago/run | Lanza procesos, modifica estado |
| **Chat** | POST /api/llm/chat, /api/route | Consultas externas (Ollama), sin estado BAGO modificado |

---

## 6. Versionado y compatibilidad

- La API del launcher es **interna** — puede cambiar entre versiones major.
- Los 38 comandos `core` CLI son la interfaz de referencia del sistema (ver `.bago/tools/tool_registry.py`).
- El campo `version` debe estar alineado entre `pyproject.toml`, `.bago/pack.json` y `.bago/state/global_state.json`.
- Los cambios en endpoints se documentan en `CHANGELOG.md`.
