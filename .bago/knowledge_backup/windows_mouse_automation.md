# BAGO — Simulación de Clicks de Ratón en Windows

> Fecha: 2026-05-08  
> Aprendido durante: configuración canal synth KK S49 en Ableton  
> Problema original: SendKeys no puede activar dropdowns — necesitamos clicks reales

---

## Clase BAGOMouse (Win32 mouse_event)

```powershell
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

public class BAGOMouse {
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint f, int x, int y, int d, int e);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out BRECT r);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EWP cb, IntPtr lp);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    public delegate bool EWP(IntPtr h, IntPtr lp);

    public static void Click(int x, int y, int ms=80) {
        SetCursorPos(x, y); Thread.Sleep(50);
        mouse_event(0x0002, x, y, 0, 0); Thread.Sleep(ms);
        mouse_event(0x0004, x, y, 0, 0);
    }
    public static void RightClick(int x, int y) {
        SetCursorPos(x, y); Thread.Sleep(50);
        mouse_event(0x0008, x, y, 0, 0); Thread.Sleep(80);
        mouse_event(0x0010, x, y, 0, 0);
    }
    public static void DoubleClick(int x, int y) { Click(x,y); Thread.Sleep(100); Click(x,y); }
}
[StructLayout(LayoutKind.Sequential)]
public struct BRECT { public int Left, Top, Right, Bottom; }
"@
```

---

## Funciones de ayuda

```powershell
function Get-ProcessWindow([int[]]$Pids) {
    $script:_wh = [IntPtr]::Zero
    [BAGOMouse]::EnumWindows({
        param($h, $lp)
        if (![BAGOMouse]::IsWindowVisible($h)) { return $true }
        $sb = New-Object System.Text.StringBuilder(256)
        [BAGOMouse]::GetWindowText($h, $sb, 256) | Out-Null
        [uint]$wpid = 0
        [BAGOMouse]::GetWindowThreadProcessId($h, [ref]$wpid) | Out-Null
        if ($Pids -contains $wpid -and $sb.Length -gt 0) { $script:_wh = $h }
        return $true
    }, [IntPtr]::Zero)
    return $script:_wh
}

function Get-WindowRect([IntPtr]$handle) {
    $r = New-Object BRECT
    [BAGOMouse]::GetWindowRect($handle, [ref]$r) | Out-Null
    return $r
}

function Focus-Window([IntPtr]$handle) {
    [BAGOMouse]::ShowWindow($handle, 9) | Out-Null
    [BAGOMouse]::SetForegroundWindow($handle) | Out-Null
    Start-Sleep -Milliseconds 600
}
```

---

## Patrón completo: Focus + Click en coordenada relativa

```powershell
# Encontrar y enfocar Ableton
$ablPids = (Get-Process -Name "Ableton*").Id
$handle  = Get-ProcessWindow -Pids $ablPids
Focus-Window $handle

# Obtener posición de la ventana
$rect = Get-WindowRect $handle

# Click en coordenada RELATIVA a la ventana de Ableton
# Ejemplo: click en X=200, Y=50 dentro de la ventana
$absX = $rect.Left + 200
$absY = $rect.Top  + 50
[BAGOMouse]::Click($absX, $absY)

Start-Sleep -Milliseconds 400   # Dar tiempo al UI antes del siguiente click
```

---

## Cómo descubrir coordenadas de elementos UI

Mover el cursor encima del elemento en Ableton y leer:

```powershell
Add-Type -AssemblyName System.Windows.Forms
while ($true) {
    $p = [System.Windows.Forms.Cursor]::Position
    Write-Host -NoNewline "`rX=$($p.X)  Y=$($p.Y)   "
    Start-Sleep -Milliseconds 150
}
```

Anotar X,Y cuando el cursor esté sobre el botón/dropdown deseado. Ctrl+C para parar.

---

## Constantes mouse_event

| Flag | Valor hex | Acción |
|---|---|---|
| LEFTDOWN  | 0x0002 | Click izquierdo ↓ |
| LEFTUP    | 0x0004 | Click izquierdo ↑ |
| RIGHTDOWN | 0x0008 | Click derecho ↓ |
| RIGHTUP   | 0x0010 | Click derecho ↑ |
| WHEEL     | 0x0800 | Scroll rueda |

---

## Pantalla verny PC

- **Resolución:** 1536 × 864
- **Ableton (no maximizado):** Left=334 Top=17 W=814 H=806
- El handle cambia en cada sesión — siempre usar EnumWindows, nunca hardcodear

---

## Verificado ✅

Click en centro de Ableton (741, 420) ejecutado correctamente — 2026-05-08  
`mouse_event` funciona en Windows 11 sin permisos elevados para clicks normales.
