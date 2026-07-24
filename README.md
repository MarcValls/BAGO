# BAGO v4.8.1

[![Version](https://img.shields.io/badge/version-4.8.1-blue)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![Node](https://img.shields.io/badge/node-20%2B-green)]()
[![License](https://img.shields.io/badge/license-Proprietary-red)]()

**BAGO** es un plano de control de IA local. Su función principal es mantener la sesión como fuente de verdad mientras los proveedores y modelos permanecen como motores de ejecución intercambiables.

---

## ¿Qué problema resuelve?

La mayoría de herramientas de IA vinculan el contexto a un único proveedor o modelo. BAGO separa el estado de sesión de la ejecución del modelo, permitiendo al usuario mantener la continuidad al cambiar de proveedor, modelo, superficie de API o superficie de UI.

---

## Estructura del monorepo

```
BAGO/
├── backend/          # Runtime Python (core, CLI, API local, contratos)
├── frontend/         # UI React + TypeScript (Vite)
├── electron-viewer/  # Visor Electron (opcional)
├── scripts/          # Scripts de desarrollo (PowerShell / Bash)
├── package.json      # Raíz del workspace npm
└── README.md
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

### Instalación rápida (Windows)

```powershell
git clone https://github.com/MarcValls/BAGO.git
cd BAGO
.\backend\install-v4.ps1 -Mode Express
```

### Instalador remoto (última release publicada)

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

| Área | Estado | Documentación |
|---|---|---|
| Runtime core | ✅ Estable | `backend/docs/CLAIMS.md`, `backend/docs/TESTING.md` |
| Instalación y soporte de plataforma | ✅ Estable | `backend/docs/MVP.md`, `backend/docs/SUPPORT_MATRIX.md` |
| Seguridad y postura API | ✅ Estable | `backend/docs/SECURITY.md` |
| UI React | 🔶 Superficie opcional | `backend/docs/UI_CANONICAL_CONTRACT.md` |
| Capa RL policy | 🧪 Experimental | `backend/docs/MVP.md` |
| Agentes y autopilot | 🧪 Experimental | `backend/docs/MVP.md` |
| Runtime C++ | 🧪 Experimental | `backend/docs/MVP.md` |
| Multiprovider cloud completo | 🔶 Parcial | `backend/docs/SUPPORT_MATRIX.md` |
| Store de conocimiento/embeddings avanzado | 🔶 Parcial | `backend/docs/MODULES.md` |

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
