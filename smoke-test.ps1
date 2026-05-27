#Requires -Version 5.1
<#
.SYNOPSIS
    Smoke test post-instalación de BAGO para usuarios nuevos.
#>

$ErrorActionPreference = 'Stop'
$passed = 0
$failed = 0
$warnings = 0

function Test-BagoSmoke {
    param([string]$Name, [scriptblock]$Test)
    Write-Host -NoNewline "  [..] $Name ... "
    try {
        $res = & $Test
        if ($res -match "^WARN") {
            Write-Host "WARN" -ForegroundColor Yellow
            Write-Host "       $($res -replace '^WARN: ')" -ForegroundColor DarkGray
            $script:warnings++
        } elseif ($res -match "^FAIL") {
            Write-Host "FAIL" -ForegroundColor Red
            Write-Host "       $($res -replace '^FAIL: ')" -ForegroundColor DarkGray
            $script:failed++
        } else {
            Write-Host "OK" -ForegroundColor Green
            $script:passed++
        }
    } catch {
        Write-Host "FAIL" -ForegroundColor Red
        Write-Host "       $_" -ForegroundColor DarkGray
        $script:failed++
    }
}

Write-Host "`nBAGO Smoke Test`n================`n" -ForegroundColor Cyan

$expectedRoot = "C:\Program Files\BAGO"
$bagoCmd = Join-Path $expectedRoot "bago.cmd"

Test-BagoSmoke "bago resuelve en PATH" {
    $cmd = Get-Command bago -ErrorAction SilentlyContinue
    if (-not $cmd) { return "FAIL: No encontrado en PATH" }
    $path = $cmd.Source
    if ($path -notlike "*$expectedRoot*") {
        return "WARN: bago apunta a $path (sesion vieja?). En terminal nueva ira a $expectedRoot"
    }
    "OK"
}

Test-BagoSmoke "bago validate pasa" {
    $out = & $bagoCmd validate 2>&1
    $outStr = $out | Out-String
    if ($outStr -notmatch "GO manifest") { return "FAIL: validate no paso: $outStr" }
    "OK"
}

Test-BagoSmoke "bago smoke pasa" {
    $out = & $bagoCmd smoke 2>&1
    $outStr = $out | Out-String
    if ($LASTEXITCODE -ne 0) { return "FAIL: smoke rc=$($LASTEXITCODE): $outStr" }
    if ($outStr -notmatch "smoke\[pack\]") { return "FAIL: smoke no genero salida esperada: $outStr" }
    "OK"
}

Test-BagoSmoke "bago preflight-check funciona" {
    & $bagoCmd preflight-check *> $null
    $rc = $LASTEXITCODE
    if ($rc -ne 0) { return "FAIL: preflight rc=$rc" }
    "OK"
}

Test-BagoSmoke "estructura de runtime existe" {
    $needed = @(".bago","bago.cmd","bago.ps1","bago_core")
    foreach ($n in $needed) {
        if (-not (Test-Path (Join-Path $expectedRoot $n))) {
            return "FAIL: Falta $n"
        }
    }
    "OK"
}

Test-BagoSmoke "estado de usuario separado" {
    if (-not (Test-Path "C:\ProgramData\BAGO\user")) {
        return "FAIL: No existe C:\ProgramData\BAGO\user"
    }
    "OK"
}

Write-Host "`n================" -ForegroundColor Cyan
Write-Host "PASSED: $passed" -ForegroundColor Green
Write-Host "WARNINGS: $warnings" -ForegroundColor Yellow
Write-Host "FAILED: $failed" -ForegroundColor $(if ($failed -gt 0) { "Red" } else { "Green" })

if ($failed -gt 0) {
    Write-Host "`nAlgunas pruebas fallaron. Revisa INSTALL.md o ejecuta:" -ForegroundColor Yellow
    Write-Host "  & '$expectedRoot\bago.cmd' validate --verbose" -ForegroundColor DarkGray
    exit 1
} elseif ($warnings -gt 0) {
    Write-Host "`nInstalacion OK con advertencias. Abre una terminal nueva para PATH limpio." -ForegroundColor Yellow
    exit 0
} else {
    Write-Host "`nInstalacion OK. Bienvenido a BAGO." -ForegroundColor Green
    exit 0
}



