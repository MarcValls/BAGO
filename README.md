# BAGO v4.8.2

[![Version](https://img.shields.io/badge/version-4.8.2-blue)](https://github.com/MarcValls/BAGO/releases/tag/v4.8.2)
[![CI](https://github.com/MarcValls/BAGO/actions/workflows/canonical-ci.yml/badge.svg)](https://github.com/MarcValls/BAGO/actions/workflows/canonical-ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![Node](https://img.shields.io/badge/node-20%2B-green)]()
[![Tests](https://img.shields.io/badge/tests-844%20passed%20%7C%2014%20skipped%20backend%20%7C%2052%20frontend-brightgreen)]()
[![License](https://img.shields.io/badge/license-Proprietary-red)]()

**BAGO** es un plano de control de IA local. Su función principal es mantener la sesión como fuente de verdad mientras los proveedores y modelos permanecen como motores de ejecución intercambiables.

---

## Novedades en 4.8.2

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
- Instalador Windows `bago-4.8.2-setup.exe` (NSIS) — instala todos los componentes y crea accesos directos
- Script `install-v4.ps1` con soporte para `-PackageZip`

---



La mayoría de herramientas de IA vinculan el contexto a un único proveedor o modelo. BAGO separa el estado de sesión de la ejecución del modelo, permitiendo al usuario mantener la continuidad al cambiar de proveedor, modelo, superficie de API o superficie de UI.

---

## Estructura del monorepo

```
BAGO/
├── backend/                  # Runtime Python (core, CLI, API local, contratos)
│   ├── bago_core/            # Núcleo: sesiones, proveedores, capacidades, RL
│   ├── tests/                # 844 passed, 14 skipped (pytest)
│   ├── docs/                 # Documentación técnica
│   └── ui-react/dist/        # Copia del build de la UI (generada por npm run build)
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
│   ├── dev.ps1               # start / stop / build / status
│   └── bago-launcher.ps1     # Lanzador manual legacy (los accesos directos apuntan a BAGO.exe)
├── releases/
│   ├── bago-installer.nsi    # Script NSIS para generar setup.exe
│   └── bago-4.8.2-*.zip      # Artefactos de release
├── ARRANCAR_BAGO.bat         # Lanzador principal Windows
└── package.json              # Raíz del workspace npm
```

---

## Requisitos

| Componente | Versión mínima |
|---|---|
| Windows | 10 / 11 (plataforma principal) |
| Python | 3.11+ |
| Node.js | 20.19.0 o ≥ 22.12.0 |
| npm | ≥ 10.0.0 |
| Ollama | Opcional — necesario para el path local con modelo en vivo |

> macOS y Linux son experimentales hasta que sus gates de instalación y runtime sean verificados.

---

## Instalación

### Opción A — Instalador Windows (recomendado)

Descarga `bago-4.8.2-setup.exe` desde [Releases](https://github.com/MarcValls/BAGO/releases/tag/v4.8.2) y ejecútalo. El instalador:
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
# Arrancar backend + abrir UI en el navegador
npm run start

# Sólo el backend
npm run start:backend

# Build de producción
npm run build
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
npm run start      # Arrancar frontend + backend
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
| Runtime core | ✅ Estable | 844 passed, 14 skipped en backend |
| Instalación Windows | ✅ Estable | Instalador NSIS + `ARRANCAR_BAGO.bat` |
| Ciclo de vida Electron | ✅ Estable | Auto-stop al cerrar ventana |
| UI React | ✅ Funcional | 52 tests frontend, tema claro/oscuro, tokens CSS |
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
| [v4.8.2](https://github.com/MarcValls/BAGO/releases/tag/v4.8.2) | 2026-08-06 | `bago-4.8.2-setup.exe` · `backend.zip` · `frontend.zip` · `electron-viewer.zip` |

Los artefactos de release deben generarse desde una referencia etiquetada/inmutable (no desde `main`) con:

```powershell
npm run build
# luego reempaquetar con releases/bago-installer.nsi y gh release upload
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
| [`backend/MANUAL.md`](backend/MANUAL.md) | Manual de usuario (español) |
| [`backend/docs/MVP.md`](backend/docs/MVP.md) | Límite del MVP |
| [`backend/docs/MODULES.md`](backend/docs/MODULES.md) | Matriz de estado de módulos |
| [`backend/docs/CLAIMS.md`](backend/docs/CLAIMS.md) | Matriz de evidencias |
| [`backend/docs/SUPPORT_MATRIX.md`](backend/docs/SUPPORT_MATRIX.md) | Soporte por sistema operativo |
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
