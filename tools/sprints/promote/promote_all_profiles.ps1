# Promote the working copy at C:\Program Files\BAGO (v4.7 with Qwen skin +
# BagoREPL fix) into every BAGO install profile on this machine.

# 1. Pre-flight: confirm repo state.
$ErrorActionPreference = 'Stop'
$repoRoot = 'C:\Program Files\BAGO'
$installScript = Join-Path $repoRoot 'install-v4.ps1'

if (-not (Test-Path $installScript)) {
    Write-Error "install-v4.ps1 not found at $installScript"
    exit 1
}

# 2. Confirm we are running elevated (install-v4.ps1 needs it for Program Files).
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warning "Not running elevated. install-v4.ps1 will likely fail on the 'stable' profile (writes to C:\Program Files). Re-launch this script from an elevated PowerShell."
}

# 3. Three profiles: stable (Program Files), des (dev tree), ign (launch).
$profiles = @('stable', 'des', 'ign')
$results = @()

foreach ($p in $profiles) {
    Write-Host ""
    Write-Host "=== Updating profile: $p ===" -ForegroundColor Cyan

    # Build a log file for this run.
    $logDir = Join-Path $env:ProgramData 'BAGO\promote-logs'
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $logPath = Join-Path $logDir ("promote-{0}-{1}.log" -f $p, $stamp)

    $args = @{
        SourceRoot = $repoRoot
        Profile    = $p
        NoPathUpdate = $true   # don't touch PATH on every profile, just the install copy
    }

    try {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $installScript @args 2>&1 | Tee-Object -FilePath $logPath
        $exitCode = $LASTEXITCODE
        $results += [pscustomobject]@{
            Profile = $p
            Exit    = $exitCode
            Log     = $logPath
        }
        if ($exitCode -ne 0) {
            Write-Host "  FAIL ($exitCode). See $logPath" -ForegroundColor Red
        } else {
            Write-Host "  OK. Log: $logPath" -ForegroundColor Green
        }
    } catch {
        Write-Host "  EXCEPTION: $_" -ForegroundColor Red
        $results += [pscustomobject]@{
            Profile = $p
            Exit    = -1
            Log     = $logPath
        }
    }
}

# 4. Summary.
Write-Host ""
Write-Host "=== Promote summary ===" -ForegroundColor Cyan
$results | Format-Table -AutoSize | Out-String | Write-Host

# 5. If any profile failed, exit non-zero so the caller knows.
$failed = $results | Where-Object { $_.Exit -ne 0 }
if ($failed) {
    Write-Host "One or more profiles failed. Rollback is available via rollback-v4.ps1." -ForegroundColor Yellow
    exit 2
}

Write-Host "All profiles updated." -ForegroundColor Green
exit 0