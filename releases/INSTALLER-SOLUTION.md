# BAGO 4.8.2 Installation Solution - Final

## El Problema

Durante 2 días intentamos resolver el instalador para BAGO 4.8.2:
- ❌ Compilar en la máquina del usuario (requiere git, node, python, toma 15+ min)
- ❌ Descargar source y compilar (mismo problema)
- ❌ ps2exe PowerShell → SmartScreen warnings
- ❌ NSIS con download dinámico → internet required, complex logic
- ❌ Binarios compilados en git → exceden límite de GitHub (100 MB)

## La Solución: Build Local → Package NSIS

### Workflow para Desarrolladores/Releases

```
1. Clonar/actualizar repo
   git clone https://github.com/MarcValls/BAGO.git
   cd BAGO

2. Compilar BAGO.exe (una sola vez cuando hay cambios)
   cd electron-viewer
   npm install
   npm run dist
   # Genera: electron-viewer/dist/win-unpacked/BAGO.exe (216 MB)

3. Compilar instalador
   cd ../releases
   .\build-installer.ps1
   # Genera: bago-4.8.2-setup.exe (~240 MB)

4. Probar instalador
   .\bago-4.8.2-setup.exe
   # Instala BAGO en %LOCALAPPDATA%\BAGO\
   # Usuario hace click y ejecuta
```

### Resultado Final para el Usuario

El usuario descarga un único archivo:
- **bago-4.8.2-setup.exe** (~240 MB)
  - Click → InstallShield NSIS
  - Extrae BAGO.exe, backend, y archivos necesarios
  - Crea shortcuts en Desktop + Start Menu
  - Done

**No requiere:** git, node.js, internet, Python, compilación, downloads
**Instala en:** %LOCALAPPDATA%\BAGO\

## Archivos en el Repo

### Nuevos
- `releases/bago-installer-local.nsi` — Configuración NSIS
- `releases/build-installer.ps1` — Script para compilar installer
- `releases/BUILD-INSTALLER.md` — Documentación

### Requisitos
- **NSIS 3.x** instalado (Windows)
  - Download: https://nsis.sourceforge.io/Download
  - Chocolatey: `choco install nsis -y`

## Importante: Actualizar Instalador

**Cada vez que actualices BAGO:**

1. Compilation only changes en backend/ o electron-viewer/:
   ```
   cd electron-viewer && npm run dist
   cd ../releases && .\build-installer.ps1
   ```

2. Commitar NSIS scripts (no binarios):
   ```
   git add releases/*.nsi releases/build-installer.ps1
   git commit -m "Update BAGO installer"
   git push
   ```

3. Subir bago-4.8.2-setup.exe a GitHub Releases (v4.8.2 tag)

## Por qué este Enfoque

✓ **Simple:** Un .exe que "just works"
✓ **Offline:** No requiere internet durante instalación  
✓ **Seguro:** Binarios compilados localmente, verificados antes de empacar
✓ **Git-friendly:** No almacena binarios de 216 MB en repositorio
✓ **Reproducible:** Mismo source → mismo .exe (si npm/electron-builder es determinista)

## Próximos Pasos

- [ ] Instalar NSIS si no lo tienes
- [ ] Ejecutar `npm run dist` en electron-viewer
- [ ] Ejecutar `.\build-installer.ps1` en releases/
- [ ] Prueba de instalación en máquina limpia
- [ ] Subir bago-4.8.2-setup.exe a GitHub Releases
- [ ] Verificar que no hay SmartScreen warnings
- [ ] Smoke test: ejecutar BAGO, verificar backend health

## Status de v4.8.2

✓ BAGO.exe compilado
✓ NSIS installer scripts creados
✓ build-installer.ps1 listo
⏳ NSIS compilation (requiere NSIS instalado)
⏳ Testing e2e
⏳ GitHub release upload
