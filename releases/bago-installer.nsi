; BAGO 4.8.2 Windows Installer - NSIS 3.x
; Descargar paquete precompilado desde GitHub Release

!define APP_NAME "BAGO"
!ifndef APP_VERSION
!define APP_VERSION "4.8.2"
!endif
!define APP_PUBLISHER "MarcValls"
!define APP_URL "https://github.com/MarcValls/BAGO"
!define UNINSTALL_REG "Software\Microsoft\Windows\CurrentVersion\Uninstall\BAGO"
!define INSTALL_DIR "$LOCALAPPDATA\BAGO"
!define BACKEND_ZIP_URL "https://github.com/MarcValls/BAGO/releases/download/v4.8.2/bago-4.8.2-backend.zip"

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
  
  DetailPrint "Extrayendo herramientas..."
  SetOutPath "$TEMP"
  File /oname=bago-download.ps1 "Install-BAGO.ps1"
  
  DetailPrint "Descargando y extrayendo BAGO 4.8.2 (5-10 minutos)..."
  nsExec::ExecToLog 'powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& {$ErrorActionPreference=''Stop''; $repoRoot=''${INSTALL_DIR}''; $tag=''v4.8.2''; $repo=''MarcValls/BAGO''; $backendZipUrl=''${BACKEND_ZIP_URL}''; $tempZip=Join-Path $env:TEMP ''bago-4.8.2-backend.zip''; $tempExtract=Join-Path $env:TEMP ''bago-backend-tmp''; try { Write-Host ''Descargando...''; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri $backendZipUrl -OutFile $tempZip -UseBasicParsing; Write-Host ''Extrayendo...''; Expand-Archive -LiteralPath $tempZip -DestinationPath $tempExtract -Force; Write-Host ''Instalando...''; Copy-Item -Path (Join-Path $tempExtract ''backend'') -Destination (Join-Path $repoRoot ''backend'') -Recurse -Force; Copy-Item -Path (Join-Path $tempExtract ''electron-viewer'') -Destination (Join-Path $repoRoot ''electron-viewer'') -Recurse -Force; Write-Host ''Limpiando...''; Remove-Item $tempZip -Force -ErrorAction SilentlyContinue; Remove-Item $tempExtract -Recurse -Force -ErrorAction SilentlyContinue; Write-Host ''OK'' } catch { throw $_ } }"' $0
  
  ${If} $0 != 0
    MessageBox MB_ICONSTOP|MB_OK "Descarga/Extracción fallida (código $0).$\n$\nAsegúrate de tener conexión a Internet."
    Abort
  ${EndIf}
  
  DetailPrint "Verificando instalación..."
  ${IfNot} ${FileExists} "${INSTALL_DIR}\electron-viewer\dist\win-unpacked\BAGO.exe"
    MessageBox MB_ICONSTOP|MB_OK "Error: BAGO.exe no se encontró tras descargar."
    Abort
  ${EndIf}
  
  DetailPrint "Creando accesos directos..."
  SetOutPath "${INSTALL_DIR}\electron-viewer"
  File /oname=bago.ico "bago.ico"
  
  DetailPrint "Registrando aplicación..."
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
  CreateShortcut "$SMPROGRAMS\BAGO\BAGO.lnk" "${INSTALL_DIR}\electron-viewer\dist\win-unpacked\BAGO.exe" "" "${INSTALL_DIR}\electron-viewer\bago.ico" 0
  CreateShortcut "$DESKTOP\BAGO.lnk" "${INSTALL_DIR}\electron-viewer\dist\win-unpacked\BAGO.exe" "" "${INSTALL_DIR}\electron-viewer\bago.ico" 0
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
