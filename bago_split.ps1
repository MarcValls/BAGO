#requires -Version 5.1
<#
.SYNOPSIS
    Abre BAGO Chat y un terminal vacio lado a lado.
.DESCRIPTION
    Intenta usar Windows Terminal (wt.exe) para paneles divididos.
    Si no esta disponible, abre dos ventanas de PowerShell separadas
    con instrucciones para dividirlas manualmente (Win+Izquierda/Derecha).
#>

param(
    [string]$BagoRoot = "C:\bago_true",
    [string]$ChatScript = ".bago\tools\bago_chat.py"
)

$ErrorActionPreference = "Stop"

# ── 1. Detectar wt.exe (Windows Terminal) ─────────────────────────────────────
function Find-WindowsTerminal {
    $candidates = @(
        "wt.exe",
        "$env:LOCALAPPDATA\Microsoft\WindowsApps\wt.exe",
        "$env:LOCALAPPDATA\Microsoft\WindowsApps\Microsoft.WindowsTerminal_8wekyb3d8bbwe\wt.exe",
        "C:\Program Files\WindowsApps\Microsoft.WindowsTerminal_*\wt.exe"
    )
    foreach ($c in $candidates) {
        $resolved = Get-Command $c -ErrorAction SilentlyContinue
        if ($resolved) { return $resolved.Source }
        if (Test-Path $c) { return $c }
    }
    # Fallback: buscar en WindowsApps recursivamente
    $found = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WindowsApps" -Filter "wt.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
    if ($found) { return $found }
    return $null
}

$wt = Find-WindowsTerminal

# ── 2. Lanzar con Windows Terminal (paneles divididos) ───────────────────────
if ($wt) {
    Write-Host "[BAGO-Split] Windows Terminal detectado: $wt" -ForegroundColor Cyan

    # Comandos para cada panel
    $leftCmd = "powershell.exe -NoExit -Command `"cd `"$BagoRoot`"; python `"$ChatScript`"`""
    $rightCmd = "powershell.exe -NoExit -Command `"cd `"$BagoRoot`"`""

    $wtArgs = @(
        "-w", "0",
        "split-pane", "-V", "-d", $BagoRoot, $leftCmd,
        ";",
        "split-pane", "-H", "-d", $BagoRoot, $rightCmd
    )

    Start-Process -FilePath $wt -ArgumentList $wtArgs -WindowStyle Hidden
    Start-Sleep -Seconds 1
    Write-Host "[BAGO-Split] Ventana dividida lanzada." -ForegroundColor Green
    Write-Host "  - Panel izquierdo : BAGO Chat" -ForegroundColor Green
    Write-Host "  - Panel derecho   : Terminal vacio en $BagoRoot" -ForegroundColor Green
    exit 0
}

# ── 3. Fallback: dos ventanas de PowerShell separadas ─────────────────────────
Write-Host "[BAGO-Split] Windows Terminal no detectado." -ForegroundColor Yellow
Write-Host "Abriendo dos ventanas de PowerShell separadas..." -ForegroundColor Yellow

# Ventana 1: BAGO Chat
$proc1 = Start-Process -FilePath "powershell.exe" `
    -ArgumentList "-NoExit","-Command","cd `"$BagoRoot`"; python `"$ChatScript`"" `
    -PassThru

# Ventana 2: Terminal vacio
$proc2 = Start-Process -FilePath "powershell.exe" `
    -ArgumentList "-NoExit","-Command","cd `"$BagoRoot`"" `
    -PassThru

Start-Sleep -Seconds 1

Write-Host "`n[BAGO-Split] Dos ventanas abiertas." -ForegroundColor Green
Write-Host "Para verlas lado a lado:" -ForegroundColor Cyan
Write-Host "  1. Selecciona la ventana 'BAGO Chat'" -ForegroundColor White
Write-Host "  2. Presiona  Win + Flecha Izquierda  (snap izquierdo)" -ForegroundColor White
Write-Host "  3. Selecciona la otra ventana" -ForegroundColor White
Write-Host "  4. Presiona  Win + Flecha Derecha  (snap derecho)" -ForegroundColor White
Write-Host "`nO usa Alt+Tab para alternar entre ellas.`n" -ForegroundColor DarkGray

