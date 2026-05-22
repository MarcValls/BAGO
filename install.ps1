#!/usr/bin/env pwsh
# BAGO clean installer for Windows
# Installs the framework to C:\Program Files\BAGO and places mutable user
# state outside Program Files at %ProgramData%\BAGO\user.

param(
    [switch]$NoKnowledge,
    [string]$TargetRoot = "",
    [switch]$NoPathUpdate
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$env:PYTHONDONTWRITEBYTECODE = "1"

$sourceRoot = (Resolve-Path $PSScriptRoot).Path
$customTarget = -not [string]::IsNullOrWhiteSpace($TargetRoot)
$installRoot = if ($customTarget) {
    [System.IO.Path]::GetFullPath($TargetRoot)
} else {
    Join-Path $env:ProgramFiles "BAGO"
}
$programDataRoot = Join-Path $env:ProgramData "BAGO"
$userHome = Join-Path $programDataRoot "user"

function New-DefaultRuntimeContract {
    [pscustomobject]@{
        schema = 1
        contract_id = "bago.runtime.clean-install"
        version = "1.0.0"
        root = [pscustomobject]@{
            keep = @(
                ".bago",
                "bago.cmd",
                "bago.ps1",
                "bago.ico",
                "bago_core",
                "LICENSE",
                "README.md",
                "INSTALL.md",
                "CHANGELOG.md",
                "QUICKSTART.md",
                "install.ps1",
                "smoke-test.ps1",
                "runtime_contract.json"
            )
        }
        state = [pscustomobject]@{
            keep_dirs = @("sessions", "changes", "evidences", "reports", "config")
            reset_dirs = @("reports", "sac_locks")
            prune_file_patterns = @(
                "*.jsonl",
                "*.db",
                "contribution_*.md",
                "install_complete.json",
                "benchmark_last.json",
                "experimental_command_test_results.json",
                "scan_history.json",
                "recent_projects.json",
                "neural_token.txt",
                "path_healer_memory.json",
                "orphan_baseline.json",
                "self_state.json",
                "canon_log.json",
                "conductor_state.json",
                "goal_validation_*.json"
            )
        }
    }
}

function Load-RuntimeContract {
    $contractPath = Join-Path $sourceRoot "docs\runtime_contract.json"
    if (Test-Path $contractPath) {
        try {
            return Get-Content -LiteralPath $contractPath -Raw | ConvertFrom-Json
        } catch {
            Write-Host "WARN: no se pudo leer el runtime contract, usando fallback embebido." -ForegroundColor Yellow
        }
    }
    return New-DefaultRuntimeContract
}

function Get-RuntimeContractVersion {
    param([Parameter(Mandatory = $true)]$Contract)

    foreach ($name in @("contract_version", "version")) {
        if ($Contract.PSObject.Properties.Name -contains $name) {
            return $Contract.$name
        }
    }

    return $null
}
$script:RuntimeContract = Load-RuntimeContract

function Assert-ExactTarget {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Expected
    )

    $resolved = [System.IO.Path]::GetFullPath($Path)
    $expectedResolved = [System.IO.Path]::GetFullPath($Expected)
    if (-not $resolved.Equals($expectedResolved, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Target path mismatch: $resolved (expected $expectedResolved)"
    }
}

function Assert-InstallTarget {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][bool]$IsCustom
    )

    if (-not $IsCustom) {
        Assert-ExactTarget -Path $Path -Expected (Join-Path $env:ProgramFiles "BAGO")
        return
    }

    $resolved = [System.IO.Path]::GetFullPath($Path).TrimEnd("\")
    $sourceResolved = [System.IO.Path]::GetFullPath($sourceRoot).TrimEnd("\")
    $root = [System.IO.Path]::GetPathRoot($resolved).TrimEnd("\")
    $leaf = Split-Path -Leaf $resolved

    if (-not [System.IO.Path]::IsPathRooted($resolved)) {
        throw "TargetRoot debe ser una ruta absoluta: $Path"
    }
    if ($resolved.Equals($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "TargetRoot no puede ser la raiz de una unidad: $resolved"
    }
    if ($resolved.Equals($sourceResolved, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "TargetRoot no puede ser el repo fuente: $resolved"
    }
    if ($leaf -notin @("BAGO", "bago_fw")) {
        throw "TargetRoot custom debe terminar en BAGO o bago_fw para evitar borrados ambiguos: $resolved"
    }
}

function Backup-ExistingTarget {
    param([Parameter(Mandatory = $true)][string]$Root)

    $resolved = [System.IO.Path]::GetFullPath($Root).TrimEnd("\")
    $parent = Split-Path -Parent $resolved
    $leaf = Split-Path -Leaf $resolved
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backup = Join-Path $parent "$leaf.backup.$stamp"
    if (Test-Path $backup) {
        $backup = Join-Path $parent "$leaf.backup.$stamp.$PID"
    }
    Move-Item -LiteralPath $resolved -Destination $backup
    return $backup
}

function Invoke-PythonScript {
    param(
        [Parameter(Mandatory = $true)][string]$ScriptPath,
        [string[]]$Args = @(),
        [string]$WorkingDirectory = $null
    )

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        if ($WorkingDirectory) { Push-Location $WorkingDirectory }
        try {
            $null = & $python.Source $ScriptPath @Args
            return $LASTEXITCODE
        } finally {
            if ($WorkingDirectory) { Pop-Location }
        }
    }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        if ($WorkingDirectory) { Push-Location $WorkingDirectory }
        try {
            $null = & py -3 $ScriptPath @Args
            return $LASTEXITCODE
        } finally {
            if ($WorkingDirectory) { Pop-Location }
        }
    }

    throw "Python no encontrado en PATH"
}

function Update-UserPath {
    param([Parameter(Mandatory = $true)][string]$Entry)

    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if ($current) {
        $parts = $current.Split(";") | Where-Object { $_ -and $_.Trim() }
    }
    $sourcePath = $sourceRoot
    $parts = @($Entry) + @(
        $parts | Where-Object {
            (-not $_.Equals($Entry, [System.StringComparison]::OrdinalIgnoreCase)) -and
            (-not $_.Equals($sourcePath, [System.StringComparison]::OrdinalIgnoreCase))
        }
    )
    [Environment]::SetEnvironmentVariable("Path", ($parts -join ";"), "User")

    $sessionParts = @()
    if ($env:Path) {
        $sessionParts = $env:Path.Split(";") | Where-Object { $_ -and $_.Trim() }
    }
    $sessionParts = @($Entry) + @(
        $sessionParts | Where-Object {
            (-not $_.Equals($Entry, [System.StringComparison]::OrdinalIgnoreCase)) -and
            (-not $_.Equals($sourcePath, [System.StringComparison]::OrdinalIgnoreCase))
        }
    )
    $env:Path = $sessionParts -join ";"
}

function Remove-RuntimeState {
    param([Parameter(Mandatory = $true)][string]$Root)

    if (-not (Test-Path $Root)) {
        return
    }

    $stateContract = $script:RuntimeContract.state
    $resetDirs = @($stateContract.reset_dirs)
    if (-not $resetDirs -or $resetDirs.Count -eq 0) {
        $resetDirs = @("reports", "sac_locks")
    }
    $dirPaths = $resetDirs | ForEach-Object { Join-Path $Root $_ }
    foreach ($dir in $dirPaths) {
        if (Test-Path $dir) {
            Remove-Item -LiteralPath $dir -Recurse -Force
        }
    }

    $filePatterns = @($stateContract.prune_file_patterns)
    if (-not $filePatterns -or $filePatterns.Count -eq 0) {
        $filePatterns = @(
            "*.jsonl",
            "*.db",
            "contribution_*.md",
            "install_complete.json",
            "benchmark_last.json",
            "experimental_command_test_results.json",
            "scan_history.json",
            "recent_projects.json",
            "neural_token.txt",
            "path_healer_memory.json",
            "orphan_baseline.json",
            "self_state.json",
            "canon_log.json",
            "conductor_state.json",
            "goal_validation_*.json"
        )
    }

    foreach ($pattern in $filePatterns) {
        Get-ChildItem -Path $Root -Recurse -File -Filter $pattern -ErrorAction SilentlyContinue |
            Remove-Item -Force -ErrorAction SilentlyContinue
    }

    $toolboxRoot = Join-Path $Root "toolboxes"
    if (Test-Path $toolboxRoot) {
        Get-ChildItem -Path $toolboxRoot -Recurse -File -Filter "*-sprint-test.json" -ErrorAction SilentlyContinue |
            Remove-Item -Force -ErrorAction SilentlyContinue
    }

    $contractsRoot = Join-Path $Root "contracts"
    if (Test-Path $contractsRoot) {
        Get-ChildItem -Path $contractsRoot -Recurse -File -Filter "*_report.json" -ErrorAction SilentlyContinue |
            Remove-Item -Force -ErrorAction SilentlyContinue
    }
}

function Remove-KnowledgeTree {
    param([Parameter(Mandatory = $true)][string]$Root)

    if (-not (Test-Path $Root)) {
        return @()
    }

    Remove-Item -LiteralPath $Root -Recurse -Force
    return @(".bago\knowledge")
}

function Prune-RuntimeTree {
    param([Parameter(Mandatory = $true)][string]$RuntimeRoot)

    if (-not (Test-Path $RuntimeRoot)) {
        return @()
    }

    $treeContract = $script:RuntimeContract.tree
    $keep = @($treeContract.keep)
    if (-not $keep -or $keep.Count -eq 0) {
        $keep = @(
            ".llama",
            ".models",
            "agents",
            "assets",
            "bin",
            "config",
            "core",
            "extensions",
            "knowledge",
            "manifests",
            "mcp",
            "prompts",
            "roles",
            "state",
            "supervision",
            "templates",
            "tools",
            "workflows",
            "pack.json",
            "tools.manifest.json",
            "AGENT_START.md",
            "BOOTSTRAP.md",
            "TREE.txt",
            "CHECKSUMS.sha256"
        )
    }

    $removed = @()
    Get-ChildItem -LiteralPath $RuntimeRoot -Force | ForEach-Object {
        if ($keep -notcontains $_.Name) {
            $removed += (".bago\" + $_.Name)
            Remove-Item -LiteralPath $_.FullName -Recurse -Force
        }
    }
    return $removed
}

function Remove-GeneratedCaches {
    param([Parameter(Mandatory = $true)][string]$Root)

    if (-not (Test-Path $Root)) {
        return @()
    }

    $removed = @()
    foreach ($cacheName in @("__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache")) {
        Get-ChildItem -LiteralPath $Root -Recurse -Force -Directory -Filter $cacheName -ErrorAction SilentlyContinue |
            ForEach-Object {
                $removed += $_.FullName.Replace($Root.TrimEnd("\") + "\", "")
                Remove-Item -LiteralPath $_.FullName -Recurse -Force
            }
    }
    return $removed
}

function Prune-DevelopmentResidue {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [string[]]$KnowledgePruned = @()
    )

    $rootContract = $script:RuntimeContract.root
    $keep = @($rootContract.keep)
    if (-not $keep -or $keep.Count -eq 0) {
        $keep = @(
            ".bago",
            "bago.cmd",
            "bago.ps1",
            "bago.ico",
            "bago_core",
            "LICENSE",
            "README.md",
            "INSTALL.md",
            "CHANGELOG.md",
            "QUICKSTART.md",
            "install.ps1",
            "smoke-test.ps1",
            "runtime_contract.json"
        )
    }
    if ($keep -notcontains "runtime_contract.json") {
        $keep += "runtime_contract.json"
    }

    $removed = @()
    Get-ChildItem -LiteralPath $Root -Force | ForEach-Object {
        if ($keep -notcontains $_.Name) {
            $removed += $_.Name
            Remove-Item -LiteralPath $_.FullName -Recurse -Force
        }
    }

    $runtimeRemoved = Prune-RuntimeTree -RuntimeRoot (Join-Path $Root ".bago")

    $manifest = [ordered]@{
        contract_id = $script:RuntimeContract.contract_id
        contract_version = Get-RuntimeContractVersion -Contract $script:RuntimeContract
        install_root = $Root
        runtime_root = (Join-Path $Root ".bago")
        user_home = $userHome
        custom_target = $customTarget
        path_updated = (-not $NoPathUpdate)
        backup_of_existing_target = $backupPath
        knowledge_included = (-not $NoKnowledge)
        install_profile = if ($NoKnowledge) { "without-knowledge" } else { "with-knowledge" }
        publication = $script:RuntimeContract.publication
        root = $script:RuntimeContract.root
        tree = $script:RuntimeContract.tree
        state = $script:RuntimeContract.state
        policy = $script:RuntimeContract.policy
        knowledge = $script:RuntimeContract.knowledge
        kept = $keep
        pruned = @($removed + $runtimeRemoved + $KnowledgePruned) | Sort-Object
        contract_source = (Join-Path $sourceRoot "docs\runtime_contract.json")
        contract_source_sha256 = if (Test-Path (Join-Path $sourceRoot "docs\runtime_contract.json")) {
            (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $sourceRoot "docs\runtime_contract.json")).Hash
        } else {
            $null
        }
        generated_at = (Get-Date).ToString("o")
    }
    $manifestPath = Join-Path $Root "runtime_contract.json"
    $json = $manifest | ConvertTo-Json -Depth 10
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($manifestPath, $json, $utf8NoBom)
}

Assert-InstallTarget -Path $installRoot -IsCustom $customTarget

$backupPath = $null
if (Test-Path $installRoot) {
    if ($customTarget) {
        $backupPath = Backup-ExistingTarget -Root $installRoot
    } else {
        Remove-Item -LiteralPath $installRoot -Recurse -Force
    }
}
New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
New-Item -ItemType Directory -Path $programDataRoot -Force | Out-Null
New-Item -ItemType Directory -Path $userHome -Force | Out-Null

$excludeDirs = @(
    ".git",
    ".github",
    ".githooks",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".tox",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "bago.egg-info"
)

$excludeFiles = @(
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.log",
    "*.out",
    "*.err",
    "tmp_*"
)

$robocopyArgs = @(
    $sourceRoot,
    $installRoot,
    "/MIR",
    "/R:1",
    "/W:1",
    "/NFL",
    "/NDL",
    "/NJH",
    "/NJS",
    "/NP",
    "/XD"
) + $excludeDirs + @("/XF") + $excludeFiles

& robocopy @robocopyArgs | Out-Null
if ($LASTEXITCODE -ge 8) {
    throw "robocopy fallo con codigo $LASTEXITCODE"
}

$knowledgePruned = @()
if ($NoKnowledge) {
    $knowledgePruned = Remove-KnowledgeTree -Root (Join-Path $installRoot ".bago\knowledge")
}

$null = Prune-DevelopmentResidue -Root $installRoot -KnowledgePruned $knowledgePruned

$internalUserHome = Join-Path $installRoot ".bago\user"
if (Test-Path $internalUserHome) {
    Remove-Item -LiteralPath $internalUserHome -Recurse -Force
}

Remove-RuntimeState -Root (Join-Path $installRoot ".bago\state")

$env:BAGO_USER_HOME = $userHome
[Environment]::SetEnvironmentVariable("BAGO_USER_HOME", $userHome, "User")
if (-not $NoPathUpdate) {
    Update-UserPath -Entry $installRoot
}

$bootstrap = Join-Path $installRoot ".bago\tools\bootstrap_state.py"
if (-not (Test-Path $bootstrap)) {
    throw "No se encontro bootstrap_state.py en $bootstrap"
}

$wizard = Join-Path $installRoot ".bago\tools\bago_wizard.py"
if (-not (Test-Path $wizard)) {
    throw "No se encontro bago_wizard.py en $wizard"
}

if ((Invoke-PythonScript -ScriptPath $bootstrap -Args @($installRoot) -WorkingDirectory $installRoot) -ne 0) {
    throw "bootstrap_state.py fallo"
}

$dbInit = Join-Path $installRoot ".bago\tools\bago_db.py"
if (Test-Path $dbInit) {
    if ((Invoke-PythonScript -ScriptPath $dbInit -Args @("init") -WorkingDirectory $installRoot) -ne 0) {
        throw "bago_db.py init fallo"
    }
}

$oldCI = $env:CI
$oldSkipWizard = $env:BAGO_SKIP_WIZARD
$env:CI = "1"
$env:BAGO_SKIP_WIZARD = "1"
try {
    if ((Invoke-PythonScript -ScriptPath $wizard -WorkingDirectory $installRoot) -ne 0) {
        throw "bago_wizard.py fallo"
    }
} finally {
    if ($null -ne $oldCI) {
        $env:CI = $oldCI
    } else {
        Remove-Item Env:\CI -ErrorAction SilentlyContinue
    }
    if ($null -ne $oldSkipWizard) {
        $env:BAGO_SKIP_WIZARD = $oldSkipWizard
    } else {
        Remove-Item Env:\BAGO_SKIP_WIZARD -ErrorAction SilentlyContinue
    }
}

$generatedResidue = Remove-GeneratedCaches -Root $installRoot
$null = Prune-DevelopmentResidue -Root $installRoot -KnowledgePruned @($knowledgePruned + $generatedResidue)

$launcher = Join-Path $installRoot "bago.cmd"
if (-not (Test-Path $launcher)) {
    throw "No se encontro bago.cmd en $launcher"
}

Write-Host ""
Write-Host "BAGO instalado limpiamente en $installRoot" -ForegroundColor Green
Write-Host "BAGO_USER_HOME: $userHome" -ForegroundColor Cyan
if ($backupPath) {
    Write-Host "Backup destino anterior: $backupPath" -ForegroundColor Yellow
}
if ($NoPathUpdate) {
    Write-Host "PATH usuario no modificado (-NoPathUpdate)" -ForegroundColor Yellow
} else {
    Write-Host "PATH usuario actualizado con $installRoot" -ForegroundColor Cyan
}
Write-Host "Verificacion sugerida: & `"$launcher`" validate" -ForegroundColor Yellow


