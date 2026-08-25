## BAGO v4.9.0 — snapshot histórico obsoleto

> Este documento conserva afirmaciones y referencias de la entrega anterior.
> No describe ni valida el candidato de remediación actual. La identidad Git
> comprobada del tag se registra en `releases/INDEX.md`; las referencias
> antiguas de abajo se mantienen solo como evidencia histórica divergente.

Release estable centrada en correcciones de UI, compatibilidad con Python 3.14 y entrega de artefactos de release coherentes.

### Novedades

- **Selector de tema claro/oscuro** en la cabecera principal, persiste en sesión.
- **Modo claro completamente funcional**: todos los fondos oscuros hardcodeados migrados a variables CSS.
- **Arquitectura CSS por tokens**: `frontend/src/styles/` dividido en `tokens.css`, `reset.css`, `utilities.css`, `components.css` con tokens semánticos de espaciado, tipografía, radios, sombras y duraciones.
- **Ciclo de vida (Windows)**: `ARRANCAR_BAGO.bat` lanza backend, Electron y detiene backend al cerrar; hook `before-quit` en Electron llama a `dev.ps1 stop`; accesos directo en Menú Inicio y Escritorio.
- **Backend y sesiones**: sistema de capacidades avanzado (`capability-anatomy`), soporte multi-conversación con `active_conversation_id`, registro de sesiones (`session registry`), integración del módulo Vision, Provider Center con grid de proveedores configurables.

### Correcciones

- **Detección de GitHub restaurada** — el panel de autenticación vuelve a reportar si `gh` está instalado y si el usuario está autenticado.
- **Navegación lateral reparada** — los botones de drawers de Herramientas, Pipeline y Capacidades ahora abren su panel correspondiente.
- **CI Canonical reparada** — pin de `numpy` a `2.4.4` para evitar el crash de importación en Python 3.14 en Windows.

### Infraestructura

- Repositorio alineado a **Python 3.14+** en workflows, scripts de instalación y documentación.
- Runtime wrapper `backend/.bago/bin/bago.py` versionado.
- Instalador oficial generado con electron-builder NSIS.

### Artefactos

| Archivo | Tamaño (bytes) | SHA-256 |
|---|---:|---|
| `BAGO-Installation-Manager-4.9.0-win-x64.exe` | 102,371,750 | `9ae9507f435debf978a3d268e5b59fc98bd37f45567e652dd976b4b85a012230` |
| `bago-v4.9.0.zip` | 1,800,073 | `7d67ccde3bf77702daf0f79941da662f316af7fff1df48cbaffd902cafcd8f65` |
| `BAGO-Installation-Manager-4.9.0-win-x64.exe.sha256` | 66 | - |
| `bago-v4.9.0.zip.sha256` | 83 | - |
| `bago-v4.9.0.zip.manifest.json` | 122,275 | - |
| `latest.yml` | 182 | - |

### Instalación recomendada (Windows)

1. Descarga `BAGO-Installation-Manager-4.9.0-win-x64.exe` desde la release `v4.9.0`.
2. Doble clic para iniciar la instalación y acepta el prompt de administrador (UAC).
3. Abre BAGO desde el acceso directo de Escritorio o Menú Inicio.
4. Verifica integridad con los archivos `.sha256` publicados en la release.

### Trazabilidad

- Tag: `v4.9.0` (`f1dcd765f63989e1a66a774c8fba9805fdfef3ee`)
- Commit `main`: `4ad27a0a4a154d20740d62bfbc20c888a0f2f3cc`
- Instalación por usuario: `%LOCALAPPDATA%\BAGO`
- Registro: `HKCU\Software\BAGO` (`InstallPath`, `InstallRef`, `Version`)

### Verificación

- Historical release evidence: backend 928 passed / 13 skipped / 188 subtests passed (not transferable to later candidates)
- Historical release evidence: frontend 99 passed (not transferable to later candidates)
- Release gate: PASS
