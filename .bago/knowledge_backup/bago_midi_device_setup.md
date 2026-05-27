# BAGO como dispositivo MIDI — Aprendizaje

## Estado actual (2026-05-08) ✅ RESUELTO

### Instalado y funcionando
- loopMIDI v1.0.16.27 en `C:\Program Files (x86)\Tobias Erichsen\loopMIDI\`
- teVirtualMIDI64.dll en `C:\Windows\System32\` ✓
- teVirtualMIDI64.sys en `C:\Windows\System32\drivers\` ✓
- **Servicio `teVirtualMIDI` registrado y Running** ✓
- Puerto "BAGO" creado en loopMIDI ✓

### Cómo se instaló el driver (necesitó admin una sola vez)
```powershell
# Admin via UAC — registrar e iniciar el servicio kernel:
sc.exe create teVirtualMIDI type= kernel start= auto binPath= "C:\Windows\System32\drivers\teVirtualMIDI64.sys" DisplayName= "teVirtualMIDI"
sc.exe start teVirtualMIDI
# Verificar: Get-Service teVirtualMIDI → Status: Running
```

### Error que bloqueaba antes
`virtualMIDICreatePortEx2` devolvía handle=0 con error 1379 porque el servicio kernel no estaba registrado.
La instalación silenciosa de loopMIDI (`/S`) no instaló el driver automáticamente → había que registrarlo a mano con `sc.exe create`.

### Uso sin admin (driver ya instalado):
BAGO puede ahora crear puertos MIDI en cualquier sesión:
```powershell
Add-Type @"
using System; using System.Runtime.InteropServices;
public class BAGOMIDI {
    public const uint TX_ONLY = 8;
    [DllImport("C:\\Windows\\System32\\teVirtualMIDI64.dll", CharSet=CharSet.Unicode)]
    public static extern IntPtr virtualMIDICreatePortEx2(string name, IntPtr cb, IntPtr inst, uint sysex, uint flags);
    [DllImport("C:\\Windows\\System32\\teVirtualMIDI64.dll")]
    public static extern bool virtualMIDISendData(IntPtr port, byte[] data, uint len);
    [DllImport("C:\\Windows\\System32\\teVirtualMIDI64.dll")]
    public static extern void virtualMIDIClosePort(IntPtr port);
}
"@
$port = [BAGOMIDI]::virtualMIDICreatePortEx2("BAGO", [IntPtr]::Zero, [IntPtr]::Zero, 256, [BAGOMIDI]::TX_ONLY)
# Enviar nota MIDI: [status, note, velocity]
[BAGOMIDI]::virtualMIDISendData($port, [byte[]](0x90, 60, 100), 3)
```

### Arquitectura cuando funcione
```
BAGO (PowerShell)
  → virtualMIDISendData(port, noteBytes)
  → teVirtualMIDI driver (kernel)
  → Puerto MIDI IN "BAGO" (visible en Ableton)
  → Track de percusión en Ableton (MIDI From: BAGO)
```

### Otros hallazgos
- puertos KK (Komplete Kontrol - 4, EXT, DAW) no se pueden abrir con midiOutOpen desde procesos externos — bloqueados por el software KK
- Microsoft GS Wavetable Synth devuelve error 1 (MMSYSERR_ERROR) — no disponible
- loopMIDI 32-bit puede crear puertos que sean visibles a apps 64-bit si el driver kernel está correctamente instalado

### Para tocar percusión mientras el driver no está disponible
Opción A: Editar .als y añadir clips MIDI de percusión → lanzar con PostMessage
Opción B: Usar Ableton's built-in drum machine (Impulse) con clips pre-grabados
