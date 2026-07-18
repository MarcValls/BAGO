#Requires -Version 5.1
[CmdletBinding()]
param([switch]$Keep)

$ErrorActionPreference = "Stop"
$sourceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$installer = Join-Path $sourceRoot "install-v4.ps1"
$tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd("\")
$workRoot = Join-Path $tempRoot ("bago-clean-install-" + [Guid]::NewGuid().ToString("N"))
$installRoot = Join-Path $workRoot "installed"
$userRoot = Join-Path $workRoot "user"
$stateRoot = Join-Path $workRoot "state"
$backupRoot = Join-Path $workRoot "backups"
$previousUserRoot = $env:BAGO_USER_ROOT

try {
    New-Item -ItemType Directory -Path $userRoot -Force | Out-Null
    $seedTime = (Get-Date).ToUniversalTime().ToString("o")
    [ordered]@{
        version = 1
        updated_at = $seedTime
        roles = [ordered]@{
            dev = [ordered]@{
                path = $sourceRoot
                label = "Copia de desarrollo"
                updated_at = $seedTime
            }
        }
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $userRoot "install_selection.json") -Encoding UTF8

    $env:BAGO_USER_ROOT = $userRoot
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer `
        -SourceRoot $sourceRoot `
        -InstallDir $installRoot `
        -BackupRoot $backupRoot `
        -UserStateDir $stateRoot `
        -Mode Express `
        -NoPathUpdate `
        -NoShellIntegration `
        -ElevatedChild
    if ($LASTEXITCODE -ne 0) { throw "install-v4.ps1 falló con código $LASTEXITCODE" }

    $expectedVersion = (Get-Content -LiteralPath (Join-Path $sourceRoot "release_version.txt") -Raw).Trim()
    $installedVersion = (Get-Content -LiteralPath (Join-Path $installRoot "release_version.txt") -Raw).Trim()
    if ($installedVersion -ne $expectedVersion) {
        throw "versión instalada $installedVersion != fuente $expectedVersion"
    }
    foreach ($required in @("bago.ps1", "bago_core\cli.py", "ui-react\dist\index.html", "install_config.json")) {
        if (-not (Test-Path -LiteralPath (Join-Path $installRoot $required))) {
            throw "artefacto instalado ausente: $required"
        }
    }

    $selection = Get-Content -LiteralPath (Join-Path $userRoot "install_selection.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    $selectedActive = [System.IO.Path]::GetFullPath([string]$selection.roles.active.path)
    $expectedActive = [System.IO.Path]::GetFullPath($installRoot)
    if ($selectedActive -ne $expectedActive) {
        throw "install_selection.json no apunta al runtime instalado: actual=$selectedActive esperado=$expectedActive"
    }
    if (-not $selection.roles.dev -or [System.IO.Path]::GetFullPath([string]$selection.roles.dev.path) -ne $sourceRoot) {
        throw "el instalador no preservó el rol dev existente"
    }

    $runtimeConfigPath = Join-Path $installRoot ".bago\config.json"
    $runtimeConfig = Get-Content -LiteralPath $runtimeConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $runtimeConfig | Add-Member -NotePropertyName "clean_install_marker" -NotePropertyValue "preserved" -Force
    $runtimeConfig | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $runtimeConfigPath -Encoding UTF8
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer `
        -SourceRoot $sourceRoot `
        -InstallDir $installRoot `
        -BackupRoot $backupRoot `
        -UserStateDir $stateRoot `
        -Mode Express `
        -SkipTests `
        -NoPathUpdate `
        -NoShellIntegration `
        -ElevatedChild
    if ($LASTEXITCODE -ne 0) { throw "la segunda instalación falló con código $LASTEXITCODE" }
    $updatedRuntimeConfig = Get-Content -LiteralPath $runtimeConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($updatedRuntimeConfig.clean_install_marker -ne "preserved") {
        throw "la actualización no preservó .bago/config.json"
    }

    $python = (Get-Command python.exe -ErrorAction Stop | Select-Object -First 1).Source
    $roleOutput = & $python (Join-Path $installRoot "bago_core\cli.py") install-role show --json | Out-String | ConvertFrom-Json
    if ([System.IO.Path]::GetFullPath([string]$roleOutput.roles.active.path) -ne [System.IO.Path]::GetFullPath($installRoot)) {
        throw "la copia instalada no puede leer install_selection.json"
    }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $installRoot "bago.ps1") --version
    if ($LASTEXITCODE -ne 0) { throw "bago.ps1 instalado no puede arrancar" }
    & $python (Join-Path $installRoot "bago_core\cli.py") validate
    if ($LASTEXITCODE -ne 0) { throw "la copia instalada no supera bago validate" }

    Write-Host "clean-install:PASS version=$installedVersion root=$installRoot" -ForegroundColor Green
} finally {
    if ($null -eq $previousUserRoot) {
        Remove-Item Env:BAGO_USER_ROOT -ErrorAction SilentlyContinue
    } else {
        $env:BAGO_USER_ROOT = $previousUserRoot
    }
    if (-not $Keep -and (Test-Path -LiteralPath $workRoot)) {
        $resolvedWork = [System.IO.Path]::GetFullPath($workRoot)
        if (-not $resolvedWork.StartsWith($tempRoot + "\", [System.StringComparison]::OrdinalIgnoreCase) -or
            -not ([System.IO.Path]::GetFileName($resolvedWork)).StartsWith("bago-clean-install-")) {
            throw "ruta temporal insegura; no se elimina: $resolvedWork"
        }
        Remove-Item -LiteralPath $resolvedWork -Recurse -Force
    }
}
