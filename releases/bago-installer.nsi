; BAGO 4.8.2 Windows Installer
; Built with NSIS 3.x
;
; Estrategia: clona el repositorio GitHub en el directorio de instalacion,
; instala dependencias, compila el frontend y empaqueta el app con
; electron-builder para obtener un BAGO.exe nativo.

!define APP_NAME "BAGO"
!define APP_VERSION "4.8.2"
!define APP_GIT_REF "v4.8.2"
!define APP_GIT_SHA "6ed4e9daf7201e90dcb429ad8654a71ed1766db3"
!define APP_PUBLISHER "MarcValls"
!define APP_REPO "https://github.com/MarcValls/BAGO.git"
!define APP_URL "https://github.com/MarcValls/BAGO"
!define INSTALL_DIR "$LOCALAPPDATA\BAGO"
!define UNINSTALL_REG "Software\Microsoft\Windows\CurrentVersion\Uninstall\BAGO"
!define EXE_PATH "$INSTDIR\electron-viewer\dist\win-unpacked\BAGO.exe"

!macro AbortWithMessage MSG
  MessageBox MB_ICONSTOP|MB_OK "${MSG}"
  Abort
!macroend

Name "${APP_NAME} ${APP_VERSION}"
OutFile "bago-4.8.2-setup.exe"
InstallDir "${INSTALL_DIR}"
InstallDirRegKey HKCU "Software\BAGO" "InstallPath"
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails show
ShowUnInstDetails show

;--- Pages ---
!include "MUI2.nsh"
!define MUI_ABORTWARNING
!define MUI_ICON "..\releases\bago.ico"
!define MUI_UNICON "..\releases\bago.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "Spanish"

