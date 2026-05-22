# Windows Audio Setup — BAGO Knowledge

> **Aprendido:** 2026-05-08  
> **Contexto:** Sesión de setup studio — driver NI KK S49 MK2 + Ableton 11 Suite  
> **Máquina:** verny — Windows 11, pwsh instalado

---

## CASO 1: Instalar driver Native Instruments Komplete Kontrol MK2

### Identificación del dispositivo
```
USB\VID_17CC&PID_1350&MI_00  →  Komplete Kontrol S49 MK2
```

### Driver correcto
- **Nombre:** Native Instruments Komplete Kontrol MK2 Driver
- **Versión:** 5.0.0.57
- **Installer disponible en:** `C:\Users\verny\Downloads\Komplete_Kontrol_Driver_Setup_Win.exe`

### Procedimiento autónomo (agente)
```powershell
# 1. Lanzar installer como Admin
Start-Process -FilePath "$env:USERPROFILE\Downloads\Komplete_Kontrol_Driver_Setup_Win.exe" -Verb RunAs

# 2. Esperar que el proceso termine
Wait-Process -Id <PID> -Timeout 300

# 3. Forzar re-escaneo de hardware
pnputil /scan-devices

# 4. Verificar resultado
Get-PnpDevice | Where-Object { $_.FriendlyName -match "Komplete" } | Select FriendlyName, Status
```

### Verificación OK
```
KOMPLETE KONTROL S49 DFU   → OK
KOMPLETE KONTROL S49 IAD   → OK
Komplete Kontrol - 4       → OK (SoftwareDevice)
Komplete Kontrol MIDI      → OK
```

### Registro Windows (post-instalación)
```
HKLM:\SOFTWARE\...\Uninstall\  →  "Native Instruments Komplete Kontrol MK2 Driver"  v5.0.0.57
```

---

## CASO 2: Error de inicio Ableton 11 — "Acceso denegado" en VST scan

### Síntoma en log
```
C:\Users\verny\AppData\Roaming\Ableton\Live 11.0.11\Preferences\Log.txt:
VstScan: Scan of folder "C:\Program Files\Archivos comunes" failed (Acceso denegado)
```

### Causa raíz
La carpeta `C:\Program Files\Archivos comunes` tenía una ACE **DENY (RD)** explícita para "Todos":
```
C:\Program Files\Archivos comunes  Todos:(DENY)(RD)   ← BLOQUEA listing
                                   Todos:(RX)
                                   NT AUTHORITY\SYSTEM:(F)
                                   BUILTIN\Administradores:(F)
```
El DENY tiene prioridad sobre ALLOW → Ableton no puede listar la carpeta → falla el escaneo de plugins.

### Fix autónomo
```powershell
# Eliminar el DENY (requiere elevación Admin)
Start-Process -FilePath "icacls.exe" `
  -ArgumentList '"C:\Program Files\Archivos comunes" /remove:d "Todos"' `
  -Verb RunAs -Wait

# Verificar resultado esperado:
# C:\Program Files\Archivos comunes  Todos:(RX)
#                                    NT AUTHORITY\SYSTEM:(F)
#                                    BUILTIN\Administradores:(F)
```

### Contenido de la carpeta (VSTs instalados)
```
C:\Program Files\Archivos comunes\
  ├── Native Instruments\    ← NI plugins
  ├── VST2\
  ├── VST3\
  ├── Avid\
  └── Propellerhead Software\
```

### Verificación OK
Tras el fix y reinicio de Ableton:
- **Sin warnings** en el log relacionados con VstScan
- `PluginManager: Scan start` completa limpio
- Ableton abre correctamente (Main window: "Sin título - Ableton Live 11 Suite")

---

## PATRÓN: Diagnóstico rápido de arranque Ableton

```powershell
# Log principal de Ableton 11:
$log = "$env:APPDATA\Ableton\Live 11.0.11\Preferences\Log.txt"
Get-Content $log | Select-String "error|warn|failed|Acceso" | Select -Last 20
```

### Rutas clave Ableton 11 Suite en verny
| Recurso | Ruta |
|---------|------|
| Ejecutable | `C:\ProgramData\Ableton11\Live 11 Suite\Program\Ableton Live 11 Suite.exe` |
| Log | `C:\Users\verny\AppData\Roaming\Ableton\Live 11.0.11\Preferences\Log.txt` |
| Preferences | `C:\Users\verny\AppData\Roaming\Ableton\Live 11.0.11\Preferences\` |
| Core Library | `C:\ProgramData\Ableton11\Live 11 Suite\Resources\Core Library` |

---

## REGLAS BAGO para setup studio verny

1. **Driver KK MK2:** Ya instalado (v5.0.0.57). Si da problemas → reinstalar desde `Downloads\Komplete_Kontrol_Driver_Setup_Win.exe`
2. **Ableton VST scan error:** Verificar permisos de `C:\Program Files\Archivos comunes` — eliminar DENY si existe
3. **ASIO disponibles en Ableton:** ASIO4ALL v2, Komplete Audio 6, Komplete Audio ASIO Driver, Traktor Audio series
4. **MIDI configurado:** Komplete Kontrol - 4 (In/Out), DAW port, EXT port — todos activos

---

*Generado por BAGO COPILOT-CLI · 2026-05-08*
