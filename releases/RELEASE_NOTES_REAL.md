## BAGO 4.8.2

Release enfocada en **consistencia de distribución**, **trazabilidad** y **endurecimiento del ciclo de instalación/arranque**.

### Cambios clave

- Instalador NSIS fail-closed (aborta en errores críticos).
- Instalación fijada a referencia Git inmutable (`v4.8.2`).
- Gate de verificación final de `BAGO.exe` antes de registrar instalación.
- Electron reforzado:
  - lock de instancia única,
  - validación de backend `/health` antes de abrir UI,
  - endurecimiento de apertura de enlaces externos.
- CI con smoke empaquetado de `BAGO.exe` (arranque, salud, cierre, parada backend).

### Instalación rápida (Windows)

Descarga `bago-4.8.2-setup.exe` y ejecútalo.  
Los accesos directos creados en Escritorio e Inicio abren `BAGO.exe` directamente.

### Artefactos

| Archivo | Descripción |
|---|---|
| `bago-4.8.2-setup.exe` | Instalador Windows NSIS |
| `bago-4.8.2-backend.zip` | Backend Python |
| `bago-4.8.2-frontend.zip` | Frontend compilado |
| `bago-4.8.2-electron-viewer.zip` | Fuente mínima del viewer Electron |
| `bago-4.8.2-installer.ps1` | Instalador remoto por PowerShell |