;--- Installer ---
Section "BAGO Core" SecCore
  SectionIn RO

  ; ---- 1. Verificar prerequisitos -----------------------------------------
  DetailPrint "Verificando prerequisitos..."

  nsExec::ExecToLog 'git --version'
  Pop $0
  IntCmp $0 0 git_ok 0 0
    MessageBox MB_ICONEXCLAMATION|MB_OK "Git no esta instalado.$\nDescargalo desde https://git-scm.com y vuelve a ejecutar el instalador."
    Abort
  git_ok:

  nsExec::ExecToLog 'node --version'
  Pop $0
  IntCmp $0 0 node_ok 0 0
    MessageBox MB_ICONEXCLAMATION|MB_OK "Node.js no esta instalado.$\nDescargalo desde https://nodejs.org (v20 o v22) y vuelve a ejecutar el instalador."
    Abort
  node_ok:

  nsExec::ExecToLog 'python --version'
  Pop $0
  IntCmp $0 0 python_ok 0 0
    MessageBox MB_ICONEXCLAMATION|MB_OK "Python no esta instalado.$\nDescargalo desde https://python.org (3.11+) y vuelve a ejecutar el instalador."
    Abort
  python_ok:

  ; ---- 2. Clonar o actualizar repositorio ---------------------------------
  ; Origen inmutable: siempre instalar desde una referencia fija (tag/commit).
  IfFileExists "$INSTDIR\.git\HEAD" update_repo clone_repo

  clone_repo:
    DetailPrint "Clonando repositorio BAGO (requiere conexion a Internet)..."
    nsExec::ExecToLog 'git clone --depth 1 --branch "${APP_GIT_REF}" "${APP_REPO}" "$INSTDIR"'
    Pop $0
    IntCmp $0 0 clone_ok 0 0
      DetailPrint "Clone shallow por tag fallido. Reintentando con init + fetch de ref inmutable..."
      RMDir /r "$INSTDIR"
      CreateDirectory "$INSTDIR"
      nsExec::ExecToLog 'git -C "$INSTDIR" init'
      Pop $0
      IntCmp $0 0 clone_fallback_ok 0 0
        !insertmacro AbortWithMessage "Error al inicializar el repositorio local en $INSTDIR."
      clone_fallback_ok:
      nsExec::ExecToLog 'git -C "$INSTDIR" remote add origin "${APP_REPO}"'
      Pop $0
      IntCmp $0 0 clone_remote_ok 0 0
        !insertmacro AbortWithMessage "Error al configurar origin (${APP_REPO})."
      clone_remote_ok:
      nsExec::ExecToLog 'git -C "$INSTDIR" fetch --depth 1 --tags --force origin "${APP_GIT_REF}"'
      Pop $0
      IntCmp $0 0 clone_fetch_tags_ok 0 0
        !insertmacro AbortWithMessage "Fallo al descargar la ref inmutable ${APP_GIT_REF} desde origin."
      clone_fetch_tags_ok:
      nsExec::ExecToLog 'git -C "$INSTDIR" checkout --force "${APP_GIT_REF}^{commit}"'
      Pop $0
      IntCmp $0 0 clone_checkout_ok 0 0
        !insertmacro AbortWithMessage "Fallo al fijar la ref inmutable ${APP_GIT_REF}."
      clone_checkout_ok:
      nsExec::ExecToLog 'git -C "$INSTDIR" checkout --force "${APP_GIT_SHA}"'
      Pop $0
      IntCmp $0 0 clone_sha_ok 0 0
        !insertmacro AbortWithMessage "La release no coincide con el commit esperado ${APP_GIT_SHA}."
      clone_sha_ok:
    clone_ok:
    Goto deps

  update_repo:
    DetailPrint "Actualizando instalacion existente a ${APP_GIT_REF}..."
    nsExec::ExecToLog 'git -C "$INSTDIR" fetch --depth 1 origin "refs/tags/${APP_GIT_REF}:refs/tags/${APP_GIT_REF}"'
    Pop $0
    IntCmp $0 0 fetch_ok 0 0
      !insertmacro AbortWithMessage "Fallo al sincronizar origin y sus tags."
    fetch_ok:
    nsExec::ExecToLog 'git -C "$INSTDIR" checkout --force "${APP_GIT_REF}^{commit}"'
    Pop $0
    IntCmp $0 0 checkout_ok 0 0
      !insertmacro AbortWithMessage "Fallo al hacer checkout de la ref ${APP_GIT_REF}."
    checkout_ok:
    nsExec::ExecToLog 'git -C "$INSTDIR" reset --hard "${APP_GIT_REF}^{commit}"'
    Pop $0
    IntCmp $0 0 update_ok 0 0
      !insertmacro AbortWithMessage "Fallo al fijar el estado exacto de ${APP_GIT_REF}."
    update_ok:
    nsExec::ExecToLog 'git -C "$INSTDIR" checkout --force "${APP_GIT_SHA}"'
    Pop $0
    IntCmp $0 0 update_sha_ok 0 0
      !insertmacro AbortWithMessage "La release no coincide con el commit esperado ${APP_GIT_SHA}."
    update_sha_ok:
    Goto deps

  ; ---- 3. Instalar dependencias Node.js (incluye Electron) ----------------
  deps:
  DetailPrint "Instalando dependencias Node.js del monorepo..."
  nsExec::ExecToLog 'cmd /c "cd /d "$INSTDIR" && npm install 2>&1"'
  Pop $0
  IntCmp $0 0 npm_root_ok 0 0
    !insertmacro AbortWithMessage "npm install (raiz) ha fallado con codigo $0."
  npm_root_ok:

  DetailPrint "Instalando dependencias del electron-viewer (con electron-builder)..."
  nsExec::ExecToLog 'cmd /c "cd /d "$INSTDIR\electron-viewer" && npm install 2>&1"'
  Pop $0
  IntCmp $0 0 npm_electron_ok 0 0
    !insertmacro AbortWithMessage "npm install (electron-viewer) ha fallado con codigo $0."
  npm_electron_ok:

  ; ---- 4. Instalar entorno Python (backend) --------------------------------
  DetailPrint "Configurando entorno Python del backend..."
  nsExec::ExecToLog 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\backend\install-v4.ps1" -Mode Express -SkipTests'
  Pop $0
  IntCmp $0 0 backend_ok 0 0
    !insertmacro AbortWithMessage "install-v4.ps1 ha fallado con codigo $0."
  backend_ok:

  ; ---- 5. Build del frontend -----------------------------------------------
  DetailPrint "Compilando interfaz de usuario..."
  nsExec::ExecToLog 'cmd /c "cd /d "$INSTDIR" && npm run build 2>&1"'
  Pop $0
  IntCmp $0 0 build_ok 0 0
    !insertmacro AbortWithMessage "npm run build ha fallado con codigo $0."
  build_ok:

  ; ---- 6. Empaquetar app Electron (genera BAGO.exe) -----------------------
  DetailPrint "Empaquetando BAGO.exe con electron-builder..."
  nsExec::ExecToLog 'cmd /c "cd /d "$INSTDIR\electron-viewer" && npx electron-builder --dir 2>&1"'
  Pop $0
  IntCmp $0 0 eb_ok 0 0
    !insertmacro AbortWithMessage "electron-builder --dir ha fallado con codigo $0."
  eb_ok:

  ; ---- 7. Gate final de integridad de instalacion --------------------------
  IfFileExists "${EXE_PATH}" exe_ok 0
    !insertmacro AbortWithMessage "Instalacion incompleta: no existe ${EXE_PATH}."
  exe_ok:

  ; ---- 8. Copiar icono al directorio empaquetado ---------------------------
  SetOutPath "$INSTDIR\electron-viewer"
  File /oname=bago.ico "..\releases\bago.ico"

  ; ---- 9. Registro ---------------------------------------------------------
  WriteRegStr HKCU "Software\BAGO" "InstallPath" "$INSTDIR"
  WriteRegStr HKCU "Software\BAGO" "Version" "${APP_VERSION}"
  WriteRegStr HKCU "Software\BAGO" "InstallRef" "${APP_GIT_REF}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "DisplayName" "${APP_NAME} ${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKCU "${UNINSTALL_REG}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "URLInfoAbout" "${APP_URL}"
  WriteRegDWORD HKCU "${UNINSTALL_REG}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_REG}" "NoRepair" 1

  WriteUninstaller "$INSTDIR\uninstall.exe"

  ; ---- 10. Accesos directos al BAGO.exe nativo -----------------------------
  ; Apunta directamente al ejecutable empaquetado: sin consola, sin powershell.
  CreateDirectory "$SMPROGRAMS\BAGO"
  CreateShortcut "$SMPROGRAMS\BAGO\BAGO.lnk" "${EXE_PATH}" "" "$INSTDIR\electron-viewer\bago.ico" 0 "" "" "Abrir BAGO"
  CreateShortcut "$DESKTOP\BAGO.lnk" "${EXE_PATH}" "" "$INSTDIR\electron-viewer\bago.ico" 0 "" "" "Abrir BAGO"
  CreateShortcut "$SMPROGRAMS\BAGO\Desinstalar BAGO.lnk" "$INSTDIR\uninstall.exe"

SectionEnd

;--- Uninstaller ---
Section "Uninstall"
  ; Intentar detener el backend antes de borrar
  nsExec::ExecToLog 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\scripts\dev.ps1" stop'
  Pop $0

  ; Eliminar todo el directorio (incluye el repo clonado y node_modules)
  RMDir /r "$INSTDIR"

  Delete "$SMPROGRAMS\BAGO\BAGO.lnk"
  Delete "$SMPROGRAMS\BAGO\Desinstalar BAGO.lnk"
  RMDir  "$SMPROGRAMS\BAGO"
  Delete "$DESKTOP\BAGO.lnk"

  DeleteRegKey HKCU "Software\BAGO"
  DeleteRegKey HKCU "${UNINSTALL_REG}"
SectionEnd