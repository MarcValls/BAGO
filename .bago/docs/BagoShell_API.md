# BagoShell API — Documentación Técnica

> **Versión**: 2.0  
> **Fecha**: 2026-05-27  
> **Archivo**: `.bago/tools/bago_shell.py`

---

## ¿Qué es BagoShell?

**BagoShell** (BISH — BAGO Interactive SHell) es la shell propia de BAGO con **dos modos de operación**:

1. **REPL interactivo** (`bago shell`) — para humanos
2. **API programática** (`BagoShell.run()`) — para agentes autónomos

Ambos comparten el mismo motor de clasificación de riesgo, autorización y logging.

---

## Uso desde línea de comandos

```bash
# Entrar al REPL interactivo
bago shell

# Ejecutar un comando y salir
bago shell -- echo "hola"
bago shell -c "git status"

# Ejecutar un script
bago shell script.ps1
```

### Comandos dentro del REPL

| Comando | Descripción |
|---------|-------------|
| `health`, `validate`, `status` … | Ejecuta comando BAGO nativo |
| `git status`, `docker ps` … | Delega al shell del sistema |
| `ls -la \| head -n 5` | Pipes/redirecciones → shell nativo |
| `ll`, `la`, `cls` | Aliases del sistema |
| `!!` | Repite último comando |
| `!42` | Repite comando #42 del historial |
| `!git` | Repite último comando que empiece por "git" |
| `cd ..`, `cd ~`, `cd -` | Cambia directorio |
| `history` | Muestra historial |
| `exit`, `quit`, `q` | Sale de la shell |

---

## Uso programático (API para agentes)

```python
from bago_shell import BagoShell, ShellResult

# Instancia por defecto: no auto-aprueva peligrosos
shell = BagoShell(auto_approve=False)

# Ejecutar un comando seguro
r: ShellResult = shell.run("health", capture_output=True)
print(r.exit_code, r.stdout)

# Ejecutar comando del sistema
r = shell.run("git log --oneline | head -n 5", capture_output=True)

# Comando peligroso → bloqueado sin autorización
r = shell.run("autonomous", capture_output=True)
print(r.needs_auth)   # True
print(r.authorized)    # False

# Autorizar y reintentar
shell.authorize_once("autonomous")
r = shell.run("autonomous", capture_output=True)

# Modo dry-run (simulación)
r = shell.run("heal --yes", capture_output=True, dry_run=True)
print(r.stdout)  # [DRY-RUN] Se ejecutaría: heal --yes

# Ejecutar batch de comandos
results = shell.run_batch(["validate", "sync", "echo done"])
for res in results:
    print(res.canonical, res.exit_code, res.category)
```

---

## ShellResult — Estructura de respuesta

```python
@dataclass
class ShellResult:
    command: str        # Comando original
    canonical: str      # Comando canónico
    category: str       # bago_safe | bago_caution | bago_dangerous
                        # system_safe | system_caution | system_dangerous
                        # builtin | script | unknown
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    authorized: bool = False
    needs_auth: bool = False
    dry_run: bool = False
    duration_ms: float = 0.0
    timestamp: str      # ISO 8601
    error: str | None = None
```

---

## Clasificación de riesgo

### Comandos BAGO

| Categoría | Comandos ejemplo | Comportamiento |
|-----------|-----------------|----------------|
| `bago_safe` | `health`, `validate`, `status`, `registry` | ✅ Ejecuta directo |
| `bago_caution` | `sync`, `cosecha`, `ideas`, `task` | ✅ Ejecuta + log |
| `bago_dangerous` | `autonomous`, `heal --yes`, `cabinet` | 🚫 Requiere autorización |

### Comandos del sistema

| Categoría | Comandos ejemplo | Comportamiento |
|-----------|-----------------|----------------|
| `system_safe` | `git status`, `ls`, `echo` | ✅ Ejecuta directo |
| `system_caution` | `git add`, `mkdir` | ✅ Ejecuta + log |
| `system_dangerous` | `rm -rf`, `sudo`, `mkfs` | 🚫 Requiere autorización |

### Protecciones implementadas

- `git`, `python`, `docker`, `node`, `code`, `vim`… **nunca** se secuestran por BAGO sin prefijo `bago`
- Heurísticas: `rm -rf`, `curl …\|sh`, `sudo`, `dd if=`, etc. → `system_dangerous`
- Pipes (`\|`), redirecciones (`>`, `>>`), operadores (`&&`, `\|\|`) → shell nativo

