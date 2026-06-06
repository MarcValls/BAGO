[CmdletBinding()]
param(
    [string]$SourceRoot = "",
    [string]$InstallDir = "C:\Program Files\BAGO",
    [string]$Mode = "",
    [switch]$DryRun,
    [switch]$AssumeYes,
    [switch]$NoContextMenu
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Read-Choice {
    param(
        [Parameter(Mandatory = $true)][string]$Prompt,
        [Parameter(Mandatory = $true)][string[]]$Options,
        [int]$DefaultIndex = 0
    )
    while ($true) {
        $suffix = if ($DefaultIndex -ge 0 -and $DefaultIndex -lt $Options.Length) { " [$($Options[$DefaultIndex])]" } else { "" }
        $value = Read-Host "$Prompt$suffix"
        if ([string]::IsNullOrWhiteSpace($value) -and $DefaultIndex -ge 0 -and $DefaultIndex -lt $Options.Length) {
            return $Options[$DefaultIndex]
        }
        foreach ($opt in $Options) {
            if ($value.Trim().ToLowerInvariant() -eq $opt.ToLowerInvariant()) { return $opt }
        }
        Write-Host "Opcion invalida."
    }
}

function Read-YesNo {
    param(
        [Parameter(Mandatory = $true)][string]$Prompt,
        [bool]$Default = $true
    )
    $defaultLabel = if ($Default) { "S/n" } else { "s/N" }
    while ($true) {
        $value = Read-Host "$Prompt [$defaultLabel]"
        if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
        switch ($value.Trim().ToLowerInvariant()) {
            "s" { return $true }
            "si" { return $true }
            "y" { return $true }
            "yes" { return $true }
            "n" { return $false }
            "no" { return $false }
        }
        Write-Host "Responde si/no."
    }
}

function Read-InputOrDefault {
    param(
        [Parameter(Mandatory = $true)][string]$Prompt,
        [string]$Default = ""
    )
    $suffix = if ($Default) { " [$Default]" } else { "" }
    $value = Read-Host "$Prompt$suffix"
    if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
    return $value.Trim()
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$installer = Join-Path $root "install-v4.ps1"
if (-not (Test-Path -LiteralPath $installer)) {
    throw "No se encontro install-v4.ps1 junto al asistente: $installer"
}

Write-Host "BAGO install assistant"
Write-Host "----------------------"
Write-Host "Instalador : $installer"
Write-Host "Destino    : $InstallDir"
Write-Host ""

if (-not $AssumeYes -and -not (Read-YesNo -Prompt "Quieres instalar o reparar BAGO ahora?" -Default $true)) {
    Write-Host "Cancelado."
    exit 0
}

if (-not $Mode) {
    $Mode = Read-Choice -Prompt "Modo de instalacion" -Options @("Express", "Advanced") -DefaultIndex 0
}

if (-not $SourceRoot) {
    $SourceRoot = $root
}

$enableContextMenu = -not $NoContextMenu
if (-not $AssumeYes -and -not $NoContextMenu) {
    $enableContextMenu = Read-YesNo -Prompt "Agregar 'Abrir con BAGO' en menu contextual de directorios" -Default $true
}

Write-Host ""
Write-Host "Resumen"
Write-Host "-------"
Write-Host "Modo       : $Mode"
Write-Host "Fuente     : $SourceRoot"
Write-Host "Destino    : $InstallDir"
Write-Host "Dry-run    : $([bool]$DryRun)"
Write-Host "Menu       : $([string]$(if ($enableContextMenu) { 'si' } else { 'no' }))"
Write-Host ""

if ($DryRun) {
    Write-Host "No se ejecuta el instalador."
    exit 0
}

$argsList = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $installer,
    "-SourceRoot",
    $SourceRoot,
    "-InstallDir",
    $InstallDir,
    "-Mode",
    $Mode
)

$shell = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
if (-not $shell) {
    $shell = (Get-Command powershell.exe -ErrorAction SilentlyContinue).Source
}
if (-not $shell) {
    throw "No se encontro pwsh.exe ni powershell.exe en PATH."
}

if (-not $enableContextMenu) {
    $argsList += "-NoContextMenu"
}

& $shell @argsList
exit $LASTEXITCODE
