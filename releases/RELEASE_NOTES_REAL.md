## BAGO v4.8.2

Release estable centrada en reproducibilidad, trazabilidad y robustez del instalador.

### Cambios clave

- Instalador NSIS fail-closed: aborta ante cualquier paso crítico fallido.
- Instalación fijada a referencia inmutable (`v4.8.2`) en lugar de `main` mutable.
- Verificación final de `BAGO.exe` antes de registrar instalación y accesos directos.
- Endurecimiento de Electron: instancia única y espera activa de `/health` antes de abrir UI.
- Validación canónica en progreso para el corte 4.8.2 (consultar estado del workflow antes de declarar cierre).

### Artefactos

| Archivo | Tamaño (bytes) | SHA-256 |
|---|---:|---|
| `bago-4.8.2-setup.exe` | 79,709 | `0dcf39dc4fe15732ae189d9b0887ff40ecc9206e0edc83975110030d6c1b984e` |
| `bago-4.8.2-backend.zip` | 214,569,936 | `66d45e999f86e2d2ec0220fd49fdca0f815758884038a8fe6864dc29300437c9` |
| `bago-4.8.2-frontend.zip` | 178,546 | `d3b853e36dfeafd2f14632a52055b95165d85ceb66460b935d428f15c9612805` |
| `bago-4.8.2-electron-viewer.zip` | 13,097 | `01e5e34cad39274902fda5fd3531f630210d08c39d53cd7d8deb71046ef38fa3` |
| `bago-4.8.2-installer.ps1` | 3,611 | `bee3e02a3faaa972ba2204958fbc433ad7be638cf5b206772b2f7a93068d15e4` |

### Instalación recomendada (Windows)

1. Descarga y ejecuta `bago-4.8.2-setup.exe`.
2. Abre BAGO desde el acceso directo de Escritorio o Menú Inicio.
3. Verifica integridad con los archivos `.sha256` publicados en esta release.

### Trazabilidad

- Tag: `v4.8.2`
- Instalación por usuario: `%LOCALAPPDATA%\BAGO`
- Registro: `HKCU\Software\BAGO` (`InstallPath`, `InstallRef`)