---

## Autorización

```python
# Autorizar un comando puntual
shell.authorize_once("autonomous")

# Autorizar múltiples comandos
shell.authorize_batch([
    "heal --yes",
    "autonomous --loop",
    "rm -rf /tmp/old"
])

# Revocar autorización
shell.revoke_authorization("autonomous")   # uno
shell.revoke_authorization()                # todos

# Modo auto-approve (desde constructor o env)
shell = BagoShell(auto_approve=True)
# o: BAGO_AUTO_APPROVE=1
```

---

## Variables de entorno

| Variable | Efecto |
|----------|--------|
| `BAGO_AUTO_APPROVE=1` | Auto-autoriza categoría dangerous |
| `BAGO_SHELL_DRY_RUN=1` | Solo simula, no ejecuta nada |
| `BAGO_SHELL_LOG_PATH` | Ruta del JSONL de auditoría (default: `state/shell_autonomous_log.jsonl`) |

---

## Logging de auditoría

Toda ejecución se registra en **JSONL**:

```json
{"command":"health","canonical":"health","category":"bago_safe","exit_code":0,"authorized":true,"needs_auth":false,"duration_ms":1240.5,"timestamp":"2026-05-27T12:34:56"}
{"command":"autonomous","canonical":"autonomous","category":"bago_dangerous","exit_code":1,"authorized":false,"needs_auth":true,"dry_run":true,"timestamp":"2026-05-27T12:34:57","error":"Comando peligroso requiere autorización: autonomous"}
```

Default: `.bago/state/shell_autonomous_log.jsonl`

---

## Integración en otros módulos

BagoShell está integrado con **fail-soft** en 7 módulos:

| Módulo | Método integrado | Rationale |
|--------|-----------------|-----------|
| `autonomous_loop.py` | `_run_tool()` | Bucle autónomo usa logging unificado |
| `agent_gateway.py` | `_run_bago()` | Gateway multi-agente con clasificación |
| `bago_mcp_server.py` | `_run_bago()` | MCP ya validado → auto_approve=True |
| `bago_miniapp_server.py` | `run_bago_cmd()` | Mini App expone a usuarios |
| `cabinet_orchestrator.py` | `run_agent()` | Gabinete con captura de output |
| `workflow_autonomy.py` | `reconcile_workflow()` | Cierre W2 auto con logging |
| `auto_mode.py` | `_validate()`, `_stale_count()` | Modo auto unificado |

Si `bago_shell.py` no está disponible, cada módulo **fallback transparente** a `subprocess.run` original.

---

## Prompt del REPL

```
🅱 ~/bago_fw [main] bago$ 
```

- `🅱` — logo BAGO
- `~/bago_fw` — directorio relativo al repo
- `[main]` — branch git (si hay TTY)
- `bago$` — prompt

---

## Arquitectura

```
┌─────────────────────────────────────────┐
│  BagoShell                              │
│  ├── classify() → risk level             │
│  ├── authorize_*() → gatekeeping       ││
│  ├── run() → ShellResult               │
│  ├── run_batch() → list[ShellResult]   │
│  └── repl() → interactivo humano         │
├─────────────────────────────────────────┤
│  Integración fall-soft (7 módulos)       │
│  autonomous_loop │ agent_gateway │ mcp   │
│  miniapp_server │ cabinet │ workflow     │
│  auto_mode                               │
├─────────────────────────────────────────┤
│  Logging JSONL persistente               │
│  state/shell_autonomous_log.jsonl        │
└─────────────────────────────────────────┘
```

---

## Changelog de la v2.0

| Cambio | Detalle |
|--------|---------|
| Nueva API | `BagoShell` clase + `ShellResult` dataclass |
| Clasificación | safe / caution / dangerous para BAGO y sistema |
| Autorización | `authorize_once()`, `authorize_batch()`, `revoke_authorization()` |
| Dry-run | Simulación sin ejecución real |
| Logging | JSONL persistente con timestamp |
| Historial | `!!`, `!n`, `!prefix` + persistencia en `.bago/state/shell_history.txt` |
| Prompt | Directorio relativo + branch git |
| Aliases | `ll`, `la`, `cls` adaptativos según entorno |
| Fail-soft | Integración en 7 módulos con fallback a subprocess |

---

*Generado automáticamente por BAGO · 2026-05-27*
