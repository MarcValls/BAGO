# Windows Execution Patterns — BAGO Knowledge

> **Aprendido:** 2026-05-08  
> **Contexto:** Instalación driver NI Komplete Kontrol S49 MK2  
> **Lección:** El agente no puede pedir al usuario "clic derecho → Ejecutar como Admin" — debe generar scripts auto-elevantes.

---

## PATRÓN: SCRIPT BAT AUTO-ELEVANTE (UAC)

**Problema:** Los scripts `.bat` que requieren privilegios de Admin obligan al usuario a hacer clic derecho → Ejecutar como administrador. BAGO debe evitar esta fricción.

**Solución:** Incluir siempre al inicio de cualquier `.bat` que requiera Admin:

```bat
@echo off
:: AUTO-ELEVACION: si no somos Admin, relanzar como Admin automaticamente
net session >nul 2>&1
if %errorLevel% neq 0 (
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
```

**Cómo funciona:**
1. `net session` falla si no hay privilegios de Admin
2. Si falla (`errorLevel neq 0`), relanza el mismo script (`%~f0`) con UAC via `Start-Process -Verb RunAs`
3. El usuario ve el diálogo UAC de Windows → acepta → el script continúa como Admin
4. El doble clic normal es suficiente — no hace falta clic derecho

**Regla BAGO:** Todo `.bat` que instale software, modifique registro, o acceda a rutas del sistema DEBE incluir este bloque como primeras líneas.

---

## PATRÓN: DESCARGA EN BAT SIN PWSH

**Problema:** `pwsh.exe` (PowerShell 7) puede no estar instalado. `powershell.exe` (5.1) siempre está en Windows 7+.

**Solución:** Usar `powershell` (sin `.exe`) + `curl` como fallback:

```bat
:: Intento 1: PowerShell 5.1 nativo (siempre disponible en Windows)
powershell -Command "Invoke-WebRequest -Uri '%URL%' -OutFile '%DEST%' -UseBasicParsing"

:: Intento 2: curl (disponible en Windows 10 1803+)
if not exist "%DEST%" (
    curl -L -o "%DEST%" "%URL%"
)

:: Verificar descarga
if not exist "%DEST%" (
    echo ERROR: No se pudo descargar.
    pause & exit /b 1
)
```

**Regla BAGO:** Nunca asumir `pwsh.exe`. Usar `powershell` (5.1) + `curl` fallback.

---

## PATRÓN: EXTRACCIÓN ZIP EN BAT

```bat
powershell -Command "Expand-Archive -Path '%ZIP%' -DestinationPath '%DIR%' -Force"
```

PowerShell 5.1 incluye `Expand-Archive` nativamente desde Windows 10.

---

## PATRÓN: BUSCAR Y EJECUTAR EXE RECURSIVO

```bat
for /r "%EXTRACTDIR%" %%f in (*.exe) do (
    powershell -Command "Start-Process '%%f' -Verb RunAs -Wait"
    goto :done
)
:done
```

---

## PLANTILLA COMPLETA: DESCARGA + EXTRAE + INSTALA

```bat
@echo off
net session >nul 2>&1
if %errorLevel% neq 0 (
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

set URL=https://example.com/driver.zip
set DEST=%USERPROFILE%\Downloads\driver.zip
set DIR=%USERPROFILE%\Downloads\driver_extracted

echo [1/3] Descargando...
powershell -Command "Invoke-WebRequest -Uri '%URL%' -OutFile '%DEST%' -UseBasicParsing"
if not exist "%DEST%" curl -L -o "%DEST%" "%URL%"
if not exist "%DEST%" (echo ERROR & pause & exit /b 1)

echo [2/3] Extrayendo...
powershell -Command "Expand-Archive -Path '%DEST%' -DestinationPath '%DIR%' -Force"

echo [3/3] Instalando...
for /r "%DIR%" %%f in (*.exe) do (
    powershell -Command "Start-Process '%%f' -Verb RunAs -Wait"
    goto :done
)
:done
echo Listo. Conecta el dispositivo.
pause
```

---

## PATRÓN: "DOBLE CLICK" AUTÓNOMO (ejecutar .bat desde el agente)

**Cuando pwsh SÍ está instalado** — el agente hace el doble click él solo:

```powershell
# Equivale a doble click + UAC (Admin)
Start-Process -FilePath "C:\ruta\script.bat" -Verb RunAs -Wait

# Doble click simple (sin Admin):
Start-Process -FilePath "C:\ruta\script.bat" -Wait
```

**Regla BAGO:** Intentar `Start-Process` primero. Si falla por pwsh ausente → generar .bat auto-elevante como fallback para el usuario.

---

## LIMITACIÓN CRÍTICA — RAÍZ DEL PROBLEMA

| Situación | Agente puede ejecutar |
|-----------|----------------------|
| `pwsh.exe` instalado | ✅ Todo: bat, exe, python, scripts |
| `pwsh.exe` NO instalado | ❌ Sin runtime — herramienta powershell inoperativa |

**La herramienta `powershell` del agente requiere `pwsh.exe` (PowerShell 7+) como runtime.**

### Fix permanente (UNA VEZ, como Admin):
```cmd
winget install Microsoft.PowerShell
```
Después → reiniciar terminal → BAGO puede "hacer doble click" autónomamente.

### Flujo ideal con pwsh instalado:
1. Crear `.bat` con auto-elevación UAC
2. `Start-Process -FilePath 'file.bat' -Verb RunAs -Wait` ← el agente ejecuta solo
3. Usuario no necesita intervenir

### Estado actual de esta máquina (2026-05-08 actualizado):
- ✅ `pwsh.exe` YA INSTALADO — agente puede ejecutar autónomamente
- ✅ Driver NI Komplete Kontrol MK2 v5.0.0.57 instalado y verificado
- ✅ Ableton 11 error de inicio resuelto (ver sección abajo)
