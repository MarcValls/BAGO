# BAGO 4.9.0 Installer Build Process

## Quick Start

```powershell
cd releases
.\build-installer.ps1
```

Esto lee `release_version.txt`, prepara el runtime, y compila el instalador
con BAGO.exe embebido.

Para refrescar únicamente `compiled/runtime` después de un bloque de cambios,
sin tocar el ZIP ni el instalador existentes:

```powershell
cd releases
.\build-installer.ps1 -RuntimeOnly -SkipBuild -Version (Get-Content ..\release_version.txt -Raw).Trim()
```

Este modo aplica las mismas exclusiones, copia los builds existentes de
frontend y Electron, y valida el payload global. `-SkipBuild` requiere que
ambos builds ya existan y correspondan a la versión canónica; sin esa opción,
el script los construye antes de actualizar el runtime.

Para construir runtime y setup desde un checkout concreto, usa el empaquetador
completo con `-GitRef`, `-GitSha` y `-NsisMakensis`. No apuntes el empaquetador
a una rama remota durante la copia: Actions puede seleccionar `source_ref`,
hacer checkout de ese ref y fijar el SHA resuelto como identidad del candidato.

En GitHub Actions, `workflow_dispatch` acepta `source_ref` (rama, tag o SHA).
El workflow registra el SHA exacto resuelto después del checkout y ese SHA es
el que queda embebido en el instalador. Si se omite, usa el ref seleccionado
al lanzar el workflow.

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
- ✓ Ejecuta NSIS para crear `bago-4.9.0-setup.exe`
- ✓ Calcula SHA256

### 3. Subir a GitHub

```powershell
git add releases/compiled/ releases/bago-4.9.0-setup.exe releases/bago-4.9.0-setup.exe.sha256
git commit -m "Update BAGO 4.9.0 installer with precompiled binaries"
git push
git tag -a v4.9.0 -m "BAGO 4.9.0 Release"
git push origin v4.9.0
```

Luego subir a GitHub Releases:
- bago-4.9.0-setup.exe

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

Actualmente se recomienda incluirlo en git para que cada tag v4.9.0 tenga BAGO.exe embebido.

## Verificación

Después de compilar:

```powershell
# Verificar tamaño
ls -lh bago-4.9.0-setup.exe

# Verificar SHA256
cat bago-4.9.0-setup.exe.sha256

# Verificar que NSIS embebió los archivos correctamente
# (Abre el .exe con 7-Zip si quieres inspeccionar)
```

## Troubleshooting

### "NSIS makensis.exe no encontrado"
→ Instala NSIS desde https://nsis.sourceforge.io/Download

### "BAGO.exe no encontrado"
→ Ejecuta `cd electron-viewer && npm run dist`

### Error compilando NSIS
→ Revisa la salida de NSIS, normalmente es un error en `bago-installer.nsi`
