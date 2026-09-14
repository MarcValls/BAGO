[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string[]]$Path,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedPublisher,
    [string]$ExpectedThumbprint = "",
    [string]$EvidencePath = "",
    [switch]$SkipSignTool
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$codeSigningOid = "1.3.6.1.5.5.7.3.3"
$records = @()

if ([string]::IsNullOrWhiteSpace($ExpectedPublisher)) {
    throw "ExpectedPublisher debe indicar el sujeto completo o el nombre simple del certificado de firma."
}
if (-not (Get-Command Get-AuthenticodeSignature -ErrorAction SilentlyContinue)) {
    throw "Get-AuthenticodeSignature no está disponible; la verificación Authenticode no puede completarse."
}

function Resolve-SignTool {
    $command = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $kitsRoot = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"
    if (-not (Test-Path -LiteralPath $kitsRoot)) { return $null }
    $candidate = Get-ChildItem -LiteralPath $kitsRoot -Filter signtool.exe -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\x64\\signtool\.exe$' } |
        Sort-Object FullName -Descending |
        Select-Object -First 1
    if ($candidate) { return $candidate.FullName }
    return $null
}

function Test-ExpectedPublisher {
    param(
        [Parameter(Mandatory = $true)]
        [System.Security.Cryptography.X509Certificates.X509Certificate2]$Certificate,
        [Parameter(Mandatory = $true)]
        [string]$Expected
    )
    $expectedValue = $Expected.Trim()
    $subject = [string]$Certificate.Subject
    $simpleName = [string]$Certificate.GetNameInfo(
        [System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName,
        $false
    )
    return $subject.Equals($expectedValue, [System.StringComparison]::OrdinalIgnoreCase) -or
        $simpleName.Equals($expectedValue, [System.StringComparison]::OrdinalIgnoreCase)
}

$signTool = if ($SkipSignTool) { $null } else { Resolve-SignTool }
if (-not $SkipSignTool -and -not $signTool) {
    throw "signtool.exe no está disponible; la verificación Authenticode no puede completarse."
}

foreach ($requestedPath in $Path) {
    $resolved = (Resolve-Path -LiteralPath $requestedPath -ErrorAction Stop).Path
    $signature = Get-AuthenticodeSignature -LiteralPath $resolved
    if ($signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
        throw "Firma Authenticode no válida para '$resolved': $($signature.Status)."
    }
    if (-not $signature.SignerCertificate) {
        throw "La firma de '$resolved' no contiene certificado de firmante."
    }
    $subject = [string]$signature.SignerCertificate.Subject
    if (-not (Test-ExpectedPublisher -Certificate $signature.SignerCertificate -Expected $ExpectedPublisher)) {
        throw "Publisher inesperado para '$resolved': '$subject'."
    }
    $thumbprint = ([string]$signature.SignerCertificate.Thumbprint).Replace(" ", "").ToUpperInvariant()
    $expectedNormalized = $ExpectedThumbprint.Replace(" ", "").ToUpperInvariant()
    if ($expectedNormalized -and $thumbprint -ne $expectedNormalized) {
        throw "Thumbprint inesperado para '$resolved': '$thumbprint'."
    }
    $hasCodeSigningEku = $false
    foreach ($extension in $signature.SignerCertificate.Extensions) {
        if ($extension.Oid.Value -eq "2.5.29.37") {
            $eku = [System.Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]$extension
            if ($eku.EnhancedKeyUsages | Where-Object { $_.Value -eq $codeSigningOid }) {
                $hasCodeSigningEku = $true
                break
            }
        }
    }
    if (-not $hasCodeSigningEku) {
        throw "El certificado de '$resolved' no declara el EKU Code Signing $codeSigningOid."
    }
    if (-not $signature.TimeStamperCertificate) {
        throw "La firma de '$resolved' no contiene timestamp RFC 3161 verificable."
    }
    if (-not $SkipSignTool) {
        & $signTool verify /pa /all /v $resolved | Out-Host
        if ($LASTEXITCODE -ne 0) {
            throw "signtool verify rechazó '$resolved' con código $LASTEXITCODE."
        }
    }
    $records += [ordered]@{
        path = $resolved
        sha256 = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash
        status = $signature.Status.ToString()
        subject = $subject
        thumbprint = $thumbprint
        code_signing_eku = $codeSigningOid
        timestamp_subject = [string]$signature.TimeStamperCertificate.Subject
        timestamp_thumbprint = [string]$signature.TimeStamperCertificate.Thumbprint
        verified_with_signtool = -not $SkipSignTool
    }
}

$evidence = [ordered]@{
    contract = "bago.authenticode-evidence.v1"
    result = "PASS"
    expected_publisher = $ExpectedPublisher
    expected_thumbprint = $ExpectedThumbprint
    files = $records
}
$json = $evidence | ConvertTo-Json -Depth 6
if ($EvidencePath) {
    $parent = Split-Path -Parent $EvidencePath
    if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    [System.IO.File]::WriteAllText($EvidencePath, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
}
$json
