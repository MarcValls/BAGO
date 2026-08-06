## BAGO v4.8.2

Release estable centrada en reproducibilidad, trazabilidad y robustez del instalador.

### Cambios clave

- Instalador NSIS fail-closed: aborta ante cualquier paso critico fallido.
- Instalacion fijada a referencia inmutable (`v4.8.2`) en lugar de `main` mutable.
- Verificacion final de `BAGO.exe` antes de registrar instalacion y accesos directos.
- Endurecimiento de Electron: instancia unica y espera activa de `/health` antes de abrir UI.
- Validacion canonica de release completada para el corte 4.8.2.

### Artefactos

| Archivo | Tamano (bytes) | SHA-256 |
|---|---:|---|
| `bago-4.8.2-setup.exe` | 79,571 | `8c131d5bc7c21b046e0f9cf587a913bb634df2ad78a9f727682c4d46248b9ddc` |
| `bago-4.8.2-backend.zip` | 214,569,936 | `66d45e999f86e2d2ec0220fd49fdca0f815758884038a8fe6864dc29300437c9` |
| `bago-4.8.2-frontend.zip` | 178,546 | `d3b853e36dfeafd2f14632a52055b95165d85ceb66460b935d428f15c9612805` |
| `bago-4.8.2-electron-viewer.zip` | 13,097 | `01e5e34cad39274902fda5fd3531f630210d08c39d53cd7d8deb71046ef38fa3` |
| `bago-4.8.2-installer.ps1` | 2,774 | `342fac60364e5281ef1e5a7535c8c0ee8d7df46d5140d7c3d3538c176883a91e` |

### Instalacion recomendada (Windows)

1. Descarga y ejecuta `bago-4.8.2-setup.exe`.
2. Abre BAGO desde el acceso directo de Escritorio o Menu Inicio.
3. Verifica integridad con los archivos `.sha256` publicados en esta release.

### Trazabilidad

- Tag: `v4.8.2`
- Instalacion por usuario: `%LOCALAPPDATA%\BAGO`
- Registro: `HKCU\Software\BAGO` (`InstallPath`, `InstallRef`)
