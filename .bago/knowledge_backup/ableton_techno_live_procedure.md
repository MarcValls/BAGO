# BAGO — Techno Live Set: Template & Procedimiento

> Fecha: 2026-05-08  
> Set creado: `BAGO_TECHNO_LIVE_001`  
> Base: VCH-8_ENERO_2023 (proyecto de VERNY, enero 2023)  
> Modo: BAGO Temporal Autónomo

---

## Set Creado

**Archivo:** `C:\Users\verny\Documents\BAGO_TECHNO_LIVE_001 Project\BAGO_TECHNO_LIVE_001.als`  
**Tempo:** 138 BPM  
**Ableton:** Live 11 Suite

### Estructura de Tracks (heredada del VCH-8)

| Track | Tipo | Rol |
|---|---|---|
| 1-Audio | Audio | Fuente audio directa |
| 2-Group | Group | Grupo principal |
| Kick01 SC | Audio | Kick con sidechain |
| kick01 G | Group | Grupo kick |
| Kick01 | Audio | Kick principal |
| Kick01 contra | Audio | Kick contra/layering |
| Pad(Cama) | Audio | Pad atmosférico |
| Bass | Audio | Línea de bajo |
| 12-gritoos | Audio | Textura/efecto |
| Clap 909 | Audio | Clap |
| DelayRide / Ride 909 | Audio | Ride cymbal + delay send |
| A-Reverb | Return | Send reverb |
| B-Delay | Return | Send delay |
| Master | Master | Salida principal |

---

## Cómo Crear un Techno Live Set desde Cero (BAGO procedure)

### Paso 1: Tomar un set existente como base

El ALS de Ableton es gzip + XML. Usar un set propio existente como plantilla garantiza que sea un archivo válido. **No crear desde cero.**

```powershell
Add-Type -AssemblyName System.IO.Compression

$src  = "ruta\al\set_base.als"
$dest = "$env:USERPROFILE\Documents\NUEVO_SET Project\NUEVO_SET.als"

# Decodificar
$fs = [System.IO.File]::OpenRead($src)
$gz = New-Object System.IO.Compression.GZipStream($fs, [System.IO.Compression.CompressionMode]::Decompress)
$sr = New-Object System.IO.StreamReader($gz, [System.Text.Encoding]::UTF8)
$xml = $sr.ReadToEnd()
$sr.Close(); $gz.Close(); $fs.Close()

# Modificar
$xml = $xml -replace '<Manual Value="132" />', '<Manual Value="138" />'

# Re-codificar
$out = [System.IO.File]::OpenWrite($dest)
$gzOut = New-Object System.IO.Compression.GZipStream($out, [System.IO.Compression.CompressionLevel]::Optimal)
$sw = New-Object System.IO.StreamWriter($gzOut, [System.Text.Encoding]::UTF8)
$sw.Write($xml); $sw.Close(); $gzOut.Close(); $out.Close()
```

### Paso 2: Crear estructura de carpetas

```powershell
$base = "$env:USERPROFILE\Documents\NUEVO_SET Project"
New-Item -ItemType Directory "$base\Samples\Recorded" -Force | Out-Null
New-Item -ItemType Directory "$base\Backup" -Force | Out-Null
```

### Paso 3: Lanzar Ableton

```powershell
$ableton = "C:\ProgramData\Ableton11\Live 11 Suite\Program\Ableton Live 11 Suite.exe"
Start-Process $ableton -ArgumentList "`"$dest`""
```

---

## Set Base de Referencia

El mejor set base disponible para VERNY es el **VCH-8_ENERO_2023**:  
`C:\Users\verny\Downloads\wetransfer_carpeta-sin-titulo_2023-01-08_2002\carpeta sin título\VCH-8_ENERO_2023 Project\VCH-8_ENERO_2023.als`

- 26 tracks con estructura techno completa
- Tiene returns de reverb y delay configurados
- Tracks de kick con sidechain ya patched
- Ableton 11.0.11 compatible

---

## Tempos Techno de Referencia

| Estilo | BPM |
|---|---|
| Techno industrial / duro | 140-150 |
| Techno driving / estándar | 135-140 |
| Techno groove / house-techno | 128-134 |
| **BAGO_TECHNO_LIVE_001** | **138** |

---

## Notas

- El set VCH-8 parece ser una actuación en vivo de VERNY (enero 2023, Spain)
- El campo `Creator` del ALS fue marcado como `BAGO TECHNO LIVE TEMPLATE` para identificarlo
- Si se quieren patrones MIDI, crearlos dentro de Ableton — no es viable desde fuera con PowerShell
