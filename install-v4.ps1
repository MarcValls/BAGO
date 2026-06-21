[CmdletBinding()]
param(
    [string]$SourceRoot = "",
    [string]$PackageZip = "",
    [string]$Profile = "",
    [string]$InstallDir = "C:\Program Files\BAGO",
    [string]$BackupRoot = "$env:ProgramData\BAGO\backups",
    [string]$UserStateDir = "$env:ProgramData\BAGO\user",
    [string]$Mode = "",
    [switch]$SkipTests,
    [switch]$RepairOnly,
    [switch]$NoPathUpdate
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-FullPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [System.IO.Path]::GetFullPath($Path)
}

function Get-RelativePathCompat {
    param(
        [Parameter(Mandatory = $true)][string]$BasePath,
        [Parameter(Mandatory = $true)][string]$TargetPath
    )
    $baseFull = (Get-FullPath $BasePath).TrimEnd("\") + "\"
    $targetFull = Get-FullPath $TargetPath
    try {
        return [System.IO.Path]::GetRelativePath($baseFull, $targetFull)
    } catch {
        $baseUri = [System.Uri]::new($baseFull)
        $targetUri = [System.Uri]::new($targetFull)
        $relativeUri = $baseUri.MakeRelativeUri($targetUri)
        return [System.Uri]::UnescapeDataString($relativeUri.ToString()).Replace("/", "\")
    }
}

function Assert-SafeTarget {
    param([Parameter(Mandatory = $true)][string]$Path)
    $full = Get-FullPath $Path
    $root = [System.IO.Path]::GetPathRoot($full)
    if ([string]::IsNullOrWhiteSpace($full) -or $full -eq $root) {
        throw "Unsafe install target: $full"
    }
    return $full
}

function Normalize-ProfileName {
    param([Parameter(Mandatory = $true)][string]$Name)
    switch ($Name.Trim().ToLowerInvariant()) {
        "stable" { return "stable" }
        "prod" { return "stable" }
        "production" { return "stable" }
        "release" { return "stable" }
        "des" { return "des" }
        "dev" { return "des" }
        "development" { return "des" }
        "ign" { return "ign" }
        "integration" { return "ign" }
        "integracion" { return "ign" }
        "" { throw "Perfil invalido: vacio" }
        default { throw "Perfil invalido: $Name" }
    }
}

function Get-ProfileInstallDir {
    param([Parameter(Mandatory = $true)][string]$ProfileName)
    [string]$programFilesRoot = [System.Environment]::GetEnvironmentVariable("ProgramFiles")
    if ([string]::IsNullOrWhiteSpace($programFilesRoot)) { $programFilesRoot = "C:\Program Files" }
    switch ($ProfileName) {
        "stable" { return (Join-Path $programFilesRoot "BAGO") }
        "des" { return (Join-Path (Join-Path $HOME ".bago") "dev") }
        "ign" { return (Join-Path (Join-Path $HOME ".bago") "launch") }
        default { throw "Perfil invalido: $ProfileName" }
    }
}

function Get-ProfileDataRoot {
    $programData = $env:ProgramData
    if (-not $programData) { $programData = "C:\ProgramData" }
    return (Join-Path $programData "BAGO")
}

function Get-ProfileBackupRoot {
    param([Parameter(Mandatory = $true)][string]$ProfileName)
    return (Join-Path (Join-Path (Get-ProfileDataRoot) "backups") $ProfileName)
}

function Get-ProfileUserStateDir {
    param([Parameter(Mandatory = $true)][string]$ProfileName)
    return (Join-Path (Join-Path (Get-ProfileDataRoot) "user") $ProfileName)
}

$profileName = ""
if ($Profile) {
    $profileName = Normalize-ProfileName $Profile
    if (-not $PSBoundParameters.ContainsKey("InstallDir")) {
        $InstallDir = Get-ProfileInstallDir -ProfileName $profileName
    }
    if (-not $PSBoundParameters.ContainsKey("BackupRoot")) {
        $BackupRoot = Get-ProfileBackupRoot -ProfileName $profileName
    }
    if (-not $PSBoundParameters.ContainsKey("UserStateDir")) {
        $UserStateDir = Get-ProfileUserStateDir -ProfileName $profileName
    }
}

function Test-ReleaseExcluded {
    param([Parameter(Mandatory = $true)][string]$RelativePath)
    $rel = $RelativePath.Replace("\", "/").TrimStart("/")
    $parts = $rel.Split("/", [System.StringSplitOptions]::RemoveEmptyEntries)
    foreach ($part in $parts) {
        if ($part -in @(".git", "__pycache__", ".pytest_cache", "node_modules", ".vite")) {
            return $true
        }
    }
    if ([System.IO.Path]::GetFileName($rel) -in @("credentials.json", ".env", ".env.local")) {
        return $true
    }
    foreach ($prefix in @(".bago/state", ".bago/logs", "state", "logs", "PLAN_VERTICE", "release", "dist", "build")) {
        if ($rel -eq $prefix -or $rel.StartsWith("$prefix/")) {
            return $true
        }
    }
    return $false
}

function Copy-ReleaseTree {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    $sourceFull = Get-FullPath $Source
    $destFull = Get-FullPath $Destination
    Get-ChildItem -LiteralPath $sourceFull -Force -Recurse -File | ForEach-Object {
        $relative = Get-RelativePathCompat -BasePath $sourceFull -TargetPath $_.FullName
        if (Test-ReleaseExcluded $relative) {
            return
        }
        $target = Join-Path $destFull $relative
        $targetParent = Split-Path -Parent $target
        New-Item -ItemType Directory -Path $targetParent -Force | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $target -Force
    }
}

function Move-PreservedRuntimeState {
    param(
        [Parameter(Mandatory = $true)][string]$InstallPath,
        [Parameter(Mandatory = $true)][string]$PreservePath
    )
    $preserved = @()
    foreach ($rel in @(".bago\state", ".bago\logs", "state", "logs")) {
        $src = Join-Path $InstallPath $rel
        if (Test-Path -LiteralPath $src) {
            $dst = Join-Path $PreservePath $rel
            New-Item -ItemType Directory -Path (Split-Path -Parent $dst) -Force | Out-Null
            try {
                Move-Item -LiteralPath $src -Destination $dst -Force
                $preserved += $rel
            } catch {
                try {
                    Copy-Item -LiteralPath $src -Destination $dst -Recurse -Force
                    $preserved += $rel
                    Write-Warning "No se pudo mover $rel; se preservo con copia."
                } catch {
                    Write-Warning "No se pudo preservar ${rel}: $($_.Exception.Message)"
                }
            }
        }
    }
    return $preserved
}

function Restore-PreservedRuntimeState {
    param(
        [Parameter(Mandatory = $true)][string]$InstallPath,
        [Parameter(Mandatory = $true)][string]$PreservePath
    )
    if (-not (Test-Path -LiteralPath $PreservePath)) {
        return
    }
    foreach ($rel in @(".bago\state", ".bago\logs", "state", "logs")) {
        $src = Join-Path $PreservePath $rel
        if (-not (Test-Path -LiteralPath $src)) {
            continue
        }
        $target = Join-Path $InstallPath $rel
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Move-Item -LiteralPath $src -Destination $target -Force
    }
}

function Normalize-PathEntry {
    param([string]$Entry)
    return ($Entry.Trim().TrimEnd("\")).ToLowerInvariant()
}

function Set-BagoPathForScope {
    param(
        [Parameter(Mandatory = $true)][ValidateSet("Machine", "User")][string]$Scope,
        [Parameter(Mandatory = $true)][string]$InstallPath
    )
    $current = [Environment]::GetEnvironmentVariable("Path", $Scope)
    if ($null -eq $current) { $current = "" }
    $installNorm = Normalize-PathEntry $InstallPath
    $entries = New-Object System.Collections.Generic.List[string]
    foreach ($entry in ($current -split ";")) {
        $clean = $entry.Trim()
        if ([string]::IsNullOrWhiteSpace($clean)) { continue }
        if ((Normalize-PathEntry $clean) -eq $installNorm) { continue }
        $entries.Add($clean)
    }
    $newEntries = New-Object System.Collections.Generic.List[string]
    $newEntries.Add($InstallPath)
    foreach ($entry in $entries) { $newEntries.Add($entry) }
    [Environment]::SetEnvironmentVariable("Path", ($newEntries -join ";"), $Scope)
}

function Enable-BagoCommandPath {
    param([Parameter(Mandatory = $true)][string]$InstallPath)
    $scope = "Machine"
    try {
        Set-BagoPathForScope -Scope Machine -InstallPath $InstallPath
    } catch {
        Set-BagoPathForScope -Scope User -InstallPath $InstallPath
        $scope = "User"
    }
    $installNorm = Normalize-PathEntry $InstallPath
    $processEntries = New-Object System.Collections.Generic.List[string]
    foreach ($entry in ($env:Path -split ";")) {
        $clean = $entry.Trim()
        if ([string]::IsNullOrWhiteSpace($clean)) { continue }
        if ((Normalize-PathEntry $clean) -eq $installNorm) { continue }
        $processEntries.Add($clean)
    }
    $newProcessEntries = New-Object System.Collections.Generic.List[string]
    $newProcessEntries.Add($InstallPath)
    foreach ($entry in $processEntries) { $newProcessEntries.Add($entry) }
    $env:Path = $newProcessEntries -join ";"
    return $scope
}

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][object]$Value
    )
    $parent = Split-Path -Parent $Path
    if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    ($Value | ConvertTo-Json -Depth 12) | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Read-Choice {
    param(
        [Parameter(Mandatory = $true)][string]$Prompt,
        [Parameter(Mandatory = $true)][string[]]$Options,
        [int]$DefaultIndex = 0
    )
    while ($true) {
        $display = ($Options | ForEach-Object { $_ }) -join "/"
        $suffix = if ($DefaultIndex -ge 0 -and $DefaultIndex -lt $Options.Length) { " [$($Options[$DefaultIndex])]" } else { "" }
        $value = Read-Host "$Prompt ($display)$suffix"
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

function Read-UrlOrDefault {
    param(
        [Parameter(Mandatory = $true)][string]$Prompt,
        [string]$Default = ""
    )
    while ($true) {
        $value = Read-InputOrDefault -Prompt $Prompt -Default $Default
        if ([string]::IsNullOrWhiteSpace($value)) { return $value }
        if ($value -match '^\s*https?://') { return $value }
        if ($value -match '\s') {
            Write-Host "Introduce una URL, no un comando."
            continue
        }
        if ($value -match '^(ollama|gh|git|pwsh|powershell)\b') {
            Write-Host "Eso parece un comando. Aqui va una URL base."
            continue
        }
        Write-Host "La URL debe empezar por http:// o https://."
    }
}

function Invoke-GhDeviceLogin {
    $gh = Get-Command gh.exe -ErrorAction SilentlyContinue
    if (-not $gh) { throw "GitHub device-flow requiere gh CLI." }
    & gh auth status -h github.com 1>$null 2>$null
    if ($LASTEXITCODE -eq 0) { return }
    Write-Host "GitHub device-flow: iniciando gh auth login --device ..."
    & gh auth login --device -h github.com
    if ($LASTEXITCODE -ne 0) { throw "gh auth login --device fallo para github.com." }
    & gh auth status -h github.com 1>$null 2>$null
    if ($LASTEXITCODE -ne 0) { throw "gh auth status fallo despues del login." }
}

function Invoke-OllamaCloudSignin {
    param([Parameter(Mandatory = $true)][string]$BaseUrl)
    Write-Host "Ollama Cloud signin: se abrira el navegador para completar el login."
    Start-Process $BaseUrl | Out-Null
    Read-Host "Completa el login en el navegador y pulsa Enter para continuar" | Out-Null
}

function Protect-String {
    param([Parameter(Mandatory = $true)][string]$PlainText)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($PlainText)
    $entropy = [System.Text.Encoding]::UTF8.GetBytes("BAGO")
    $protected = [System.Security.Cryptography.ProtectedData]::Protect(
        $bytes,
        $entropy,
        [System.Security.Cryptography.DataProtectionScope]::CurrentUser
    )
    return [Convert]::ToBase64String($protected)
}

function Write-EncryptedStore {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][object]$Payload
    )
    $json = $Payload | ConvertTo-Json -Depth 12
    $container = [ordered]@{
        format = "bago-encrypted-v1"
        scope = "CurrentUser"
        payload = Protect-String -PlainText $json
    }
    Write-JsonFile -Path $Path -Value $container
}

function Test-PathWritable {
    param([Parameter(Mandatory = $true)][string]$Path)
    $full = Get-FullPath $Path
    $probe = Join-Path $full ".bago-write-test-$([Guid]::NewGuid().ToString('N')).tmp"
    New-Item -ItemType Directory -Path $full -Force | Out-Null
    try {
        Set-Content -LiteralPath $probe -Value "ok" -Encoding UTF8
        Remove-Item -LiteralPath $probe -Force
        return $true
    } catch {
        Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue
        throw
    }
}

function Get-GitExe {
    $git = (Get-Command git.exe -ErrorAction SilentlyContinue).Source
    if (-not $git) { $git = (Get-Command git -ErrorAction SilentlyContinue).Source }
    return $git
}

function Test-GitRepoAccess {
    param([Parameter(Mandatory = $true)][string]$RepoPath)
    $git = Get-GitExe
    if (-not $git) { throw "git no esta disponible en PATH." }
    $repoFull = Get-FullPath $RepoPath
    if (-not (Test-Path -LiteralPath $repoFull)) { throw "El repositorio de conocimiento no existe: $repoFull" }
    & $git -C $repoFull rev-parse --is-inside-work-tree 1>$null 2>$null
    if ($LASTEXITCODE -ne 0) { throw "La ruta no es un repo git valido: $repoFull" }
    & $git -C $repoFull status --short 1>$null 2>$null
    if ($LASTEXITCODE -ne 0) { throw "No se pudo leer el estado del repo: $repoFull" }
    return $true
}

function New-InstallConfig {
    param(
        [Parameter(Mandatory = $true)][string]$InstallPath,
        [Parameter(Mandatory = $true)][string]$InstallerMode,
        [Parameter(Mandatory = $true)][System.Collections.IDictionary]$Providers,
        [Parameter(Mandatory = $true)][System.Collections.IDictionary]$Knowledge,
        [Parameter(Mandatory = $true)][System.Collections.IDictionary]$CredentialStore
    )
    $publicProviders = [ordered]@{}
    foreach ($pair in $Providers.GetEnumerator()) {
        $copy = [ordered]@{}
        foreach ($key in $pair.Value.Keys) {
            if ($key -eq "api_key") { continue }
            $copy[$key] = $pair.Value[$key]
        }
        $publicProviders[$pair.Key] = $copy
    }
    $selected = @($publicProviders.GetEnumerator() | Where-Object { $_.Value.enabled } | ForEach-Object { $_.Key })
    $defaultProvider = if ($selected.Count -gt 0) { $selected[0] } else { "ollama-local" }
    $defaultModel = switch ($defaultProvider) {
        "codex" { "gpt-5.4-mini" }
        "copilot" { "gpt-4o-copilot" }
        "ollama-cloud" { "llama3.2:3b" }
        default { "llama3.2:3b" }
    }
    return [ordered]@{
        schema_version = 1
        installer_mode = $InstallerMode
        install_dir = $InstallPath
        runtime = @{
            default_provider = $defaultProvider
            default_model = $defaultModel
            enabled_providers = $selected
        }
        providers = $publicProviders
        knowledge = $Knowledge
        credentials = $CredentialStore
    }
}

function Invoke-ProviderValidation {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$Providers)
    $ok = @{}
    foreach ($name in $Providers.Keys) {
        $cfg = $Providers[$name]
        if (-not $cfg.enabled) { continue }
        switch ($name) {
            "ollama-local" {
                $url = $cfg.base_url
                $tags = Invoke-RestMethod -Uri "$url/api/tags" -Method Get -TimeoutSec 10
                $models = @($tags.models | ForEach-Object { $_.name })
                if ($cfg.model -and ($models -notcontains $cfg.model)) { throw "Modelo local no disponible: $($cfg.model)" }
                $ok[$name] = [ordered]@{ ok = $true; models = $models.Count; detail = "ollama-local ok" }
            }
            "codex" {
                if (-not $cfg.api_key) { throw "OpenAI/Codex sin api key." }
                $headers = @{ Authorization = "Bearer $($cfg.api_key)" }
                $models = Invoke-RestMethod -Uri "https://api.openai.com/v1/models" -Headers $headers -Method Get -TimeoutSec 20
                $ok[$name] = [ordered]@{ ok = $true; models = @($models.data).Count; detail = "openai ok" }
            }
            "copilot" {
                if ($cfg.auth_mode -eq "device-flow") {
                    $gh = Get-Command gh.exe -ErrorAction SilentlyContinue
                    if (-not $gh) { throw "GitHub device-flow requiere gh CLI." }
                    & gh auth status -h github.com 1>$null 2>$null
                    if ($LASTEXITCODE -ne 0) { throw "gh auth status fallo para github.com." }
                    $token = (& gh auth token) | Select-Object -First 1
                    if (-not $token) { throw "gh auth token no devolvio token." }
                    $headers = @{ Authorization = "Bearer $token" }
                } elseif ($cfg.api_key) {
                    $headers = @{ Authorization = "Bearer $($cfg.api_key)" }
                } else {
                    throw "GitHub/Copilot sin token ni device-flow autenticado."
                }
                $resp = Invoke-RestMethod -Uri "https://api.githubcopilot.com/models" -Headers $headers -Method Get -TimeoutSec 20
                $ok[$name] = [ordered]@{ ok = $true; models = @($resp.data).Count; detail = "copilot ok" }
            }
            "ollama-cloud" {
                if (-not $cfg.base_url) { throw "Ollama Cloud sin base_url." }
                $headers = @{}
                if ($cfg.api_key) { $headers.Authorization = "Bearer $($cfg.api_key)" }
                $tags = Invoke-RestMethod -Uri "$($cfg.base_url)/api/tags" -Headers $headers -Method Get -TimeoutSec 20
                $ok[$name] = [ordered]@{ ok = $true; models = @($tags.models).Count; detail = "ollama-cloud ok" }
            }
        }
    }
    return $ok
}

function Invoke-FinalValidation {
    param(
        [Parameter(Mandatory = $true)][string]$InstallPath,
        [Parameter(Mandatory = $true)][System.Collections.IDictionary]$Providers,
        [Parameter(Mandatory = $true)][System.Collections.IDictionary]$Knowledge
    )
    $report = [ordered]@{}
    $report.destination = @{ ok = (Test-PathWritable $InstallPath); path = $InstallPath }
    $report.providers = Invoke-ProviderValidation -Providers $Providers
    $report.local_model = @{ ok = $true; detail = "no local provider selected" }
    if ($Providers.Contains("ollama-local") -and $Providers["ollama-local"].enabled) {
        $report.local_model = @{ ok = $true; detail = "ollama-local validated"; model = $Providers["ollama-local"].model }
    }
    $report.knowledge = @{ ok = $true; detail = "not shared" }
    if ($Knowledge.mode -eq "existing") {
        $report.knowledge = @{ ok = (Test-GitRepoAccess $Knowledge.path); detail = "existing repo accessible"; path = $Knowledge.path }
    } elseif ($Knowledge.mode -eq "new") {
        $repoPath = Get-FullPath $Knowledge.path
        New-Item -ItemType Directory -Path $repoPath -Force | Out-Null
        if ($Knowledge.git_init) {
            $git = Get-GitExe
            if (-not $git) { throw "git no disponible para crear repo nuevo." }
            & $git -C $repoPath init 1>$null 2>$null
            if ($LASTEXITCODE -ne 0) { throw "No se pudo inicializar el repo de conocimiento." }
        }
        $report.knowledge = @{ ok = $true; detail = "new repo ready"; path = $repoPath; visibility = $Knowledge.visibility }
    }
    foreach ($item in $report.providers.GetEnumerator()) {
        if (-not $item.Value.ok) { throw "Validacion de provider fallida: $($item.Key)" }
    }
    if (-not $report.destination.ok) { throw "No se puede escribir en el destino de instalacion." }
    if (-not $report.local_model.ok) { throw "La resolucion del modelo local fallo." }
    if (-not $report.knowledge.ok) { throw "El repositorio de conocimiento no es accesible." }
    return $report
}

$installFull = Assert-SafeTarget $InstallDir
$backupFull = Get-FullPath $BackupRoot
$userStateFull = Get-FullPath $UserStateDir
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$tempExtract = $null
$backupZip = $null
$pathScope = "skipped"

if ($PackageZip) {
    $zipFull = (Resolve-Path -LiteralPath $PackageZip).Path
    $tempExtract = Join-Path ([System.IO.Path]::GetTempPath()) "bago-v4-install-$stamp"
    New-Item -ItemType Directory -Path $tempExtract -Force | Out-Null
    Expand-Archive -LiteralPath $zipFull -DestinationPath $tempExtract -Force
    $SourceRoot = $tempExtract
}

if (-not $SourceRoot -and $profileName -eq "ign") {
    $SourceRoot = Get-ProfileInstallDir -ProfileName "des"
}

if (-not $SourceRoot) {
    $SourceRoot = $PSScriptRoot
}

$sourceFull = (Resolve-Path -LiteralPath $SourceRoot).Path
if ($sourceFull -eq $installFull -and -not $RepairOnly) {
    throw "SourceRoot and InstallDir cannot be the same path."
}

New-Item -ItemType Directory -Path $backupFull -Force | Out-Null
New-Item -ItemType Directory -Path $userStateFull -Force | Out-Null

$installerMode = $Mode
if ($installerMode -and $installerMode -notin @("Express", "Advanced")) {
    throw "Modo invalido: $installerMode"
}
if (-not $installerMode) {
    if ($RepairOnly) {
        $installerMode = "Express"
    } else {
        $installerMode = Read-Choice -Prompt "Modo de instalacion" -Options @("Express", "Advanced") -DefaultIndex 0
    }
}

$providerConfigs = [ordered]@{
    "ollama-local" = [ordered]@{ enabled = $false; base_url = "http://127.0.0.1:11434"; model = "llama3.2:3b" }
    "codex" = [ordered]@{ enabled = $false; base_url = "https://api.openai.com/v1"; api_key = ""; model = "gpt-5.4-mini" }
    "copilot" = [ordered]@{ enabled = $false; base_url = "https://api.githubcopilot.com"; api_key = ""; auth_mode = "device-flow"; model = "gpt-4o-copilot" }
    "ollama-cloud" = [ordered]@{ enabled = $false; base_url = ""; api_key = ""; auth_mode = "signin"; model = "llama3.2:3b" }
}
$knowledgeCfg = [ordered]@{ mode = "none"; path = ""; visibility = "private"; git_init = $false }
$credentialStoreCfg = [ordered]@{ mode = "session"; path = ""; encrypted = $false; scope = "session" }

if ($installerMode -eq "Express") {
    $providerConfigs["ollama-local"].enabled = $true
} else {
    $providerConfigs["ollama-local"].enabled = Read-YesNo -Prompt "Activar Ollama local" -Default $true
    if ($providerConfigs["ollama-local"].enabled) {
        $providerConfigs["ollama-local"].model = Read-InputOrDefault -Prompt "Modelo local por defecto (nombre del modelo en Ollama, por ejemplo llama3.2:3b)" -Default "llama3.2:3b"
    }
    $providerConfigs["codex"].enabled = Read-YesNo -Prompt "Activar OpenAI/Codex" -Default $false
    if ($providerConfigs["codex"].enabled) {
        $providerConfigs["codex"].api_key = Read-InputOrDefault -Prompt "API key de OpenAI (empieza por sk-... o usa la variable OPENAI_API_KEY)" -Default $env:OPENAI_API_KEY
        $providerConfigs["codex"].model = Read-InputOrDefault -Prompt "Modelo OpenAI por defecto (por ejemplo gpt-5.4-mini)" -Default "gpt-5.4-mini"
    }
    $providerConfigs["copilot"].enabled = Read-YesNo -Prompt "Activar GitHub/Copilot" -Default $false
    if ($providerConfigs["copilot"].enabled) {
        Write-Host "Autenticacion GitHub:"
        Write-Host "  device-flow = login interactivo con navegador"
        Write-Host "  pat         = token manual pegado por el usuario"
        $providerConfigs["copilot"].auth_mode = Read-Choice -Prompt "Autenticacion GitHub (device-flow abre gh auth login; pat pide token)" -Options @("device-flow", "pat") -DefaultIndex 0
        if ($providerConfigs["copilot"].auth_mode -eq "pat") {
            $providerConfigs["copilot"].api_key = Read-InputOrDefault -Prompt "PAT de GitHub (token personal, o usa GITHUB_TOKEN)" -Default $env:GITHUB_TOKEN
        } else {
            Invoke-GhDeviceLogin
        }
        $providerConfigs["copilot"].model = Read-InputOrDefault -Prompt "Modelo Copilot por defecto (por ejemplo gpt-4o-copilot)" -Default "gpt-4o-copilot"
    }
    $providerConfigs["ollama-cloud"].enabled = Read-YesNo -Prompt "Activar Ollama Cloud" -Default $false
    if ($providerConfigs["ollama-cloud"].enabled) {
        Write-Host "Autenticacion Ollama Cloud:"
        Write-Host "  signin  = login interactivo con navegador"
        Write-Host "  api_key = token manual pegado por el usuario"
        $providerConfigs["ollama-cloud"].auth_mode = Read-Choice -Prompt "Autenticacion Ollama Cloud (signin abre navegador; api_key pide clave)" -Options @("signin", "api_key") -DefaultIndex 0
        $providerConfigs["ollama-cloud"].base_url = Read-UrlOrDefault -Prompt "URL base de Ollama Cloud (solo URL, por ejemplo https://cloud.example.com)" -Default $env:OLLAMA_CLOUD_URL
        if ([string]::IsNullOrWhiteSpace($providerConfigs["ollama-cloud"].base_url)) {
            throw "Ollama Cloud requiere una URL base valida."
        }
        if ($providerConfigs["ollama-cloud"].auth_mode -eq "signin") {
            Invoke-OllamaCloudSignin -BaseUrl $providerConfigs["ollama-cloud"].base_url
        }
        if ($providerConfigs["ollama-cloud"].auth_mode -eq "api_key") {
            $providerConfigs["ollama-cloud"].api_key = Read-InputOrDefault -Prompt "API key de Ollama Cloud (o usa OLLAMA_CLOUD_KEY)" -Default $env:OLLAMA_CLOUD_KEY
        }
    }
    $knowledgeCfg.mode = Read-Choice -Prompt "Repositorio de conocimiento" -Options @("none", "existing", "new") -DefaultIndex 0
    if ($knowledgeCfg.mode -eq "existing") {
        $knowledgeCfg.path = Read-InputOrDefault -Prompt "Ruta del repo existente" -Default (Join-Path $env:USERPROFILE "Documents\bago-knowledge")
        $knowledgeCfg.visibility = Read-Choice -Prompt "Visibilidad del repo" -Options @("private", "public") -DefaultIndex 0
    } elseif ($knowledgeCfg.mode -eq "new") {
        $knowledgeCfg.path = Read-InputOrDefault -Prompt "Ruta para crear el repo" -Default (Join-Path $env:USERPROFILE "Documents\bago-knowledge")
        $knowledgeCfg.visibility = Read-Choice -Prompt "Visibilidad del repo nuevo" -Options @("private", "public") -DefaultIndex 0
        $knowledgeCfg.git_init = $true
    }
    $credentialStoreCfg.mode = Read-Choice -Prompt "Persistencia de credenciales" -Options @("session", "persistent", "external") -DefaultIndex 0
    if ($credentialStoreCfg.mode -eq "persistent") {
        $credentialStoreCfg.path = Join-Path $userStateFull "secrets\bago-credentials.dpapi"
        $credentialStoreCfg.encrypted = $true
        $credentialStoreCfg.scope = "CurrentUser"
    } elseif ($credentialStoreCfg.mode -eq "external") {
        $credentialStoreCfg.path = Read-InputOrDefault -Prompt "Ruta de exportacion cifrada" -Default (Join-Path $userStateFull "exports\bago-credentials.dpapi")
        $credentialStoreCfg.encrypted = $true
        $credentialStoreCfg.scope = "CurrentUser"
    }
}

$secretStorePayload = [ordered]@{}
if ($providerConfigs["codex"].enabled -and $providerConfigs["codex"].api_key) {
    $secretStorePayload["codex"] = @{ OPENAI_API_KEY = $providerConfigs["codex"].api_key }
}
if ($providerConfigs["copilot"].enabled -and $providerConfigs["copilot"].api_key) {
    $secretStorePayload["copilot"] = @{ GITHUB_TOKEN = $providerConfigs["copilot"].api_key }
}
if ($providerConfigs["ollama-cloud"].enabled -and $providerConfigs["ollama-cloud"].api_key) {
    $secretStorePayload["ollama-cloud"] = @{ OLLAMA_CLOUD_KEY = $providerConfigs["ollama-cloud"].api_key }
}

$installConfig = New-InstallConfig -InstallPath $installFull -InstallerMode $installerMode -Providers $providerConfigs -Knowledge $knowledgeCfg -CredentialStore $credentialStoreCfg
$runtimeConfig = [ordered]@{
    default_provider = $installConfig.runtime.default_provider
    default_model = $installConfig.runtime.default_model
    providers = [ordered]@{}
}
foreach ($name in $providerConfigs.Keys) {
    $runtimeConfig.providers[$name] = [ordered]@{ enabled = [bool]$providerConfigs[$name].enabled }
    foreach ($key in $providerConfigs[$name].Keys) {
        if ($key -eq "enabled" -or $key -eq "api_key") { continue }
        $runtimeConfig.providers[$name][$key] = $providerConfigs[$name][$key]
    }
}

if (-not $RepairOnly) {
    if (Test-Path -LiteralPath $installFull) {
        $backupZip = Join-Path $backupFull "bago-programfiles-backup-$stamp.zip"
        $children = @(Get-ChildItem -LiteralPath $installFull -Force)
        if ($children.Count -gt 0) {
            Compress-Archive -Path (Join-Path $installFull "*") -DestinationPath $backupZip -CompressionLevel Optimal -Force
        } else {
            $backupZip = $null
        }
    } else {
        New-Item -ItemType Directory -Path $installFull -Force | Out-Null
    }

    $preserveTemp = Join-Path ([System.IO.Path]::GetTempPath()) "bago-v4-preserve-$stamp"
    New-Item -ItemType Directory -Path $preserveTemp -Force | Out-Null
    $preserved = Move-PreservedRuntimeState -InstallPath $installFull -PreservePath $preserveTemp

    Get-ChildItem -LiteralPath $installFull -Force | ForEach-Object {
        try {
            Remove-Item -LiteralPath $_ -Recurse -Force -ErrorAction Stop
        } catch {
            Write-Warning "No se pudo limpiar $($_): $($_.Exception.Message)"
        }
    }

    Copy-ReleaseTree -Source $sourceFull -Destination $installFull
    Restore-PreservedRuntimeState -InstallPath $installFull -PreservePath $preserveTemp
} else {
    if (-not (Test-Path -LiteralPath $installFull)) {
        throw "RepairOnly requires an installed runtime at $installFull"
    }
    $preserved = @()
}

$installConfigPath = Join-Path $installFull "install_config.json"
$runtimeConfigPath = Join-Path $installFull ".bago\config.json"
Write-JsonFile -Path $installConfigPath -Value $installConfig
Write-JsonFile -Path $runtimeConfigPath -Value $runtimeConfig
if ($credentialStoreCfg.mode -ne "session") {
    if (-not $credentialStoreCfg.path) { throw "La persistencia elegida requiere una ruta de almacenamiento." }
    Write-EncryptedStore -Path $credentialStoreCfg.path -Payload $secretStorePayload
}

$validation = Invoke-FinalValidation -InstallPath $installFull -Providers $providerConfigs -Knowledge $knowledgeCfg
Write-Host "Validacion final:"
Write-Host ("  destination: {0}" -f $(if ($validation.destination.ok) { "ok" } else { "fail" }))
foreach ($name in $validation.providers.Keys) {
    $state = if ($validation.providers[$name].ok) { "ok" } else { "fail" }
    Write-Host ("  provider[{0}]: {1}" -f $name, $state)
}
Write-Host ("  knowledge: {0}" -f $(if ($validation.knowledge.ok) { "ok" } else { "fail" }))

if (-not $NoPathUpdate) {
    $pathScope = Enable-BagoCommandPath -InstallPath $installFull
}

if ($RepairOnly) {
    # Repair-only updates the runtime config in place. Some managed installs
    # keep only runtime state and do not ship the full source tree needed by
    # the post-install tests, so do not fail repair on that missing payload.
    $SkipTests = $true
}

if (-not $SkipTests) {
    Push-Location $installFull
    try {
        & python "bago_core\launcher.py" "--test"
        if ($LASTEXITCODE -ne 0) { throw "launcher.py --test failed with exit code $LASTEXITCODE" }
        & python "test_security_release.py"
        if ($LASTEXITCODE -ne 0) { throw "test_security_release.py failed with exit code $LASTEXITCODE" }
    } finally {
        Pop-Location
    }
}

$result = [ordered]@{
    ok = $true
    profile = $profileName
    installed_to = $installFull
    source = $sourceFull
    backup_zip = $backupZip
    preserved_runtime_state = $preserved
    user_state_dir = $userStateFull
    path_scope = $pathScope
    command_path = (Join-Path $installFull "bago.cmd")
    repair_only = [bool]$RepairOnly
    timestamp = $stamp
}

$result | ConvertTo-Json -Depth 4
