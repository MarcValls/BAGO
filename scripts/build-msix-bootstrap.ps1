[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PayloadRoot,
    [Parameter(Mandatory=$true)][string]$Publisher,
    [Parameter(Mandatory=$true)][string]$PackageName,
    [Parameter(Mandatory=$true)][string]$OutputRoot,
    [switch]$AllowDirtyCandidate
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$payload = (Resolve-Path $PayloadRoot).Path
$out = [IO.Path]::GetFullPath($OutputRoot)
if (-not (Test-Path (Join-Path $payload 'backend/.bago/core/session_manager.py'))) {
    throw 'PayloadRoot must contain the prepared candidate backend runtime.'
}
if (-not (Test-Path (Join-Path $payload 'backend/install-v4.ps1'))) { throw 'Payload lacks canonical install helper.' }
if (-not $Publisher.StartsWith('CN=', [StringComparison]::OrdinalIgnoreCase)) { throw 'Publisher must be the exact certificate subject (CN=...).' }
if ($PackageName -notmatch '^[A-Za-z0-9.-]{3,50}$') { throw 'Invalid MSIX package name.' }
$git = git -C $repo status --porcelain
$dirty = [bool]$git
if ($dirty -and -not $AllowDirtyCandidate) { throw 'Dirty candidate refused. Pass -AllowDirtyCandidate only for an isolated integration package.' }
if (Test-Path $out) { throw "OutputRoot already exists; refusing to overwrite: $out" }
$null = New-Item -ItemType Directory -Path $out
$stage = Join-Path $out 'stage'
$null = New-Item -ItemType Directory -Path $stage
$hostSource = Join-Path $repo 'bootstrap/msix-host'
$sdkBin = Get-ChildItem 'C:\Program Files (x86)\Windows Kits\10\bin' -Directory | Sort-Object Name -Descending | ForEach-Object { Join-Path $_.FullName 'x64' } | Where-Object { Test-Path (Join-Path $_ 'makeappx.exe') } | Select-Object -First 1
if (-not $sdkBin) { throw 'Windows SDK MakeAppx tools were not found.' }
$publish = Join-Path $out 'host-publish'
dotnet publish (Join-Path $hostSource 'Bago.Bootstrap.Host.csproj') -c Release -r win-x64 --self-contained true -o $publish
if ($LASTEXITCODE -ne 0) { throw 'dotnet publish failed.' }
Copy-Item (Join-Path $publish '*') $stage -Recurse
if (-not (Test-Path (Join-Path $stage 'hostpolicy.dll'))) { throw 'Self-contained host publish lacks hostpolicy.dll.' }
Remove-Item (Join-Path $stage 'Bago.Bootstrap.Host.runtimeconfig.dev.json') -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $stage 'Bago.Bootstrap.Host.pdb') -Force -ErrorAction SilentlyContinue
$authority = Join-Path $stage 'authority'
$null = New-Item -ItemType Directory -Path $authority
Copy-Item (Join-Path $payload 'backend/.bago/core') (Join-Path $authority 'core') -Recurse
Copy-Item (Join-Path $payload 'backend/.bago/api') (Join-Path $authority 'api') -Recurse
Copy-Item (Join-Path $payload 'backend/.bago/tools') (Join-Path $authority 'tools') -Recurse
Copy-Item (Join-Path $payload 'backend/.bago/providers') (Join-Path $authority 'providers') -Recurse
Copy-Item (Join-Path $payload 'backend/scripts') (Join-Path $authority 'scripts') -Recurse
Copy-Item (Join-Path $payload 'backend/bago_core') (Join-Path $authority 'bago_core') -Recurse
Copy-Item (Join-Path $payload 'backend/.bago/contracts') (Join-Path $authority 'contracts') -Recurse
$null = New-Item -ItemType Directory -Path (Join-Path $stage 'payload')
Copy-Item (Join-Path $payload '*') (Join-Path $stage 'payload') -Recurse
Remove-Item (Join-Path $stage 'payload/backend/.bago/core') -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $stage 'payload/backend/.bago/api') -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem (Join-Path $stage 'payload') -Directory -Force -Recurse | Where-Object { $_.Name -like '.pytest-tmp*' -or $_.Name -in @('__pycache__','.pytest_cache','.mypy_cache') } | Sort-Object FullName -Descending | Remove-Item -Recurse -Force
$null = New-Item -ItemType Directory -Path (Join-Path $stage 'Assets')
$logo = [Convert]::FromBase64String('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=')
[IO.File]::WriteAllBytes((Join-Path $stage 'Assets/StoreLogo.png'),$logo)
[IO.File]::WriteAllBytes((Join-Path $stage 'Assets/Square150x150Logo.png'),$logo)
[IO.File]::WriteAllBytes((Join-Path $stage 'Assets/Square44x44Logo.png'),$logo)
$pythonZip = Join-Path $out 'python-3.14.7-embed-amd64.zip'
$pythonUrl = 'https://www.python.org/ftp/python/3.14.7/python-3.14.7-embed-amd64.zip'
Invoke-WebRequest $pythonUrl -OutFile $pythonZip
$expected = 'd297e5ff019966817ad8502465176139f2d3d840fa4ed84b13bed399a6ab1f15'
$actual = (Get-FileHash $pythonZip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "CPython embedded archive hash mismatch: $actual" }
$pythonRoot = Join-Path $stage 'python'
$null = New-Item -ItemType Directory -Path $pythonRoot
Expand-Archive $pythonZip $pythonRoot
$pth = Get-ChildItem $pythonRoot -Filter '*._pth' | Select-Object -First 1
if (-not $pth) { throw 'Embedded CPython path configuration is missing.' }
Set-Content -LiteralPath $pth.FullName -Value @('python314.zip','.', 'DLLs','..\authority','..\authority\core','..\authority\api','..\authority\providers','..\authority\scripts','..\authority\tools') -Encoding Ascii
$version = (Get-Content (Join-Path $repo 'release_version.txt') -Raw).Trim()
$head = (git -C $repo rev-parse HEAD).Trim()
$manifest = Get-Content (Join-Path $hostSource 'AppxManifest.xml') -Raw
$msixVersion = if ($version -match '^\d+\.\d+\.\d+$') { "$version.0" } else { throw 'Canonical version cannot be represented as an MSIX version.' }
$manifest = $manifest.Replace('__PACKAGE_NAME__',$PackageName).Replace('__PUBLISHER__',$Publisher).Replace('__VERSION__',$msixVersion)
Set-Content -LiteralPath (Join-Path $stage 'AppxManifest.xml') -Value $manifest -Encoding utf8
$null = New-Item -ItemType Directory -Path (Join-Path $out 'pri')
& (Join-Path $sdkBin 'makepri.exe') createconfig /cf (Join-Path $out 'pri/priconfig.xml') /dq en-us
if ($LASTEXITCODE -ne 0) { throw 'MakePri createconfig failed.' }
& (Join-Path $sdkBin 'makepri.exe') new /pr $stage /cf (Join-Path $out 'pri/priconfig.xml') /of (Join-Path $stage 'resources.pri')
if ($LASTEXITCODE -ne 0) { throw 'MakePri failed.' }
$hashOutput = @(& dotnet run --project (Join-Path $hostSource 'HashTool/HashTool.csproj') -c Release -- $stage 2>&1)
$hashExit = $LASTEXITCODE
$packagePayloadDigest = ($hashOutput | ForEach-Object { [string]$_ } | Where-Object { $_ -match '^[0-9a-fA-F]{64}$' } | Select-Object -Last 1)
if ($null -eq $packagePayloadDigest -or $hashExit -ne 0 -or $packagePayloadDigest -notmatch '^[0-9a-f]{64}$') {
    throw "Could not calculate canonical package payload digest (exit=$hashExit; output=$($hashOutput -join ' | '))."
}
$branch = ([string](git -C $repo branch --show-current)).Trim()
if ([string]::IsNullOrWhiteSpace($branch)) {
    $tag = ([string](git -C $repo describe --exact-match --tags HEAD)).Trim()
    $branch = if ([string]::IsNullOrWhiteSpace($tag)) { 'DETACHED' } else { "DETACHED@$tag" }
}
$releaseManifest = [ordered]@{
    schema='bago.release-manifest.v1'; version=$version; git_head=$head; branch=$branch; dirty=$dirty
    package_payload_sha256=$packagePayloadDigest
    payload_root=(Split-Path $payload -Leaf)
}
$manifestPath = Join-Path $stage 'release-manifest.json'
$manifestJson = $releaseManifest | ConvertTo-Json -Depth 5
Set-Content -LiteralPath $manifestPath -Value $manifestJson -Encoding utf8
$manifestDigest = (Get-FileHash $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
$policy = [ordered]@{ Publisher=$Publisher; PackageName=$PackageName; Version="$version.0"; ReleaseManifestSha256=$manifestDigest; PackagePayloadSha256=$packagePayloadDigest }
Set-Content -LiteralPath (Join-Path $stage 'bootstrap-policy.json') -Value ($policy | ConvertTo-Json) -Encoding utf8
$manifestPath = Join-Path $stage 'AppxManifest.xml'
$msix = Join-Path $out "BAGO-Bootstrap-$version.msix"
& (Join-Path $sdkBin 'makeappx.exe') pack /d $stage /p $msix /o
if ($LASTEXITCODE -ne 0) { throw 'MakeAppx failed.' }
$receipt = [ordered]@{ candidate_head=$head; branch=$releaseManifest.branch; dirty=$dirty; payload=$payload; manifest_sha256=$manifestDigest; package=$msix; package_sha256=(Get-FileHash $msix -Algorithm SHA256).Hash.ToLowerInvariant(); signature='NOT_SIGNED' }
Set-Content -LiteralPath (Join-Path $out 'build-receipt.json') -Value ($receipt | ConvertTo-Json -Depth 5)
Write-Output (Join-Path $out 'build-receipt.json')
