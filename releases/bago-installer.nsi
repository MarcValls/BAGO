; BAGO 4.8.2 Windows Installer - NSIS 3.x
; Enfoque simplificado: extrae scripts, ejecuta instalación

!define APP_NAME "BAGO"
!ifndef APP_VERSION
!define APP_VERSION "4.8.2"
!endif
!define APP_PUBLISHER "MarcValls"
!define APP_URL "https://github.com/MarcValls/BAGO"
!define UNINSTALL_REG "Software\Microsoft\Windows\CurrentVersion\Uninstall\BAGO"
!define INSTALL_DIR "$LOCALAPPDATA\BAGO"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "bago-4.8.2-setup.exe"
InstallDir "${INSTALL_DIR}"
InstallDirRegKey HKCU "Software\BAGO" "InstallPath"
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails show

!include "MUI2.nsh"
!define MUI_ABORTWARNING
!define MUI_ICON "..\releases\bago.ico"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Spanish"

Section "BAGO Core" SecCore
  SectionIn RO
  
  DetailPrint "Extrayendo scripts..."
  SetOutPath "$TEMP"
  File /oname=bago-install.ps1 "..\releases\bago-install.ps1"
  File /oname=bago-install.cmd "..\releases\run-install.cmd"
  
  DetailPrint "Ejecutando instalación (10-15 minutos)..."
  ExecWait 'cmd.exe /c "$TEMP\bago-install.cmd"' $0
  
  ${If} $0 != 0
    MessageBox MB_ICONSTOP|MB_OK "Instalación fallida (código $0).$\n$\nLog: $TEMP\BAGO-Install-Log.txt"
    Abort
  ${EndIf}
  
  DetailPrint "Verificando..."
  ${IfNot} ${FileExists} "$INSTALL_DIR\electron-viewer\dist\win-unpacked\BAGO.exe"
    MessageBox MB_ICONSTOP|MB_OK "Error: BAGO.exe no se encontró."
    Abort
  ${EndIf}
  
  DetailPrint "Finalizando..."
  SetOutPath "$INSTALL_DIR\electron-viewer"
  File /oname=bago.ico "..\releases\bago.ico"
  
  WriteRegStr HKCU "Software\BAGO" "InstallPath" "$INSTALL_DIR"
  WriteRegStr HKCU "Software\BAGO" "Version" "${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "DisplayName" "${APP_NAME} ${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "UninstallString" '"$INSTALL_DIR\uninstall.exe"'
  WriteRegStr HKCU "${UNINSTALL_REG}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "URLInfoAbout" "${APP_URL}"
  WriteRegDWORD HKCU "${UNINSTALL_REG}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_REG}" "NoRepair" 1
  WriteUninstaller "$INSTALL_DIR\uninstall.exe"
  
  CreateDirectory "$SMPROGRAMS\BAGO"
  CreateShortcut "$SMPROGRAMS\BAGO\BAGO.lnk" "$INSTALL_DIR\electron-viewer\dist\win-unpacked\BAGO.exe" "" "$INSTALL_DIR\electron-viewer\bago.ico" 0
  CreateShortcut "$DESKTOP\BAGO.lnk" "$INSTALL_DIR\electron-viewer\dist\win-unpacked\BAGO.exe" "" "$INSTALL_DIR\electron-viewer\bago.ico" 0
  CreateShortcut "$SMPROGRAMS\BAGO\Desinstalar BAGO.lnk" "$INSTALL_DIR\uninstall.exe"

SectionEnd

Section "Uninstall"
  RMDir /r "$INSTALL_DIR"
  DeleteRegKey HKCU "Software\BAGO"
  DeleteRegKey HKCU "${UNINSTALL_REG}"
  Delete "$SMPROGRAMS\BAGO\*.*"
  RMDir "$SMPROGRAMS\BAGO"
  Delete "$DESKTOP\BAGO.lnk"
SectionEnd
