; BAGO 4.8.4 global Windows installer - NSIS 3.x
Unicode True

!define APP_NAME "BAGO"
!define APP_VERSION "4.8.4"
!define APP_PUBLISHER "MarcValls"
!define APP_URL "https://github.com/MarcValls/BAGO"
!define INSTALL_DIR "$PROGRAMFILES64\BAGO"
!define UNINSTALL_REG "Software\Microsoft\Windows\CurrentVersion\Uninstall\BAGO"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "bago-4.8.4-setup.exe"
InstallDir "${INSTALL_DIR}"
InstallDirRegKey HKLM "Software\BAGO" "InstallPath"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
SetCompressorDictSize 64
ShowInstDetails show
ShowUninstDetails show
VIProductVersion "4.8.4.0"
VIAddVersionKey /LANG=1034 "ProductName" "BAGO"
VIAddVersionKey /LANG=1034 "ProductVersion" "4.8.4"
VIAddVersionKey /LANG=1034 "FileVersion" "4.8.4.0"
VIAddVersionKey /LANG=1034 "CompanyName" "MarcValls"
VIAddVersionKey /LANG=1034 "FileDescription" "Instalador global BAGO 4.8.4"
VIAddVersionKey /LANG=1034 "LegalCopyright" "MarcValls"

!include "MUI2.nsh"
!include "LogicLib.nsh"

!define MUI_ABORTWARNING
!define MUI_ICON "bago.ico"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Spanish"

Section "BAGO 4.8.4" SecCore
  SectionIn RO
  SetShellVarContext current

  DetailPrint "Extrayendo payload validado..."
  InitPluginsDir
  SetOutPath "$PLUGINSDIR\runtime"
  File /r "compiled\runtime\*.*"

  ${IfNot} ${FileExists} "$PLUGINSDIR\runtime\release_version.txt"
    MessageBox MB_ICONSTOP|MB_OK "Payload invalido: falta release_version.txt."
    Abort
  ${EndIf}
  ${IfNot} ${FileExists} "$PLUGINSDIR\runtime\electron-viewer\BAGO.exe"
    MessageBox MB_ICONSTOP|MB_OK "Payload invalido: falta electron-viewer\BAGO.exe."
    Abort
  ${EndIf}
  ${IfNot} ${FileExists} "$PLUGINSDIR\runtime\electron-viewer\resources\app.asar"
    MessageBox MB_ICONSTOP|MB_OK "Payload invalido: falta Electron app.asar."
    Abort
  ${EndIf}

  DetailPrint "Instalando runtime global en ${INSTALL_DIR}..."
  nsExec::ExecToLog '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "$PLUGINSDIR\runtime\install-v4.ps1" -SourceRoot "$PLUGINSDIR\runtime" -Profile stable -InstallDir "${INSTALL_DIR}" -Mode Express -PreserveDevRole -NoShellIntegration -SkipTests'
  Pop $0
  ${If} $0 != 0
    MessageBox MB_ICONSTOP|MB_OK "La instalacion del runtime fallo (codigo $0). Revise el detalle del instalador."
    Abort
  ${EndIf}

  DetailPrint "Configurando comando global..."
  nsExec::ExecToLog '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "${INSTALL_DIR}\scripts\global-install-shell.ps1" -Action Install -InstallPath "${INSTALL_DIR}"'
  Pop $0
  ${If} $0 != 0
    MessageBox MB_ICONSTOP|MB_OK "No se pudo configurar el comando global BAGO (codigo $0)."
    Abort
  ${EndIf}
  SendMessage ${HWND_BROADCAST} ${WM_SETTINGCHANGE} 0 "STR:Environment" /TIMEOUT=5000

  DetailPrint "Validando instalacion..."
  nsExec::ExecToLog '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "${INSTALL_DIR}\scripts\validate_global_payload.ps1" -Root "${INSTALL_DIR}" -ExpectedVersion "${APP_VERSION}"'
  Pop $0
  ${If} $0 != 0
    MessageBox MB_ICONSTOP|MB_OK "La validacion posinstalacion fallo (codigo $0)."
    Abort
  ${EndIf}

  WriteUninstaller "${INSTALL_DIR}\uninstall.exe"

  WriteRegStr HKLM "Software\BAGO" "InstallPath" "${INSTALL_DIR}"
  WriteRegStr HKLM "Software\BAGO" "Version" "${APP_VERSION}"
  WriteRegStr HKCU "Software\BAGO" "InstallPath" "${INSTALL_DIR}"
  WriteRegStr HKCU "Software\BAGO" "Version" "${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "DisplayName" "${APP_NAME} ${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "InstallLocation" "${INSTALL_DIR}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "DisplayIcon" "${INSTALL_DIR}\electron-viewer\BAGO.exe,0"
  WriteRegStr HKCU "${UNINSTALL_REG}" "UninstallString" '$\"${INSTALL_DIR}\uninstall.exe$\"'
  WriteRegStr HKCU "${UNINSTALL_REG}" "URLInfoAbout" "${APP_URL}"
  WriteRegDWORD HKCU "${UNINSTALL_REG}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_REG}" "NoRepair" 1

  CreateDirectory "$SMPROGRAMS\BAGO"
  CreateShortcut "$SMPROGRAMS\BAGO\BAGO.lnk" "${INSTALL_DIR}\electron-viewer\BAGO.exe" "" "${INSTALL_DIR}\electron-viewer\BAGO.exe" 0 SW_SHOWNORMAL "" "BAGO"
  CreateShortcut "$DESKTOP\BAGO.lnk" "${INSTALL_DIR}\electron-viewer\BAGO.exe" "" "${INSTALL_DIR}\electron-viewer\BAGO.exe" 0 SW_SHOWNORMAL "" "BAGO"
  CreateShortcut "$SMPROGRAMS\BAGO\Desinstalar BAGO.lnk" "${INSTALL_DIR}\uninstall.exe"

  DetailPrint "BAGO ${APP_VERSION} instalado y validado."
SectionEnd

Section "Uninstall"
  SetShellVarContext current
  DetailPrint "Eliminando runtime global; el estado de usuario se conserva."
  nsExec::ExecToLog '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "${INSTALL_DIR}\scripts\global-install-shell.ps1" -Action Uninstall -InstallPath "${INSTALL_DIR}"'
  Pop $0
  SendMessage ${HWND_BROADCAST} ${WM_SETTINGCHANGE} 0 "STR:Environment" /TIMEOUT=5000
  Delete "$DESKTOP\BAGO.lnk"
  Delete "$SMPROGRAMS\BAGO\BAGO.lnk"
  Delete "$SMPROGRAMS\BAGO\Desinstalar BAGO.lnk"
  RMDir "$SMPROGRAMS\BAGO"
  DeleteRegKey HKCU "${UNINSTALL_REG}"
  DeleteRegKey HKCU "Software\BAGO"
  DeleteRegKey HKLM "Software\BAGO"
  RMDir /r "${INSTALL_DIR}"
SectionEnd
