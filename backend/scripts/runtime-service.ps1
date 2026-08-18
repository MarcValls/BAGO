[CmdletBinding()]
param(
    [ValidateSet('start', 'backend', 'stop', 'status')]
    [string]$Action = 'start'
)

$ErrorActionPreference = 'Stop'
$RuntimeRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$UserRoot = if ($env:BAGO_USER_ROOT) {
    [System.IO.Path]::GetFullPath($env:BAGO_USER_ROOT)
} elseif ($env:LOCALAPPDATA) {
    Join-Path $env:LOCALAPPDATA 'BAGO'
} else {
    Join-Path ([System.IO.Path]::GetTempPath()) 'BAGO'
}
$RunRoot = Join-Path $UserRoot 'run'
$PidFile = Join-Path $RunRoot 'backend-8080.pid'
$OutLog = Join-Path $RunRoot 'backend-8080.log'
$ErrLog = Join-Path $RunRoot 'backend-8080.err.log'
$HealthUrl = 'http://127.0.0.1:8080/health'
$BootstrapProjectRoot = Join-Path ([System.IO.Path]::GetTempPath()) 'BAGO\headless'

New-Item -ItemType Directory -Path $RunRoot -Force | Out-Null
New-Item -ItemType Directory -Path $BootstrapProjectRoot -Force | Out-Null

function Resolve-BagoPython {
    if ($env:BAGO_PYTHON -and (Test-Path -LiteralPath $env:BAGO_PYTHON)) {
        return $env:BAGO_PYTHON
    }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $command) { $command = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1 }
    if (-not $command -or -not $command.Source) {
        throw 'Python no esta disponible para iniciar el backend de BAGO.'
    }
    return [string]$command.Source
}

function Test-BagoHealth {
    try {
        $response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Get-OwnedBackendProcess {
    if (-not (Test-Path -LiteralPath $PidFile)) { return $null }
    $processId = 0
    if (-not [int]::TryParse((Get-Content -LiteralPath $PidFile -Raw).Trim(), [ref]$processId)) { return $null }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$processId" -ErrorAction SilentlyContinue
    if (-not $process) { return $null }
    $commandLine = [string]$process.CommandLine
    if ($commandLine -notlike '*bago_core.launcher*' -or $commandLine -notlike '*serve*') { return $null }
    return $process
}

function Start-BagoBackend {
    $owned = Get-OwnedBackendProcess
    if ($owned -and (Test-BagoHealth)) {
        Write-Output "backend listo pid=$($owned.ProcessId)"
        return
    }
    if (Test-BagoHealth) { throw 'El puerto 8080 esta ocupado por un backend no gestionado por este runtime.' }
    if ($owned) { Stop-Process -Id $owned.ProcessId -Force -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue

    $python = Resolve-BagoPython
    $arguments = @(
        '-u', '-m', 'bago_core.launcher',
        '--base-path', ('"' + $BootstrapProjectRoot + '"'),
        'serve', '--host', '127.0.0.1', '--port', '8080',
        '--ui-dist', ('"' + (Join-Path $RuntimeRoot 'ui-react\dist') + '"')
    )
    $process = Start-Process -FilePath $python -ArgumentList $arguments `
        -WorkingDirectory $RuntimeRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog
    $process.Id | Set-Content -LiteralPath $PidFile -Encoding ascii

    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($process.HasExited) {
            Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
            throw "El backend termino durante el arranque. Revisa $ErrLog"
        }
        if (Test-BagoHealth) {
            Write-Output "backend iniciado pid=$($process.Id)"
            return
        }
        Start-Sleep -Milliseconds 500
    }
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    throw "El backend no respondio en 30 segundos. Revisa $ErrLog"
}

function Stop-BagoBackend {
    $owned = Get-OwnedBackendProcess
    if ($owned) {
        Stop-Process -Id $owned.ProcessId -Force -ErrorAction SilentlyContinue
        try { Wait-Process -Id $owned.ProcessId -Timeout 10 -ErrorAction SilentlyContinue } catch {}
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    Write-Output 'backend detenido'
}

switch ($Action) {
    'start' { Start-BagoBackend }
    'backend' { Start-BagoBackend }
    'stop' { Stop-BagoBackend }
    'status' {
        $owned = Get-OwnedBackendProcess
        [pscustomobject]@{
            running = [bool]($owned -and (Test-BagoHealth))
            pid = if ($owned) { $owned.ProcessId } else { $null }
            runtime_root = $RuntimeRoot
            health_url = $HealthUrl
        } | ConvertTo-Json -Compress
    }
}
