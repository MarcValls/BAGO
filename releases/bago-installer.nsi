; BAGO 4.8.2 Windows Installer - NSIS 3.x
; Instalador offline con payload embebido (distribution.zip)

!define APP_NAME "BAGO"
!ifndef APP_VERSION
!define APP_VERSION "4.8.2"
!endif
!ifndef APP_GIT_REF
!define APP_GIT_REF "v4.8.2"
!endif
!ifndef APP_GIT_SHA
!define APP_GIT_SHA "local"
!endif
!define APP_PUBLISHER "MarcValls"
!define APP_URL "https://github.com/MarcValls/BAGO"
!define UNINSTALL_REG "Software\Microsoft\Windows\CurrentVersion\Uninstall\BAGO"
!define INSTALL_DIR "$LOCALAPPDATA\BAGO"
!define DISTRIBUTION_ZIP_FILE "bago-4.8.2-distribution.zip"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "bago-4.8.2-setup.exe"
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

  DetailPrint "Preparando directorio de instalación..."
  RMDir /r "${INSTALL_DIR}"
  CreateDirectory "${INSTALL_DIR}"

  DetailPrint "Extrayendo payload offline..."
  SetOutPath "$PLUGINSDIR"
  File /oname=bago-4.8.2-distribution.zip "${DISTRIBUTION_ZIP_FILE}"
  File /oname=install-embedded-payload.ps1 "install-embedded-payload.ps1"

  DetailPrint "Instalando BAGO 4.8.2 desde payload embebido..."
  nsExec::ExecToLog 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PLUGINSDIR\install-embedded-payload.ps1" -RepoRoot "$INSTDIR" -ZipPath "$PLUGINSDIR\bago-4.8.2-distribution.zip"' $0

  ${If} $0 != 0
    MessageBox MB_ICONSTOP|MB_OK "Instalación fallida (código $0)."
    Abort
  ${EndIf}

  DetailPrint "Verificando instalación..."
  ${IfNot} ${FileExists} "${INSTALL_DIR}\electron-viewer\BAGO.exe"
    MessageBox MB_ICONSTOP|MB_OK "Error: BAGO.exe no se encontró tras instalar."
    Abort
  ${EndIf}

  DetailPrint "Creando accesos directos..."
  SetOutPath "${INSTALL_DIR}\electron-viewer"
  File /oname=bago.ico "bago.ico"

  DetailPrint "Registrando aplicación..."
  WriteRegStr HKCU "Software\BAGO" "InstallPath" "${INSTALL_DIR}"
  WriteRegStr HKCU "Software\BAGO" "Version" "${APP_VERSION}"
  WriteRegStr HKCU "Software\BAGO" "InstallRef" "${APP_GIT_REF}"
  WriteRegStr HKCU "Software\BAGO" "InstallSha" "${APP_GIT_SHA}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "DisplayName" "${APP_NAME} ${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "UninstallString" '"${INSTALL_DIR}\uninstall.exe"'
  WriteRegStr HKCU "${UNINSTALL_REG}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "URLInfoAbout" "${APP_URL}"
  WriteRegDWORD HKCU "${UNINSTALL_REG}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_REG}" "NoRepair" 1
  WriteUninstaller "${INSTALL_DIR}\uninstall.exe"

  CreateDirectory "$SMPROGRAMS\BAGO"
  CreateShortcut "$SMPROGRAMS\BAGO\BAGO.lnk" "${INSTALL_DIR}\electron-viewer\BAGO.exe" "" "${INSTALL_DIR}\electron-viewer\bago.ico" 0
  CreateShortcut "$DESKTOP\BAGO.lnk" "${INSTALL_DIR}\electron-viewer\BAGO.exe" "" "${INSTALL_DIR}\electron-viewer\bago.ico" 0
  CreateShortcut "$SMPROGRAMS\BAGO\Desinstalar BAGO.lnk" "${INSTALL_DIR}\uninstall.exe"

  DetailPrint "¡Instalación completada!"
SectionEnd

Section "Uninstall"
  RMDir /r "${INSTALL_DIR}"
  DeleteRegKey HKCU "Software\BAGO"
  DeleteRegKey HKCU "${UNINSTALL_REG}"
  Delete "$SMPROGRAMS\BAGO\*.*"
  RMDir "$SMPROGRAMS\BAGO"
  Delete "$DESKTOP\BAGO.lnk"
SectionEnd
