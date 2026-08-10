; BAGO 4.8.4 Windows Installer - NSIS 3.x
; Instala BAGO copiando archivos compilados locales

!define APP_NAME "BAGO"
!define APP_VERSION "4.8.4"
!define APP_PUBLISHER "MarcValls"
!define APP_URL "https://github.com/MarcValls/BAGO"
!define UNINSTALL_REG "Software\Microsoft\Windows\CurrentVersion\Uninstall\BAGO"
!define INSTALL_DIR "$LOCALAPPDATA\BAGO"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "bago-4.8.4-setup.exe"
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
  
  DetailPrint "Preparando directorio de instalacion..."
  RMDir /r "${INSTALL_DIR}"
  CreateDirectory "${INSTALL_DIR}"
  
  DetailPrint "Copiando backend..."
  SetOutPath "${INSTALL_DIR}"
  File /r "compiled\backend\*.*"
  
  DetailPrint "Copiando BAGO compilado..."
  File /r "compiled\electron-viewer\*.*"
  
  DetailPrint "Verificando instalacion..."
  ${IfNot} ${FileExists} "${INSTALL_DIR}\BAGO.exe"
    MessageBox MB_ICONSTOP|MB_OK "Error: BAGO.exe no se encontro."
    Abort
  ${EndIf}
  
  DetailPrint "Creando accesos directos..."
  SetOutPath "${INSTALL_DIR}\win-unpacked"
  File /oname=bago.ico "compiled\electron-viewer\bago.ico"
  
  DetailPrint "Registrando aplicacion..."
  WriteRegStr HKCU "Software\BAGO" "InstallPath" "${INSTALL_DIR}"
  WriteRegStr HKCU "Software\BAGO" "Version" "${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "DisplayName" "${APP_NAME} ${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "UninstallString" '"${INSTALL_DIR}\uninstall.exe"'
  WriteRegStr HKCU "${UNINSTALL_REG}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_REG}" "URLInfoAbout" "${APP_URL}"
  WriteRegDWORD HKCU "${UNINSTALL_REG}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_REG}" "NoRepair" 1
  WriteUninstaller "${INSTALL_DIR}\uninstall.exe"
  
  CreateDirectory "$SMPROGRAMS\BAGO"
  CreateShortcut "$SMPROGRAMS\BAGO\BAGO.lnk" "${INSTALL_DIR}\BAGO.exe" "" "${INSTALL_DIR}\bago.ico" 0
  CreateShortcut "$DESKTOP\BAGO.lnk" "${INSTALL_DIR}\BAGO.exe" "" "${INSTALL_DIR}\bago.ico" 0
  CreateShortcut "$SMPROGRAMS\BAGO\Desinstalar BAGO.lnk" "${INSTALL_DIR}\uninstall.exe"
  
  DetailPrint "Instalacion completada!"

SectionEnd

Section "Uninstall"
  RMDir /r "${INSTALL_DIR}"
  DeleteRegKey HKCU "Software\BAGO"
  DeleteRegKey HKCU "${UNINSTALL_REG}"
  Delete "$SMPROGRAMS\BAGO\*.*"
  RMDir "$SMPROGRAMS\BAGO"
  Delete "$DESKTOP\BAGO.lnk"
<<<<<<< HEAD
=======

>>>>>>> 2f23f79 (fix: resolve merge conflicts in release files)
SectionEnd


