# BAGO: Automatización de Windows SIN interferir al usuario

## Principio fundamental
- `keybd_event` + `SetForegroundWindow` = **ROBA EL FOCO** ❌ (interfiere al usuario)
- `PostMessage` directo al handle = **NO ROBA FOCO** ✓ (usuario sigue trabajando)

---

## 1. PostMessage — Teclas a ventana en segundo plano

```powershell
Add-Type @"
using System; using System.Runtime.InteropServices; using System.Threading;
public class BAGOKeys {
    public const uint WM_KEYDOWN = 0x0100;
    public const uint WM_KEYUP   = 0x0101;
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);

    // Tecla simple (Space, F1, Escape...)
    public static void PostKey(IntPtr hwnd, int vk){
        PostMessage(hwnd, WM_KEYDOWN, new IntPtr(vk), new IntPtr(0x00000001));
        Thread.Sleep(60);
        PostMessage(hwnd, WM_KEYUP,   new IntPtr(vk), new IntPtr(unchecked((int)0xC0000001)));
    }

    // Ctrl+tecla (Ctrl+S, Ctrl+Z...)
    public static void PostCtrlKey(IntPtr hwnd, int vk){
        PostMessage(hwnd, WM_KEYDOWN, new IntPtr(0x11), new IntPtr(0x00000001)); // Ctrl down
        Thread.Sleep(30);
        PostMessage(hwnd, WM_KEYDOWN, new IntPtr(vk),   new IntPtr(0x00000001));
        Thread.Sleep(60);
        PostMessage(hwnd, WM_KEYUP,   new IntPtr(vk),   new IntPtr(unchecked((int)0xC0000001)));
        Thread.Sleep(30);
        PostMessage(hwnd, WM_KEYUP,   new IntPtr(0x11), new IntPtr(unchecked((int)0xC0000001))); // Ctrl up
    }
}
"@

# Ejemplos Ableton (usar handle real encontrado con EnumWindows)
$hwnd = [IntPtr]853146  # handle real varía cada sesión — buscar con EnumWindows
[BAGOKeys]::PostKey($hwnd, 0x20)       # Space = Play/Stop
[BAGOKeys]::PostCtrlKey($hwnd, 0x53)   # Ctrl+S = Guardar
[BAGOKeys]::PostKey($hwnd, 0x09)       # Tab = cambiar vista Session/Arrangement
```

**VirtualKey codes útiles:**
| Tecla | VK Hex |
|-------|--------|
| Space | 0x20 |
| Tab | 0x09 |
| Enter | 0x0D |
| Escape | 0x1B |
| F1-F12 | 0x70-0x7B |
| Ctrl | 0x11 |
| Shift | 0x10 |
| Alt | 0x12 |
| A-Z | 0x41-0x5A |
| 0-9 | 0x30-0x39 |

---

## 2. BM_CLICK — Click en botones de diálogo SIN foco

```powershell
Add-Type @"
using System; using System.Runtime.InteropServices;
public class BAGOBtn {
    public const uint BM_CLICK = 0x00F5;
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
}
"@

# Ejemplo: click en botón "Aceptar" en diálogo de Ableton
$btnHandle = [IntPtr]1377968  # handle del botón (de EnumChildWindows)
[BAGOBtn]::PostMessage($btnHandle, [BAGOBtn]::BM_CLICK, [IntPtr]::Zero, [IntPtr]::Zero)
```

---

## 3. Encontrar handles de ventana y botones

