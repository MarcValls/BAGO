#Requires -Version 5.1
<#
.SYNOPSIS
    Abre la UI de BAGO en modo desarrollo con consola visible y DevTools.

.DESCRIPTION
    Lanza el gestor BAGO (Electron) desde el repositorio actual,
    abriendo Chromium DevTools para inspeccionar logs del renderer,
    network, elementos DOM y excepciones.

.PARAMETER DevTools
    Abre Chromium DevTools automáticamente al cargar la UI.

.PARAMETER DisableGpu
    Desactiva aceleracion de GPU (util en maquinas virtuales o RDP).

.EXAMPLE
    .\scripts\Open-BagoUI.ps1 -DevTools
#>
param(
    [switch]$DevTools,
    [switch]$DisableGpu
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path "$root\ui-react\dist\index.html")) {
    Write-Host "ui-react/dist no existe. Compilando..." -ForegroundColor Yellow
    npm --prefix "$root\ui-react" run build
}

$env:BAGO_OPEN_DEVTOOLS = if ($DevTools) { "1" } else { "0" }

$flags = @(".", "--enable-logging", "--v=1")
if ($DisableGpu) { $flags += @("--disable-gpu", "--disable-software-rasterizer") }

Write-Host "Lanzando BAGO UI desde: $root" -ForegroundColor Cyan
Write-Host "BAGO_OPEN_DEVTOOLS = $env:BAGO_OPEN_DEVTOOLS" -ForegroundColor Cyan
Write-Host "Flags: $flags" -ForegroundColor DarkGray

# Start-Process -NoNewWindow keeps the console attached so logs are visible.
Start-Process -FilePath "npx" -ArgumentList (@("electron") + $flags) -NoNewWindow -Wait
