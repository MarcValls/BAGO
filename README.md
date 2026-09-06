# BAGO v4.10.0 — candidato de release

[![Version](https://img.shields.io/badge/version-4.10.0-blue)]()
[![CI](https://github.com/MarcValls/BAGO/actions/workflows/canonical-ci.yml/badge.svg)](https://github.com/MarcValls/BAGO/actions/workflows/canonical-ci.yml)
[![Python](https://img.shields.io/badge/python-3.14%2B-blue)]()
[![Node](https://img.shields.io/badge/node-20%2B-green)]()
[![Verification](https://img.shields.io/badge/verification-candidate--bound-blue)]()
[![License](https://img.shields.io/badge/license-Proprietary-red)]()

**BAGO** es un plano de control de IA local. Su función principal es mantener la sesión como fuente de verdad mientras los proveedores y modelos permanecen como motores de ejecución intercambiables.

---

## Novedades preparadas para 4.10.0

### Contratos y arquitectura
- Se declara y prueba la frontera kernel/extensión, con compatibilidad de entradas existentes y una migración de imports enumerada y verificable.
- Capability API v1 alinea permisos, confirmaciones, red, simulación e información de recibos entre backend y frontend.
- La identidad del modelo, sus capacidades observadas y la política de routing quedan separadas; el camino RL sigue sin autoridad de ejecución automática.

### Seguridad de distribución
- El preflight de firma Authenticode falla de forma segura y emite un recibo JSON aunque GitHub responda que falta el entorno de firma.
- Las proyecciones de rutas, migración y versión se verifican contra drift en CI.

> Este candidato no está publicado: requiere un entorno `release-signing`, una identidad de firma pública autorizada y los gates de artefacto firmados.

## Novedades en 4.9.0

### Correcciones
- **Detección de GitHub restaurada** — el panel de autenticación vuelve a reportar si `gh` está instalado y si el usuario está autenticado
- **Navegación lateral reparada** — los botones de drawers de Herramientas, Pipeline y Capacidades ahora abren su panel correspondiente

## Novedades en 4.8.6

### UI
- **Selector de tema claro/oscuro** en la cabecera principal — persiste en sesión
- **Modo claro** completamente funcional: todos los fondos oscuros hardcodeados migrados a variables CSS
- **Arquitectura CSS por tokens** — `frontend/src/styles/` dividido en `tokens.css`, `reset.css`, `utilities.css`, `components.css` con tokens semánticos de espaciado, tipografía, radios, sombras y duraciones

### Ciclo de vida (Windows)
- `ARRANCAR_BAGO.bat` — lanzador de un clic: inicia el backend, abre Electron y detiene el backend al cerrar la ventana
- Hook `before-quit` en Electron: llama a `dev.ps1 stop` de forma síncrona antes de salir
- Acceso directo en el Menú Inicio y Escritorio instalados por el instalador

### Backend y sesiones
- Sistema de capacidades avanzado (`capability-anatomy`)
- Soporte multi-conversación con `active_conversation_id`
- Registro de sesiones (`session registry`)
- Integración del módulo Vision
- Provider Center con grid de proveedores configurables

### Instalación
- Instalador Windows `BAGO-Installation-Manager-4.9.1-win-x64.exe` (NSIS) — instala todos los componentes y crea accesos directos
- Script `install-v4.ps1` con soporte para `-PackageZip`

---

## Estructura del monorepo

```
BAGO/
├── backend/                  # Runtime Python (core, CLI, API local, contratos)
│   ├── bago_core/            # Núcleo: sesiones, proveedores, capacidades, RL
│   ├── tests/                # pytest; resultados exactos en recibos del candidato
│   ├── docs/                 # Documentación técnica
│   └── ui-react/dist/        # Copia del build de la UI (generada por npm run build; no en el repo)
├── frontend/                 # UI React + TypeScript (Vite)
│   └── src/
│       ├── styles/           # Sistema de tokens CSS modular
│       │   ├── tokens.css    # Variables de diseño centralizadas
│       │   ├── reset.css     # Reset y elementos base
│       │   ├── utilities.css # Controles y utilidades compartidas
│       │   ├── components.css# Reglas de componentes
│       │   └── index.css     # Entry point
│       ├── api/              # Cliente HTTP hacia el backend
│       ├── app/              # ControlPlane principal
│       ├── layout/           # GlobalHeader, ChatPanel, etc.
│       ├── modules/          # Módulos funcionales (capabilities, vision, etc.)
│       └── state/            # uiStore (Zustand)
├── electron-viewer/          # Visor Electron con ciclo de vida automático
├── scripts/
│   ├── dev.ps1               # start / stop / build / status / backend / electron
│   └── bago-launcher.ps1     # Lanzador manual legacy
├── releases/
│   └── bago-installer.nsi    # Script NSIS para generar setup.exe legacy
├── ARRANCAR_BAGO.bat         # Lanzador principal Windows
└── package.json              # Raíz del workspace npm
```

---

## Requisitos

| Componente | Versión mínima |
|---|---|
| Windows | 10 / 11 (plataforma principal) |
| Python | 3.14+ |
| Node.js | ≥ 22.12.0 |
| npm | ≥ 10.0.0 |
| Ollama | Opcional — necesario para el path local con modelo en vivo |

> macOS y Linux son experimentales hasta que sus gates de instalación y runtime sean verificados.

---

## Instalación

### Opción A — Instalador Windows (recomendado)

La última release pública es [v4.9.3](https://github.com/MarcValls/BAGO/releases/tag/v4.9.3). Descarga `bago-4.9.3-setup.exe` y ejecútalo. La candidata 4.10.0 aún no debe distribuirse: está pendiente de firma Authenticode autorizada.
- Instala backend (Python), frontend compilado y Electron viewer
- Crea accesos directos "BAGO" en el Escritorio y el Menú Inicio
- El acceso directo apunta al `BAGO.exe` empaquetado (sin consola y sin navegador)
- La instalación queda fijada a una referencia Git inmutable (`InstallRef`) en lugar de `main`

### Opción B — Instalación desde fuentes (Windows)

```powershell
git clone https://github.com/MarcValls/BAGO.git
cd BAGO
.\backend\install-v4.ps1 -Mode Express
```

### Opción C — Instalador remoto (última release publicada)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "iwr https://raw.githubusercontent.com/MarcValls/BAGO/main/install-remote.ps1 -OutFile install-remote.ps1; .\install-remote.ps1"
```

### Instalación por perfil

```powershell
bago profiles
bago install --profile des      # desarrollo
bago install --profile ign      # ignición / staging
bago install --profile stable   # producción estable
```

---

## Uso mínimo

### Arrancar BAGO (Windows)

Doble clic en `ARRANCAR_BAGO.bat` o en el acceso directo del Menú Inicio/Escritorio.  
Esto inicia el backend en `http://127.0.0.1:8080` y abre la ventana Electron. **Al cerrar la ventana, el backend se detiene automáticamente.**

### Arrancar manualmente

```powershell
# Arrancar backend + build del frontend + ventana Electron
npm run start

# Sólo el backend
npm run backend

# Build de producción
npm run build
```


### Android minimal manager (non-local providers)

```text
manager/android/index.html
```

Android compatibility dependencies (calculated):

| Dependency | Required | Purpose | Link |
|---|---|---|---|
| Android System WebView / Chrome | Yes (UI web) | Run `manager/android/index.html` with `fetch`, `sessionStorage`, `localStorage` | https://play.google.com/store/apps/details?id=com.google.android.webview |
| Termux | Yes (CLI in Android) | Run `bago`/`python` commands on Android | https://termux.dev/en/ |
| Python 3.11+ (Termux package) | Yes (CLI core) | Execute `bago_core/cli.py` and `bago android ...` | https://wiki.termux.com/wiki/Python |
| Git (Termux package) | Yes (source install/update) | Clone/update repository in Android | https://wiki.termux.com/wiki/Git |
| OpenRouter API key | Optional (provider) | Cloud provider for Android Mini and CLI | https://openrouter.ai/docs/quickstart |
| OpenAI API key (Codex) | Optional (provider) | Alternative cloud provider for Android Mini and CLI | https://platform.openai.com/docs/quickstart |
| Anthropic API key | Optional (CLI) | Provider available in `bago android`; web Android requires proxy due CORS | https://docs.anthropic.com/en/api/getting-started |

Android/Termux minimal profile:

```bash
bago android init --provider openrouter
export OPENROUTER_API_KEY='<tu_clave>'
bago llm start --provider openrouter --model openai/gpt-4o-mini --dry-run
```

Android layered autonomy:

```bash
# Diagnóstico por capas (runtime/provider/network/security/ui)
bago android layers --json

# Aplicar baseline Android por capas (en Termux)
bago android layers --provider openrouter --apply
```


### CLI

```powershell
# Arrancar con modelo local (Ollama)
python backend\bago_core\cli.py llm start --provider ollama-local --model llama3.2:3b

# Validar sin abrir chat
python backend\bago_core\cli.py llm start --provider ollama-local --model llama3.2:3b --dry-run

# Validar contratos, seguridad y configuración de proveedores
python backend\bago_core\cli.py validate
```

### Modo headless / agente

```powershell
bago exec /help
bago exec /commands json
bago exec /doctor
bago exec /status
```

---

## Comandos principales

| Comando | Descripción |
|---|---|
| `python backend\bago_core\cli.py validate` | Valida contratos, defaults de seguridad y configuración de proveedores |
| `python backend\bago_core\cli.py llm list` | Lista disponibilidad de proveedores y modelos |
| `python backend\bago_core\cli.py llm start ...` | Arranca o simula el startup con conciencia de proveedor |
| `python backend\bago_core\cli.py serve --host 127.0.0.1 --port 8080` | Arranca la API local |
| `python backend\bago_core\cli.py rl status` | Reporta el estado RL/shadow sin conceder autoridad |
| `python backend\bago_core\cli.py evidence --test` | Valida la generación del bundle de evidencias |
| `bago exec /commands json` | Exporta el catálogo de slash-commands para agentes |
| `bago exec /doctor` | Diagnóstico: catálogo, ejecución headless, roles de instalación y salud de proveedores |

---

## Scripts de desarrollo (monorepo)

```powershell
npm run start      # Arrancar backend + build frontend + Electron
npm run stop       # Detener servicios
npm run restart    # Reiniciar
npm run status     # Estado de los servicios
npm run logs       # Ver logs
npm run build      # Build de producción
npm run test:frontend   # Tests del frontend
npm run typecheck       # Comprobación de tipos TypeScript
```

En sistemas Unix/macOS:

```bash
npm run sh:dev
npm run sh:stop
npm run sh:status
```

---

## Proveedores soportados

| Proveedor | Estado | Notas |
|---|---|---|
| `ollama-local` | ✅ Activo | Path local por defecto cuando Ollama está instalado |
| `ollama-cloud` | 🔶 Parcial | Requiere configuración de URL/clave |
| `copilot` | 🔶 Parcial | Requiere token/configuración de GitHub |
| `anthropic` | 🔶 Parcial | Requiere clave API |
| `codex` | 🔶 Parcial | Requiere clave/configuración API |
| `openrouter` | 🔶 Parcial | Requiere clave API |
| `opencode` | 🔶 Parcial | Requiere clave/configuración API |

---

## Estado del producto

| Área | Estado | Notas |
|---|---|---|
| Runtime core | Verificable | Suite y resultados ligados al SHA candidato |
| Instalación Windows | NOT_RUN en candidato actual | El instalador NSIS histórico no valida el SHA de remediación |
| Ciclo de vida Electron | Verificación pendiente | El código fuente tiene gates; falta validar el instalador exacto del candidato |
| UI React | Verificable | Tests ligados al SHA candidato, tema claro/oscuro, tokens CSS |
| Seguridad y postura API | ✅ Estable | `backend/docs/SECURITY.md` |
| Soporte de plataforma | ✅ Windows | macOS/Linux: experimental |
| Sistema de capacidades | ✅ Funcional | `capability-anatomy`, provider center |
| Conversaciones multi-turno | ✅ Funcional | `active_conversation_id`, session registry |
| Módulo Vision | 🔶 Integrado | Requiere proveedor compatible |
| Capa RL policy | 🧪 Experimental | Shadow mode, sin autoridad de ejecución |
| Agentes y autopilot | 🧪 Experimental | En desarrollo |
| Runtime C++ | 🧪 Experimental | Gates de plataforma pendientes |
| Store embeddings avanzado | 🔶 Parcial | `backend/docs/MODULES.md` |

---

## Releases

| Versión | Fecha | Artefactos |
|---|---|---|
| v4.10.0 | Pendiente de publicación | Candidato preparado; requiere instalador firmado y E2E del artefacto final |
| [v4.9.3](https://github.com/MarcValls/BAGO/releases/tag/v4.9.3) | 2026-09-01 | `bago-4.9.3-setup.exe` |
| [v4.9.2](https://github.com/MarcValls/BAGO/releases/tag/v4.9.2) | 2026-08-29 | `bago-4.9.2-setup.exe` |
| [v4.9.1](https://github.com/MarcValls/BAGO/releases/tag/v4.9.1) | 2026-08-25 | `BAGO-Installation-Manager-4.9.1-win-x64.exe` · `bago-v4.9.1.zip` |
| [v4.9.0](https://github.com/MarcValls/BAGO/releases/tag/v4.9.0) | 2026-08-18 | `BAGO-Installation-Manager-4.9.0-win-x64.exe` · `bago-v4.9.0.zip` |
| [v4.8.7](https://github.com/MarcValls/BAGO/releases/tag/v4.8.7) | 2026-08-16 | `BAGO-Installation-Manager-4.8.7-win-x64.exe` · `bago-v4.8.7.zip` |
| [v4.8.6](https://github.com/MarcValls/BAGO/releases/tag/v4.8.6) | 2026-08-16 | `BAGO-Installation-Manager-4.8.6-win-x64.exe` · `bago-v4.8.6.zip` |
| [v4.8.4](https://github.com/MarcValls/BAGO/releases/tag/v4.8.4) | 2026-08-10 | `bago-4.8.4-setup.exe` · `bago-4.8.4-distribution.zip` |
| [v4.8.2](https://github.com/MarcValls/BAGO/releases/tag/v4.8.2) | 2026-08-06 | `bago-4.8.2-setup.exe` · `backend.zip` · `frontend.zip` · `electron-viewer.zip` |

Los artefactos oficiales (`BAGO-Installation-Manager-{version}-win-x64.exe` y `bago-v{version}.zip`) se generan en CI desde una referencia etiquetada/inmutable, no desde `main`. El flujo local de referencia es:

```powershell
# 1. Validar backend
python -m pytest backend/tests

# 2. Build del frontend y del visor Electron
npm run build

# 3. Empaquetar backend runtime con la versión canónica
python backend/scripts/package_v4.py --version <version>

# 4. Solo después de que el preflight de firma esté listo, crear el tag inmutable
# git tag -a v<version> -m "release: publish BAGO v<version>"
# git push origin v<version>
# Ejecutar Build Release Installer Artifact y publicar exclusivamente sus artefactos firmados.
```

---

## Gobernanza de ramas

BAGO trabaja con exactamente tres ramas base:

- `main` — fuente de verdad
- `windows` — adaptación de plataforma
- `android` — adaptación de plataforma

Flujo obligatorio:

1. El trabajo común se fusiona en `main`.
2. Las ramas de plataforma se actualizan desde `main`.
3. No se permiten merges inversos de `windows`/`android` a `main`.

---

## Seguridad

Ver [`backend/docs/SECURITY.md`](backend/docs/SECURITY.md) para la postura de seguridad y los stops duros.

---

## Documentación

| Documento | Descripción |
|---|---|
| [`DOCUMENTATION.md`](DOCUMENTATION.md) | Índice de documentación vigente e histórica |
| [`backend/MANUAL.md`](backend/MANUAL.md) | Manual histórico de usuario para 4.9.0 |
| [`backend/docs/MVP.md`](backend/docs/MVP.md) | Límite del MVP |
| [`backend/docs/MODULES.md`](backend/docs/MODULES.md) | Matriz de estado de módulos |
| [`backend/docs/CLAIMS.md`](backend/docs/CLAIMS.md) | Matriz de evidencias |
| [`backend/docs/support-matrix.md`](backend/docs/support-matrix.md) | Soporte por sistema operativo |
| [`backend/docs/SECURITY.md`](backend/docs/SECURITY.md) | Defaults de seguridad y gates |
| [`backend/docs/TESTING.md`](backend/docs/TESTING.md) | Comandos de validación |
| [`backend/docs/ARCHITECTURE.md`](backend/docs/ARCHITECTURE.md) | Arquitectura del sistema |

---

## Licencia

BAGO es software propietario en su estado actual.

**Permitido:**
- Inspeccionar el código fuente público.
- Ejecutar validación local.
- Enviar issues o cambios propuestos a través de GitHub.

**No permitido sin permiso escrito:**
- Redistribuir BAGO como paquete competidor.
- Vender copias alojadas o empaquetadas.
- Eliminar la atribución.
- Extraer assets de release privados para distribución de terceros.

La línea de release actual permanece propietaria.
