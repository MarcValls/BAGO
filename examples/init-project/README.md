# Ejemplo robusto: inicializar un proyecto BAGO desde cero

Este ejemplo muestra cómo crear un proyecto nuevo y sembrarlo con la
estructura canónica `.bago/` sin fisuras: sin estado runtime, sin credenciales
y sin artefactos compilados.

## Requisitos

- BAGO v4.7 instalado o disponible en este repositorio.
- Python 3.11+.
- PowerShell (Windows) para el script de demo, o usar los comandos equivalentes.

## Escenario

Queremos trabajar sobre `C:\Proyectos\mi-nueva-app`, un directorio vacío que
aún no tiene BAGO.

## Pasos manuales

```powershell
# 1. Crear el directorio del proyecto
New-Item -ItemType Directory -Path "C:\Proyectos\mi-nueva-app" -Force | Out-Null
Set-Location "C:\Proyectos\mi-nueva-app"

# 2. Sembrar .bago/ desde la plantilla canónica
bago init

# 3. (Opcional) Ver en modo simulado sin escribir nada
bago init --dry-run

# 4. Verificar la estructura
Get-ChildItem .bago

# 5. Validar el proyecto recién sembrado
python C:\Ruta\De\BAGO\bago_core\cli.py validate
```

## Qué se sembró

| Ruta | Rol |
|---|---|
| `.bago/AGENT_START.md` | Entrypoint de adopción BAGO para agentes |
| `.bago/BOOTSTRAP.md` | Base prompt compartido |
| `.bago/core/` | Runtime de sesión, providers, intenciones, tools |
| `.bago/api/bridge.py` | API HTTP local |
| `.bago/chat/` | REPL y comandos |
| `.bago/providers/` | Adapters de providers |
| `.bago/agents/` | Agentes especialistas |
| `.bago/roles/` | Roles de gobierno/producción |
| `.bago/prompts/` | Plantillas de prompts |
| `.bago/workflows/` | Workflows canónicos |
| `.bago/tools/` | Tools y project memory |
| `.bago/mcp/` | Configuración MCP |
| `.bago/templates/` | Plantillas Markdown |
| `.bago/state/` | Estado mínimo inicial (vacío/sessions/evidences/changes) |
| `.bago/logs/` | Logs runtime (vacío) |

## Qué NO se sembró (y por qué)

- `state/*.json` con contenido real → se generan en runtime.
- `credentials.json`, `config.json`, `session-credentials.json` → generados por el runtime.
- `__pycache__`, `*.pyc`, `*.db` → artefactos, no plantilla.
- `knowledge/` → solo con `--with-knowledge`, porque es específico de proyecto.

## .gitignore recomendado para el nuevo proyecto

```gitignore
# BAGO runtime state
.bago/state/
.bago/logs/
.bago/launch/
.bago/credentials.json
.bago/config.json
.bago/session-credentials.json
.bago/monitor/
*.db
*.sqlite
__pycache__/
```

## Sobrescribir una semilla existente

Si ya habías sembrado y quieres refrescar con la plantilla canónica:

```powershell
bago init --force
```

**Atención:** `--force` reemplaza archivos existentes. Guarda primero tus
overrides intencionales.

## Demo automatizada

Ver `init-demo.ps1` en esta misma carpeta.
