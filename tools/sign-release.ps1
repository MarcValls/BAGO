# P1-04 helper: sign the BAGO Installation Manager artefacts.
#
# Background. The BAGO Installation Manager ships as an unsigned
# EXE. Modern Windows (SmartScreen, Defender for Endpoint, AppLocker)
# blocks or warns on unsigned installers, so the release is not viable
# for enterprise deployment until we sign it.
#
# This script wraps `signtool.exe` with the conventions we use:
#   1. SHA-256 of the EXE is computed and compared against the value
#      in the matching *.sha256 file.
#   2. `signtool sign` is invoked with a timestamping authority so the
#      signature remains valid after the certificate expires.
#   3. The signed EXE is re-hashed and the .sha256 file is updated so
#      downstream consumers (releases job, package manager) can verify
#      integrity even if they do not check the Authenticode chain.
#
# Requirements:
#   - signtool.exe on PATH (ships with the Windows SDK; usually
#     `C:\Program Files (x86)\Windows Kits\10\bin\<ver>\x64\signtool.exe`).
#   - A code-signing certificate available as a .pfx file or installed
#     in the local certificate store.
#   - A timestamping URL provided by your CA (e.g.
#     http://timestamp.digicert.com for DigiCert).
#
# Usage:
#   pwsh -NoProfile -File tools/sign-release.ps1 \
#     -ExePath "dist/BAGO-Installation-Manager-4.6.1-win-x64.exe" \
#     -Sha256Path "dist/BAGO-Installation-Manager-4.6.1-win-x64.exe.sha256" \
#     -PfxPath "C:\keys\bago-code-sign.pfx" \
#     -PfxPassword (Read-Host -AsSecureString) \
#     -TimestampUrl "http://timestamp.digicert.com"

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ExePath,
    [Parameter(Mandatory = $true)][string]$Sha256Path,
    [Parameter(Mandatory = $true)][string]$PfxPath,
    [Parameter()][System.Security.SecureString]$PfxPassword,
    [Parameter(Mandatory = $true)][string]$TimestampUrl,
    [Parameter()][string]$SignToolPath = "signtool.exe",
    [Parameter()][string]$Description = "BAGO Installation Manager",
    [Parameter()][string]$DescriptionUrl = "https://github.com/MarcValls/BAGO"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $ExePath)) {
    throw "ExePath no encontrado: $ExePath"
}
if (-not (Test-Path -LiteralPath $PfxPath)) {
    throw "PfxPath no encontrado: $PfxPath"
}
if (-not (Get-Command $SignToolPath -ErrorAction SilentlyContinue) -and -not (Test-Path -LiteralPath $SignToolPath)) {
    throw "signtool.exe no encontrado en PATH ni en $SignToolPath"
}

# 1) Verify the pre-sign SHA-256 matches the value shipped in the .sha256
#    file. This catches tampering between build and sign.
$expected = (Get-Content -LiteralPath $Sha256Path -Raw).Trim().Split(' ')[0]
$actual = (Get-FileHash -LiteralPath $ExePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($expected -ne $actual) {
    throw "SHA-256 mismatch before signing. expected=$expected actual=$actual"
}
Write-Host "Pre-sign SHA-256 OK: $actual"

# 2) Sign with signtool. The /fd sha256 /td sha256 flags ask for SHA-256
#    Authenticode, which is required for Windows 11 SmartScreen and for
#    enterprise GPOs that disable SHA-1 signatures.
$pfxArg = @()
if ($PfxPassword) {
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($PfxPassword)
    try {
        $plain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    } finally {
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
    $pfxArg = @("/p", $plain)
}
$signArgs = @(
    "sign"
    "/fd", "sha256"
    "/td", "sha256"
    "/tr", $TimestampUrl
    "/f", $PfxPath
    "/d", $Description
    "/du", $DescriptionUrl
) + $pfxArg + @($ExePath)
& $SignToolPath @signArgs
if ($LASTEXITCODE -ne 0) {
    throw "signtool fallo con codigo $LASTEXITCODE"
}
Write-Host "Signed: $ExePath"

# 3) Verify the signature, then refresh the .sha256 file so downstream
#    verifiers pick up the post-sign hash.
& $SignToolPath @("verify", "/pa", $ExePath) | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "signtool verify fallo con codigo $LASTEXITCODE"
}
$postHash = (Get-FileHash -LiteralPath $ExePath -Algorithm SHA256).Hash.ToLowerInvariant()
$postHash + "  " + (Split-Path -Leaf $ExePath) | Set-Content -LiteralPath $Sha256Path -Encoding ASCII
Write-Host "Post-sign SHA-256: $postHash"
Write-Host "Updated $Sha256Path"
