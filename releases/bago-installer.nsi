; BAGO Windows Installer - NSIS 3.x
; Instalador offline con payload embebido (distribution.zip)

!define APP_NAME "BAGO"
!ifndef APP_VERSION
!define APP_VERSION "4.8.3"
!endif
!ifndef APP_GIT_REF
!define APP_GIT_REF "v4.8.3"
!endif
!ifndef APP_GIT_SHA
!define APP_GIT_SHA "local"
!endif
!define APP_PUBLISHER "MarcValls"
!define APP_URL "https://github.com/MarcValls/BAGO"
!define UNINSTALL_REG "Software\Microsoft\Windows\CurrentVersion\Uninstall\BAGO"
!define INSTALL_DIR "$LOCALAPPDATA\BAGO"
!ifndef DISTRIBUTION_ZIP_FILE
!define DISTRIBUTION_ZIP_FILE "bago-${APP_VERSION}-distribution.zip"
!endif
!ifndef DEV_PS1_FILE
!define DEV_PS1_FILE "..\scripts\dev.ps1"
!endif

Name "${APP_NAME} ${APP_VERSION}"
OutFile "bago-${APP_VERSION}-setup.exe"
InstallDir "${INSTALL_DIR}"
InstallDirRegKey HKCU "Software\BAGO" "InstallPath"
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails show

!include "MUI2.nsh"
!define MUI_ABORTWARNING
!define MUI_ICON "bago.ico"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Spanish"

Section "BAGO Core" SecCore
  SectionIn RO

  DetailPrint "Preparando instalación..."

  DetailPrint "Extrayendo payload offline..."
  SetOutPath "$PLUGINSDIR"
  File /oname=bago-${APP_VERSION}-distribution.zip "${DISTRIBUTION_ZIP_FILE}"
  File /oname=install-embedded-payload.ps1 "install-embedded-payload.ps1"

  DetailPrint "Instalando BAGO ${APP_VERSION} desde payload embebido..."
  ExecWait '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "$PLUGINSDIR\install-embedded-payload.ps1" -RepoRoot "$INSTDIR" -ZipPath "$PLUGINSDIR\bago-${APP_VERSION}-distribution.zip"' $0

  ${If} $0 != 0
    IfSilent +2
    MessageBox MB_ICONSTOP|MB_OK "Instalación fallida (código $0)."
    Abort
  ${EndIf}

  DetailPrint "Verificando instalación..."
  ${IfNot} ${FileExists} "$INSTDIR\electron-viewer\BAGO.exe"
    IfSilent +2
    MessageBox MB_ICONSTOP|MB_OK "Error: BAGO.exe no se encontró tras instalar."
    Abort
  ${EndIf}

  DetailPrint "Instalando launcher de backend..."
  SetOutPath "$INSTDIR\scripts"
  File /oname=dev.ps1 "${DEV_PS1_FILE}"

  DetailPrint "Creando accesos directos..."
  SetOutPath "$INSTDIR\electron-viewer"
  File /oname=bago.ico "bago.ico"

  DetailPrint "Registrando aplicación..."
  WriteRegStr HKCU "Software\BAGO" "InstallPath" "$INSTDIR"
  WriteRegStr HKCU "Software\BAGO" "Version" "${APP_VERSION}"
  WriteRegStr HKCU "Software\BAGO" "InstallRef" "${APP_GIT_REF}"
  WriteRegStr HKCU "Software\BAGO" "InstallSha" "${APP_GIT_SHA}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "DisplayName" "${APP_NAME} ${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKCU "${UNINSTALL_REG}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "URLInfoAbout" "${APP_URL}"
  WriteRegDWORD HKCU "${UNINSTALL_REG}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_REG}" "NoRepair" 1
  WriteUninstaller "$INSTDIR\uninstall.exe"

  CreateDirectory "$SMPROGRAMS\BAGO"
  CreateShortcut "$SMPROGRAMS\BAGO\BAGO.lnk" "$INSTDIR\electron-viewer\BAGO.exe" "" "$INSTDIR\electron-viewer\bago.ico" 0
  CreateShortcut "$DESKTOP\BAGO.lnk" "$INSTDIR\electron-viewer\BAGO.exe" "" "$INSTDIR\electron-viewer\bago.ico" 0
  CreateShortcut "$SMPROGRAMS\BAGO\Desinstalar BAGO.lnk" "$INSTDIR\uninstall.exe"

  DetailPrint "¡Instalación completada!"
SectionEnd

Section "Uninstall"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "Software\BAGO"
  DeleteRegKey HKCU "${UNINSTALL_REG}"
  Delete "$SMPROGRAMS\BAGO\*.*"
  RMDir "$SMPROGRAMS\BAGO"
  Delete "$DESKTOP\BAGO.lnk"
SectionEnd
