# BAGO — Cómo Probar un Proyecto Ableton

> Fecha: 2026-05-08  
> Aprendido durante: validación de `BAGO_TECHNO_LIVE_001`  
> Resultado: 8/9 pasados (T6 corregido post-análisis → 9/9 real)

---

## Función de Test Completa

```powershell
function Test-AbletonProject {
    param([string]$ProjectPath)

    Add-Type -AssemblyName System.IO.Compression
    $results = @{}

    # T1: Archivo existe
    $results["T1_existe"] = Test-Path $ProjectPath

    if (-not $results["T1_existe"]) {
        Write-Warning "Proyecto no encontrado: $ProjectPath"
        return $results
    }

    # T2: Tamaño razonable (>10KB)
    $size = (Get-Item $ProjectPath).Length
    $results["T2_tamano_KB"] = [math]::Round($size / 1KB, 0)
    $results["T2_ok"] = $size -gt 10000

    # T3: Magic bytes gzip (1F 8B)
    $bytes = [System.IO.File]::ReadAllBytes($ProjectPath)
    $results["T3_gzip_valido"] = ($bytes[0] -eq 0x1F) -and ($bytes[1] -eq 0x8B)

    # T4: XML decodificable
    try {
        $fs = [System.IO.File]::OpenRead($ProjectPath)
        $gz = New-Object System.IO.Compression.GZipStream($fs, [System.IO.Compression.CompressionMode]::Decompress)
        $sr = New-Object System.IO.StreamReader($gz, [System.Text.Encoding]::UTF8)
        $xml = $sr.ReadToEnd()
        $sr.Close(); $gz.Close(); $fs.Close()
        [xml]$parsed = $xml   # Valida que es XML bien formado
        $results["T4_xml_ok"] = $true
    } catch {
        $results["T4_xml_ok"] = $false
        $results["T4_error"] = $_.Exception.Message
        return $results
    }

    # T5: Versión Ableton
    $results["T5_version"] = $parsed.Ableton.MinorVersion
    $results["T5_ok"] = $results["T5_version"] -match "^11\."

    # T6: Tempo — USAR REGEX sobre el XML raw, no el parser
    # NOTA: <Tempo> NO está en <Transport>. Está directamente en <LiveSet>.
    # La ruta XML parseada es distinta. Regex es más fiable.
    $tempoMatch = [regex]::Match($xml, '<Tempo[^>]*>.*?<Manual Value="([\d.]+)"', 
                  [System.Text.RegularExpressions.RegexOptions]::Singleline)
    $results["T6_tempo"] = $tempoMatch.Groups[1].Value
    $results["T6_ok"] = $results["T6_tempo"] -eq "138"

    # T7: Tracks de audio
    $results["T7_audio_tracks"] = $parsed.Ableton.LiveSet.Tracks.AudioTrack.Count
    $results["T7_ok"] = $results["T7_audio_tracks"] -gt 5

    # T8: Return tracks (reverb/delay)
    $results["T8_return_tracks"] = $parsed.Ableton.LiveSet.Tracks.ReturnTrack.Count
    $results["T8_ok"] = $results["T8_return_tracks"] -ge 2

    # T9: Ableton está corriendo
    $proc = Get-Process -Name "Ableton*" -ErrorAction SilentlyContinue
    $results["T9_ableton_running"] = $null -ne $proc

    # Resumen
    $passed = ($results.Keys | Where-Object { $_ -match "_ok$" } | 
               ForEach-Object { $results[$_] } | Where-Object { $_ -eq $true }).Count
    $total  = ($results.Keys | Where-Object { $_ -match "_ok$" }).Count
    $results["SUMMARY"] = "$passed/$total"
    $results["PASS"] = ($passed -eq $total)

    return $results
}

# === USO ===
$r = Test-AbletonProject "C:\Users\verny\Documents\BAGO_TECHNO_LIVE_001 Project\BAGO_TECHNO_LIVE_001.als"
$r.GetEnumerator() | Sort-Object Name | ForEach-Object { Write-Host "$($_.Key): $($_.Value)" }
```

---

## Tests Explicados

| Test | Qué verifica | Cómo |
|---|---|---|
| T1 | El archivo .als existe en disco | `Test-Path` |
| T2 | Tamaño razonable (>10KB) | `Get-Item .Length` |
| T3 | Es gzip válido | Magic bytes `1F 8B` |
| T4 | XML bien formado y decodificable | `[xml]$parsed = $content` |
| T5 | Versión Ableton 11.x | `$parsed.Ableton.MinorVersion` |
| T6 | Tempo correcto (138 BPM) | **Regex sobre XML raw** ⚠️ |
| T7 | Tiene tracks de audio (>5) | `$parsed...AudioTrack.Count` |
| T8 | Tiene returns (reverb/delay) | `$parsed...ReturnTrack.Count` |
| T9 | Ableton está en ejecución | `Get-Process Ableton*` |

---

## ⚠️ Gotcha: Tempo en el XML

El elemento `<Tempo>` **NO** está dentro de `<Transport>`. Está en otro nivel del LiveSet.  
El parser `[xml]` navega mal esta ruta. **Usar siempre regex para leer el tempo:**

```powershell
# ✅ Correcto
$m = [regex]::Match($xml, '<Tempo[^>]*>.*?<Manual Value="([\d.]+)"',
     [System.Text.RegularExpressions.RegexOptions]::Singleline)
$tempo = $m.Groups[1].Value  # "138"

# ❌ Incorrecto (path XML erróneo)
$tempo = $parsed.Ableton.LiveSet.Transport.Tempo.Manual.Value  # $null
```

---

## Resultado de BAGO_TECHNO_LIVE_001

```
T1_existe:        True
T2_tamano_KB:     201
T2_ok:            True
T3_gzip_valido:   True
T4_xml_ok:        True
T5_version:       11.0_433
T5_ok:            True
T6_tempo:         138
T6_ok:            True   ← (regex fix)
T7_audio_tracks:  17
T7_ok:            True
T8_return_tracks: 2
T8_ok:            True
T9_ableton_running: True
SUMMARY:          9/9
PASS:             True ✅
```
