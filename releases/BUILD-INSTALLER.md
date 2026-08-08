# BAGO 4.8.2 Installer Build Process

## Quick Start

```powershell
cd releases
.\build-installer.ps1
```

Esto compilará **bago-4.8.2-setup.exe** con BAGO.exe embebido.

## Prerequisitos

1. **NSIS 3.x** instalado
   - Windows: https://nsis.sourceforge.io/Download
   - O con chocolatey: `choco install nsis -y`

2. **BAGO.exe compilado** (ver abajo)

## Flujo de actualización completo

Cuando actualizas BAGO, debes recompilar el instalador:

### 1. Compilar BAGO.exe (electron-viewer)

```powershell
cd electron-viewer
npm install
npm run dist
```

Esto genera `dist/win-unpacked/BAGO.exe` (~216 MB)

### 2. Compilar instalador

```powershell
cd ..\releases
.\build-installer.ps1
```

El script:
- ✓ Copia BAGO.exe compilado a `compiled/electron-viewer/`
- ✓ Copia backend a `compiled/backend/`
- ✓ Ejecuta NSIS para crear `bago-4.8.2-setup.exe`
- ✓ Calcula SHA256

### 3. Subir a GitHub

```powershell
git add releases/compiled/ releases/bago-4.8.2-setup.exe releases/bago-4.8.2-setup.exe.sha256
git commit -m "Update BAGO 4.8.2 installer with precompiled binaries"
git push
git tag -a v4.8.2 -m "BAGO 4.8.2 Release"
git push origin v4.8.2
```

Luego subir a GitHub Releases:
- bago-4.8.2-setup.exe

## Estructura de instalación

```
%LOCALAPPDATA%\BAGO\
├── backend\                          (backend compilado)
│   ├── bin\
│   ├── src\
│   └── ...
├── BAGO.exe                          (electron app compilada)
├── bago.ico
└── (otros archivos de electron-viewer)
```

El instalador copia recursivamente desde `releases/compiled/` preservando la estructura completa.

## Nota importante: .gitignore

`releases/compiled/` puede ser GRANDE (~500 MB). 

**Opciones:**
1. Incluirlo en git (mejor para releases oficiales)
2. Agregarlo a `.gitignore` y compilar localmente antes de cada release
3. Usar GitHub LFS para reducir tamaño del repositorio

Actualmente se recomienda incluirlo en git para que cada tag v4.8.2 tenga BAGO.exe embebido.

## Verificación

Después de compilar:

```powershell
# Verificar tamaño
ls -lh bago-4.8.2-setup.exe

# Verificar SHA256
cat bago-4.8.2-setup.exe.sha256

# Verificar que NSIS embebió los archivos correctamente
# (Abre el .exe con 7-Zip si quieres inspeccionar)
```

## Troubleshooting

### "NSIS makensis.exe no encontrado"
→ Instala NSIS desde https://nsis.sourceforge.io/Download

### "BAGO.exe no encontrado"
→ Ejecuta `cd electron-viewer && npm run dist`

### Error compilando NSIS
→ Revisa la salida de NSIS, normalmente es un error en `bago-installer-local.nsi`
