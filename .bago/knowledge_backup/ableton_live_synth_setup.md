# BAGO — Montar Canal Synth en Sesión Ableton Activa (KK S49)

> Fecha: 2026-05-08  
> Aprendido durante: sesión live con VERNY + Komplete Kontrol S49 MK2  
> Contexto: Ableton 11 Suite, set BAGO_TECHNO_LIVE_001 activo

---

## Lo que BAGO puede hacer autónomamente

### ✅ Crear MIDI track con SendKeys

```powershell
Add-Type @"
using System; using System.Runtime.InteropServices;
public class AblWin {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lp);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, System.Text.StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    public delegate bool EnumWindowsProc(IntPtr h, IntPtr lp);
}
"@
Add-Type -AssemblyName System.Windows.Forms

# 1. Encontrar ventana de Ableton
$ablPids = (Get-Process -Name "Ableton*").Id
$handle  = [IntPtr]::Zero
[AblWin]::EnumWindows({
    param($h, $lp)
    if (![AblWin]::IsWindowVisible($h)) { return $true }
    $sb = New-Object System.Text.StringBuilder(256)
    [AblWin]::GetWindowText($h, $sb, 256) | Out-Null
    [uint]$wpid = 0
    [AblWin]::GetWindowThreadProcessId($h, [ref]$wpid) | Out-Null
    if ($ablPids -contains $wpid -and $sb.Length -gt 0) { $script:handle = $h }
    return $true
}, [IntPtr]::Zero)

# 2. Enfocar Ableton
[AblWin]::ShowWindow($handle, 9) | Out-Null      # SW_RESTORE
[AblWin]::SetForegroundWindow($handle) | Out-Null
Start-Sleep -Milliseconds 600

# 3. Nueva MIDI track
[System.Windows.Forms.SendKeys]::SendWait("^+t")  # Ctrl+Shift+T
Start-Sleep -Milliseconds 500

# 4. Renombrar (F2)
[System.Windows.Forms.SendKeys]::SendWait("{F2}")
Start-Sleep -Milliseconds 300
[System.Windows.Forms.SendKeys]::SendWait("^a")
[System.Windows.Forms.SendKeys]::SendWait("SYNTH KK S49")
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
Start-Sleep -Milliseconds 300

# 5. Abrir browser + buscar instrumento
[System.Windows.Forms.SendKeys]::SendWait("^%b")   # Ctrl+Alt+B = browser
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait("^f")    # Ctrl+F = buscar en browser
Start-Sleep -Milliseconds 400
[System.Windows.Forms.SendKeys]::SendWait("Komplete Kontrol")
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")  # Cargar primer resultado
Start-Sleep -Milliseconds 800
```

---

## ⚠️ Límite de BAGO: configuración MIDI I/O

BAGO **no puede** configurar via SendKeys:
- `MIDI From` input device de la track
- Canal MIDI
- Monitor (In / Auto / Off)

Estas opciones están en los **dropdowns de la track** y requieren clicks de ratón con coordenadas exactas (varían según resolución/zoom de Ableton).

---

## ✅ Lo que VERNY hace manualmente (1 minuto)

Una vez BAGO crea la track `SYNTH KK S49` con Komplete Kontrol cargado:

### En Ableton — Track SYNTH KK S49:

| Setting | Valor |
|---|---|
| **MIDI From** | `Komplete Kontrol DAW - 4` |
| **Canal** | `All Channels` |
| **Monitor** | `Auto` |
| **MIDI To** | `No Output` |

### En el plugin Komplete Kontrol (ventana del VST):
- Navega con el S49: gira el encoder grande para explorar sounds
- La pantalla del S49 muestra nombre del preset y parámetros
- Elige un preset de synth: **recomendados para techno:**
  - `Massive X` → presets Dark / Industrial
  - `FM8` → presets Techno Lead
  - `Monark` → presets Bass / Mono Lead
  - `Razor` → presets Rave / Industrial

---

## Dispositivos MIDI del S49 en Windows

| Dispositivo | Uso |
|---|---|
| `KOMPLETE KONTROL S49 IAD` | Audio (ASIO) |
| `Komplete Kontrol DAW - 4` | ✅ MIDI para Ableton (usar este) |
| `Komplete Kontrol - 4` | MIDI genérico |
| `Komplete Kontrol MIDI` | MIDI alternativo |

---

## Cómo encontrar la ventana de Ableton (aprendido)

- Ableton corre en **2 procesos** (`Ableton Live.exe` x2)
- `Get-Process -Name "Ableton*"` devuelve ambos PIDs
- El proceso con la ventana visible es el segundo (mayor PID)
- `MainWindowHandle` está vacío — hay que usar `EnumWindows`
- La ventana se llama: `"Sin título* - Ableton Live 11 Suite"` cuando hay cambios sin guardar

---

## Notas para próximas sesiones

- **Primera acción:** Guardar el set (Ctrl+S) antes de hacer cambios de UI automation
- Considerar usar **AbletonOSC** (control surface Python) para automatización más fiable
- El handle `394922` era válido en esta sesión — no hardcodear, siempre EnumWindows
