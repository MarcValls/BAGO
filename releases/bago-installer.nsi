; BAGO 4.8.1 Windows Installer
; Built with NSIS 3.x

!define APP_NAME "BAGO"
!define APP_VERSION "4.8.1"
!define APP_PUBLISHER "MarcValls"
!define APP_URL "https://github.com/MarcValls/BAGO"
!define INSTALL_DIR "$PROGRAMFILES64\BAGO"
!define UNINSTALL_REG "Software\Microsoft\Windows\CurrentVersion\Uninstall\BAGO"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "bago-4.8.1-setup.exe"
InstallDir "${INSTALL_DIR}"
InstallDirRegKey HKLM "Software\BAGO" "InstallPath"
RequestExecutionLevel admin
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
  SetOutPath "$INSTDIR"

  ; Archivos raíz
  File /oname=ARRANCAR_BAGO.bat "..\ARRANCAR_BAGO.bat"
  File /oname=DETENER_BAGO.bat "..\DETENER_BAGO.bat"
  File /oname=README.md "..\README.md"
  File /oname=bago.ico "..\releases\bago.ico"

  ; Scripts
  SetOutPath "$INSTDIR\scripts"
  File /oname=dev.ps1 "..\scripts\dev.ps1"
  File /oname=bago-launcher.ps1 "..\scripts\bago-launcher.ps1"

  ; Backend y frontend como ZIPs (se extraen mediante install-v4.ps1)
  SetOutPath "$INSTDIR"
  File /oname=install-v4.ps1 "..\backend\install-v4.ps1"
  File /oname=bago-4.8.1-backend.zip "..\releases\bago-4.8.1-backend.zip"
  File /oname=bago-4.8.1-frontend.zip "..\releases\bago-4.8.1-frontend.zip"

  ; Instalar backend extrayendo el ZIP
  DetailPrint "Instalando BAGO backend..."
  nsExec::ExecToLog 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\install-v4.ps1" -Mode Express -PackageZip "$INSTDIR\bago-4.8.1-backend.zip" -SkipTests'
  Pop $0
  DetailPrint "Resultado del instalador: $0"

  ; Registry
  WriteRegStr HKLM "Software\BAGO" "InstallPath" "$INSTDIR"
  WriteRegStr HKLM "Software\BAGO" "Version" "${APP_VERSION}"
  WriteRegStr HKLM "${UNINSTALL_REG}" "DisplayName" "${APP_NAME} ${APP_VERSION}"
  WriteRegStr HKLM "${UNINSTALL_REG}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKLM "${UNINSTALL_REG}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKLM "${UNINSTALL_REG}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKLM "${UNINSTALL_REG}" "URLInfoAbout" "${APP_URL}"
  WriteRegDWORD HKLM "${UNINSTALL_REG}" "NoModify" 1
  WriteRegDWORD HKLM "${UNINSTALL_REG}" "NoRepair" 1

  ; Uninstaller
  WriteUninstaller "$INSTDIR\uninstall.exe"

  ; ── Accesos directos ──────────────────────────────────────────────────────
  ; Un icono "BAGO" que arranca el backend + abre la ventana.
  ; Al cerrar la ventana el backend para solo (hook before-quit en main.cjs).
  CreateDirectory "$SMPROGRAMS\BAGO"

  CreateShortcut "$SMPROGRAMS\BAGO\BAGO.lnk" "powershell.exe" '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "$INSTDIR\scripts\bago-launcher.ps1"' "$INSTDIR\bago.ico" 0 SW_SHOWMINIMIZED "" "Abrir BAGO"
  CreateShortcut "$DESKTOP\BAGO.lnk" "powershell.exe" '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "$INSTDIR\scripts\bago-launcher.ps1"' "$INSTDIR\bago.ico" 0 SW_SHOWMINIMIZED "" "Abrir BAGO"
  CreateShortcut "$SMPROGRAMS\BAGO\Desinstalar BAGO.lnk" "$INSTDIR\uninstall.exe"

SectionEnd

;--- Uninstaller ---
Section "Uninstall"
  Delete "$INSTDIR\bago-4.8.1-backend.zip"
  Delete "$INSTDIR\bago-4.8.1-frontend.zip"
  Delete "$INSTDIR\install-v4.ps1"
  Delete "$INSTDIR\ARRANCAR_BAGO.bat"
  Delete "$INSTDIR\DETENER_BAGO.bat"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\bago.ico"
  Delete "$INSTDIR\scripts\dev.ps1"
  Delete "$INSTDIR\scripts\bago-launcher.ps1"
  RMDir  "$INSTDIR\scripts"
  Delete "$INSTDIR\uninstall.exe"
  RMDir  "$INSTDIR"

  Delete "$SMPROGRAMS\BAGO\BAGO.lnk"
  Delete "$SMPROGRAMS\BAGO\Desinstalar BAGO.lnk"
  RMDir  "$SMPROGRAMS\BAGO"
  Delete "$DESKTOP\BAGO.lnk"

  DeleteRegKey HKLM "Software\BAGO"
  DeleteRegKey HKLM "${UNINSTALL_REG}"
SectionEnd
