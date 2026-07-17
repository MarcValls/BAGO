#Requires -Version 5.1
<#
.SYNOPSIS
  Instalador remoto de BAGO - usa la release compatible mas reciente de GitHub.

.DESCRIPTION
  Descarga una release compatible de GitHub, lo extrae y ejecuta install-v4.ps1.
  Uso desde terminal (sin descargar nada manualmente):

      iwr -useb https://raw.githubusercontent.com/MarcValls/BAGO/main/install-remote.ps1 | iex

  O con PowerShell 5:

      (New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/MarcValls/BAGO/main/install-remote.ps1') | Invoke-Expression

.PARAMETER InstallDir
  Directorio de instalacion. Default: %BAGO_INSTALL_DIR% o %ProgramFiles%\BAGO

.PARAMETER Mode
  Modo del asistente local: Express o Advanced.

.PARAMETER SkipTests
  Omite tests post-instalacion.

.PARAMETER Tag
  Tag exacto de la release a instalar. Si no se especifica, usa la release
  estable mas reciente publicada en GitHub.

.PARAMETER RequireSignature
  Exige una firma detached .sig/.asc verificable con gpg.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = "",
    [ValidateSet("Express", "Advanced")]
    [string]$Mode = "Express",
    [string]$Tag = "",
    [switch]$SkipTests,
    [switch]$NoPathUpdate,
    [switch]$RequireSignature
)

$ErrorActionPreference = "Stop"

function Get-DefaultInstallDir {
    [string]$override = [System.Environment]::GetEnvironmentVariable("BAGO_INSTALL_DIR")
    if (-not [string]::IsNullOrWhiteSpace($override)) { return [System.IO.Path]::GetFullPath($override) }
    [string]$programFilesRoot = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::ProgramFiles)
    if ([string]::IsNullOrWhiteSpace($programFilesRoot)) { $programFilesRoot = [System.Environment]::GetEnvironmentVariable("ProgramFiles") }
    if ([string]::IsNullOrWhiteSpace($programFilesRoot)) { $programFilesRoot = [System.IO.Path]::GetTempPath() }
    return (Join-Path $programFilesRoot "BAGO")
}

if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    $InstallDir = Get-DefaultInstallDir
}

function Get-LatestRelease {
    $ceiling = Get-ManagerVersion
    $apiUrl = "https://api.github.com/repos/MarcValls/BAGO/releases?per_page=100"
    $releases = Invoke-RestMethod -Uri $apiUrl -Headers @{ Accept = "application/vnd.github+json" } -UseBasicParsing
    return @($releases) |
        Where-Object { -not $_.draft -and -not $_.prerelease -and (Test-ReleaseAllowed -ReleaseTag ([string]$_.tag_name) -CeilingTag $ceiling) } |
        Sort-Object { [datetime]$_.published_at } -Descending |
        Select-Object -First 1
}

function Get-TaggedRelease {
    param([Parameter(Mandatory = $true)][string]$RequestedTag)
    $tag = $RequestedTag.Trim()
    if (-not $tag) { return $null }
    $url = "https://api.github.com/repos/MarcValls/BAGO/releases/tags/$tag"
    $release = Invoke-RestMethod -Uri $url -Headers @{ Accept = "application/vnd.github+json" } -UseBasicParsing
    $ceiling = Get-ManagerVersion
    if (-not (Test-ReleaseAllowed -ReleaseTag ([string]$release.tag_name) -CeilingTag $ceiling)) {
        throw "La release $($release.tag_name) es futura respecto a la version permitida $ceiling."
    }
    return $release
}

function Get-PairedBundle {
    param([Parameter(Mandatory = $true)]$Release)
    $assets = @($Release.assets)
    foreach ($bundle in @($assets | Where-Object { $_.name -like "*.zip" -and $_.name -notlike "*.sha256" })) {
        $checksumName = ([string]$bundle.name) + ".sha256"
        $checksum = $assets | Where-Object { ([string]$_.name).ToLowerInvariant() -eq $checksumName.ToLowerInvariant() } | Select-Object -First 1
        if ($checksum) {
            $signatureName = ([string]$bundle.name) + ".sig"
            $signature = $assets | Where-Object { ([string]$_.name).ToLowerInvariant() -eq $signatureName.ToLowerInvariant() } | Select-Object -First 1
            if (-not $signature) {
                $signatureName = ([string]$bundle.name) + ".asc"
                $signature = $assets | Where-Object { ([string]$_.name).ToLowerInvariant() -eq $signatureName.ToLowerInvariant() } | Select-Object -First 1
            }
            return [ordered]@{ bundle = $bundle; checksum = $checksum; signature = $signature }
        }
    }
    return $null
}

function Assert-ZipMagic {
    param([Parameter(Mandatory = $true)][string]$Path)
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        $first = $stream.ReadByte()
        $second = $stream.ReadByte()
        if ($first -ne 0x50 -or $second -ne 0x4B) {
            throw "El asset descargado no tiene cabecera ZIP valida."
        }
    } finally {
        $stream.Dispose()
    }
}

