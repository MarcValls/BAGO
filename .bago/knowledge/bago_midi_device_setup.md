# BAGO como dispositivo MIDI — Aprendizaje

## Estado actual (2026-05-08)

### Instalado
- loopMIDI v1.0.16.27 en `C:\Program Files (x86)\Tobias Erichsen\loopMIDI\`
- teVirtualMIDI64.dll en `C:\Windows\System32\` ✓
- Puerto "BAGO" creado en loopMIDI UI ✓

### Problema bloqueante
**El servicio kernel `teVirtualMIDI` NO está instalado como servicio de Windows.**
Sin el servicio del kernel driver registrado, `virtualMIDICreatePortEx2` falla con error 1379.

Causa: instalación de loopMIDI requiere **admin** para registrar el driver de kernel.
El proceso actual corre sin admin → el driver no se instaló correctamente.

### Solución pendiente (necesita admin una sola vez)
```powershell
# Ejecutar como administrador:
pnputil /add-driver "C:\Program Files\Tobias Erichsen\teVirtualMIDI\teVirtualMIDI64.inf" /install

# O reinstalar loopMIDI con RunAs:
Start-Process "C:\Users\verny\AppData\Local\Temp\loopMIDI_setup\loopMIDISetup.exe" -Verb RunAs -Wait
```

Después de instalar el driver correctamente, BAGO puede crear puertos MIDI sin admin:
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