```powershell
Add-Type @"
using System; using System.Runtime.InteropServices; using System.Text;
public class BAGOFind {
    [DllImport("user32.dll")] public static extern bool EnumWindows(EWP cb, IntPtr lp);
    [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr h, EWP cb, IntPtr lp);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    public delegate bool EWP(IntPtr h, IntPtr lp);
}
"@

# Encontrar ventana principal de un proceso
function Find-WindowByProcess($processName, $titleContains=""){
    $pids = (Get-Process -Name $processName -EA SilentlyContinue).Id
    $script:result = [IntPtr]::Zero
    [BAGOFind]::EnumWindows({
        param($h,$lp)
        if(![BAGOFind]::IsWindowVisible($h)){return $true}
        $sb=New-Object System.Text.StringBuilder(256)
        [BAGOFind]::GetWindowText($h,$sb,256)|Out-Null
        [uint]$wpid=0
        [BAGOFind]::GetWindowThreadProcessId($h,[ref]$wpid)|Out-Null
        if(($pids -contains $wpid) -and ($sb.ToString() -match $titleContains)){
            $script:result=$h
        }
        return $true
    },[IntPtr]::Zero)
    return $script:result
}

# Encontrar botón en diálogo por texto
function Find-Button($dialogHandle, $btnText){
    $script:btn=[IntPtr]::Zero
    [BAGOFind]::EnumChildWindows($dialogHandle,{
        param($h,$lp)
        $sb=New-Object System.Text.StringBuilder(256)
        [BAGOFind]::GetWindowText($h,$sb,256)|Out-Null
        if($sb.ToString() -eq $btnText){$script:btn=$h}
        return $true
    },[IntPtr]::Zero)
    return $script:btn
}

# Uso:
$ablH    = Find-WindowByProcess "Ableton*" "BAGO_CONCERT"
$dlgH    = Find-WindowByProcess "Ableton*" "^Live$"
$aceptar = Find-Button $dlgH "Aceptar"
```

---

## 4. Patrón BAGO para Ableton sin interferir

```powershell
function Send-AbletonKey($vk){
    $hwnd = Find-WindowByProcess "Ableton*" "BAGO_CONCERT"
    if($hwnd -ne [IntPtr]::Zero){
        [BAGOKeys]::PostKey($hwnd, $vk)
    }
}

# Usar solo PostMessage, NUNCA keybd_event+SetForegroundWindow para Ableton
Send-AbletonKey 0x20   # Play/Stop sin interferir
```

---

## 5. Diálogo VST de Ableton al arrancar

Cuando Ableton arranca tras un crash durante escaneo VST, muestra:
> "La última sesión de Live se cerró inesperadamente al escanear el plug-in VST2..."

**SIEMPRE pulsar Aceptar** (no Cancelar — Cancelar desactiva el plugin y Ableton no abre bien).

```powershell
# Buscar y aceptar diálogo VST automáticamente
function Dismiss-AbletonVSTDialog {
    $dlgH = Find-WindowByProcess "Ableton*" "^Live$"
    if($dlgH -ne [IntPtr]::Zero){
        $btn = Find-Button $dlgH "Aceptar"
        if($btn -ne [IntPtr]::Zero){
            [BAGOBtn]::PostMessage($btn, [BAGOBtn]::BM_CLICK, [IntPtr]::Zero, [IntPtr]::Zero)
        }
    }
}

# Esperar carga Ableton con auto-dismiss de diálogos VST
function Wait-AbletonLoaded($timeoutSec=120){
    for($i=0;$i -lt $timeoutSec/2;$i++){
        Start-Sleep -Milliseconds 2000
        Dismiss-AbletonVSTDialog  # auto-click Aceptar si aparece
        $h = Find-WindowByProcess "Ableton*" "BAGO_CONCERT|Ableton Live"
        if($h -ne [IntPtr]::Zero){return $h}
    }
    return [IntPtr]::Zero
}
```

---

## 6. Reglas de no-interferencia BAGO

1. **Nunca** usar `SetForegroundWindow` para automatizar (solo para screenshots)
2. **Nunca** usar `keybd_event` sin `SetForegroundWindow` previo (irá al foco actual = CLI)
3. **Siempre** usar `PostMessage` directo al handle de la ventana/botón target
4. Para screenshots: usar `SetForegroundWindow` solo justo antes de capturar, restaurar inmediatamente
5. Para configuración mayor → editar .als XML (cerrar Ableton primero, reabrir después)

---

## 7. MIDI en tiempo real sin interferir

Para controlar Ableton en tiempo real (clips, efectos) durante un concierto:
- Usar la API de MIDI Remote Scripts de Ableton (Python en carpeta MIDI Remote Scripts)
- O loopMIDI + enviar MIDI CC desde PowerShell via Win32 midiOut API
- Esto permite control total sin tocar el teclado/ratón

```powershell
# Enviar MIDI CC via Win32 (requiere abrir el puerto MIDI virtual)
# midiOutOpen → midiOutShortMsg(handle, 0xB0 | canal | (cc<<8) | (valor<<16))
# Este método no interfiere NADA con el PC
```