function Normalize-VersionTag {
    param([Parameter(Mandatory = $true)][string]$Value)
    return ($Value.Trim() -replace '^[vV]', '')
}

function Parse-VersionTag {
    param([Parameter(Mandatory = $true)][string]$Value)
    $text = Normalize-VersionTag $Value
    if ($text -notmatch '^(?<major>\d+)\.(?<minor>\d+)\.(?<patch>\d+)(?:-(?<pre>[0-9A-Za-z.-]+))?(?:\+.*)?$') {
        return $null
    }
    $pre = @()
    if ($Matches.pre) {
        $pre = $Matches.pre.Split('.')
    }
    return [pscustomobject]@{
        major = [int]$Matches.major
        minor = [int]$Matches.minor
        patch = [int]$Matches.patch
        prerelease = $pre
    }
}

function Compare-VersionTags {
    param(
        [Parameter(Mandatory = $true)]$Left,
        [Parameter(Mandatory = $true)]$Right
    )
    $a = if ($Left -is [string]) { Parse-VersionTag $Left } else { $Left }
    $b = if ($Right -is [string]) { Parse-VersionTag $Right } else { $Right }
    if (-not $a -or -not $b) { return 0 }
    foreach ($key in @('major', 'minor', 'patch')) {
        if ($a.$key -ne $b.$key) { return ($a.$key - [int]$b.$key) }
    }
    $aPre = @($a.prerelease)
    $bPre = @($b.prerelease)
    if (-not $aPre.Count -and -not $bPre.Count) { return 0 }
    if (-not $aPre.Count) { return 1 }
    if (-not $bPre.Count) { return -1 }
    $length = [Math]::Max($aPre.Count, $bPre.Count)
    for ($i = 0; $i -lt $length; $i++) {
        if ($i -ge $aPre.Count) { return -1 }
        if ($i -ge $bPre.Count) { return 1 }
        $leftPart = [string]$aPre[$i]
        $rightPart = [string]$bPre[$i]
        $leftNum = $leftPart -match '^\d+$'
        $rightNum = $rightPart -match '^\d+$'
        if ($leftNum -and $rightNum) {
            $diff = [int]$leftPart - [int]$rightPart
            if ($diff -ne 0) { return $diff }
            continue
        }
        if ($leftNum) { return -1 }
        if ($rightNum) { return 1 }
        $diff = [string]::Compare($leftPart, $rightPart, $true)
        if ($diff -ne 0) { return $diff }
    }
    return 0
}

function Get-ManagerVersion {
    $candidates = @(
        (Join-Path $PSScriptRoot 'release_version.txt'),
        (Join-Path $PSScriptRoot 'package.json')
    )
    foreach ($candidate in $candidates) {
        if (-not (Test-Path -LiteralPath $candidate)) { continue }
        try {
            if ($candidate -like '*.json') {
                $json = Get-Content -LiteralPath $candidate -Raw | ConvertFrom-Json
                if ($json.version) { return Normalize-VersionTag ([string]$json.version) }
            } else {
                $text = (Get-Content -LiteralPath $candidate -Raw).Trim()
                if ($text) { return Normalize-VersionTag $text }
            }
        } catch {}
    }
    return ''
}

function Test-ReleaseAllowed {
    param(
        [Parameter(Mandatory = $true)][string]$ReleaseTag,
        [Parameter(Mandatory = $true)][string]$CeilingTag
    )
    $release = Parse-VersionTag $ReleaseTag
    $ceiling = Parse-VersionTag $CeilingTag
    if (-not $release -or -not $ceiling) { return $true }
    return ((Compare-VersionTags -Left $release -Right $ceiling) -le 0)
}

if ($Tag) {
    $release = Get-TaggedRelease -RequestedTag $Tag
    if (-not $release) {
        throw "No se encontro la release con tag $Tag."
    }
} else {
    $release = Get-LatestRelease
}
if (-not $release) {
    throw "No se encontro ninguna release compatible publicada de BAGO."
}
$version = [string]$release.tag_name
$contract = Get-PairedBundle -Release $release
if (-not $contract) {
    throw "La release $version no contiene un par instalable ZIP + SHA256."
}
$assetInfo = $contract.bundle
$checksumInfo = $contract.checksum
$signatureInfo = $contract.signature
if ($RequireSignature -and -not $signatureInfo) {
    throw "La release $version no publica firma detached .sig/.asc."
}
$asset = [string]$assetInfo.name
$releaseUrl = [string]$assetInfo.browser_download_url
$tempZip = Join-Path $env:TEMP $asset
$tempChecksum = Join-Path $env:TEMP ([string]$checksumInfo.name)
$tempSignature = if ($signatureInfo) { Join-Path $env:TEMP ([string]$signatureInfo.name) } else { "" }
$safeVersion = $version -replace '[^A-Za-z0-9._-]', '_'
$tempExtract = Join-Path $env:TEMP "bago-$safeVersion-extract"

Write-Host "[install-remote] Descargando checksum $($checksumInfo.name) ..." -ForegroundColor Cyan
Invoke-WebRequest -Uri ([string]$checksumInfo.browser_download_url) -OutFile $tempChecksum -UseBasicParsing
Write-Host "[install-remote] Descargando BAGO $version ($asset) ..." -ForegroundColor Cyan
Invoke-WebRequest -Uri $releaseUrl -OutFile $tempZip -UseBasicParsing

$checksumText = Get-Content -LiteralPath $tempChecksum -Raw
$match = [regex]::Match($checksumText, "(?i)\b[a-f0-9]{64}\b")
if (-not $match.Success) {
    throw "El asset SHA256 no contiene un hash valido."
}
$expectedHash = $match.Value.ToLowerInvariant()
$actualHash = (Get-FileHash -LiteralPath $tempZip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne $expectedHash) {
    throw "SHA256 no coincide. Esperado $expectedHash, obtenido $actualHash."
}
$githubDigest = ([string]$assetInfo.digest) -replace '(?i)^sha256:', ''
if ($githubDigest -and $actualHash -ne $githubDigest.ToLowerInvariant()) {
    throw "El digest publicado por GitHub no coincide con el bundle."
}
Assert-ZipMagic -Path $tempZip
Write-Host "[install-remote] SHA256 verificado: $actualHash" -ForegroundColor Green

if ($signatureInfo) {
    Write-Host "[install-remote] Descargando firma $($signatureInfo.name) ..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri ([string]$signatureInfo.browser_download_url) -OutFile $tempSignature -UseBasicParsing
    $gpg = Get-Command gpg.exe -ErrorAction SilentlyContinue
    if ($gpg) {
        & $gpg.Source --batch --verify $tempSignature $tempZip
        if ($LASTEXITCODE -ne 0) { throw "La firma detached no es valida." }
        Write-Host "[install-remote] Firma detached verificada." -ForegroundColor Green
    } elseif ($RequireSignature) {
        throw "RequireSignature exige gpg.exe, pero no esta disponible."
    } else {
        Write-Warning "Firma publicada pero no verificada: gpg.exe no disponible."
    }
} else {
    Write-Warning "La release no publica firma detached; se ha verificado SHA256 y digest GitHub."
}

Write-Host "[install-remote] Extrayendo ..." -ForegroundColor Cyan
if (Test-Path $tempExtract) { Remove-Item -Recurse -Force $tempExtract }
Expand-Archive -Path $tempZip -DestinationPath $tempExtract -Force

$sourceRoot = $tempExtract
$installScript = Join-Path $sourceRoot "install-v4.ps1"
if (-not (Test-Path $installScript)) {
    $package = Get-ChildItem $tempExtract -Directory | Select-Object -First 1
    if ($package) {
        $sourceRoot = $package.FullName
        $installScript = Join-Path $sourceRoot "install-v4.ps1"
    }
}
if (-not (Test-Path $installScript)) {
    throw "No se encontro install-v4.ps1 dentro del paquete descargado."
}
$launcherPath = Join-Path $sourceRoot "bago_core\launcher.py"
if (-not (Test-Path $launcherPath)) {
    throw "El paquete descargado no contiene bago_core\launcher.py."
}
$releaseVersionPath = Join-Path $sourceRoot "release_version.txt"
if (Test-Path $releaseVersionPath) {
    $bundleVersion = (Get-Content -LiteralPath $releaseVersionPath -Raw).Trim()
    if (($bundleVersion -replace '^v', '') -ne ($version -replace '^v', '')) {
        throw "La version del bundle ($bundleVersion) no coincide con la release ($version)."
    }
}
Write-Host "[install-remote] Compatibilidad del bundle verificada." -ForegroundColor Green

Write-Host "[install-remote] Ejecutando instalador local ..." -ForegroundColor Cyan
$argsList = @("-SourceRoot", $sourceRoot, "-InstallDir", $InstallDir, "-Mode", $Mode)
if ($SkipTests) { $argsList += "-SkipTests" }
if ($NoPathUpdate) { $argsList += "-NoPathUpdate" }
& powershell.exe -ExecutionPolicy Bypass -File $installScript @argsList
if ($LASTEXITCODE -ne 0) {
    throw "install-v4.ps1 fallo con codigo $LASTEXITCODE."
}

Write-Host "[install-remote] Limpieza temporal ..." -ForegroundColor Cyan
Remove-Item -Force $tempZip -ErrorAction SilentlyContinue
Remove-Item -Force $tempChecksum -ErrorAction SilentlyContinue
if ($tempSignature) { Remove-Item -Force $tempSignature -ErrorAction SilentlyContinue }
Remove-Item -Recurse -Force $tempExtract -ErrorAction SilentlyContinue

foreach ($profilePath in @($PROFILE.CurrentUserAllHosts, $PROFILE.CurrentUserCurrentHost)) {
    if ($profilePath -and (Test-Path -LiteralPath $profilePath)) {
        . $profilePath
    }
}

Write-Host "[install-remote] BAGO $version instalado en $InstallDir" -ForegroundColor Green
