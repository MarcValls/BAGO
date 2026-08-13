#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet("Install", "Uninstall")][string]$Action,
    [Parameter(Mandatory = $true)][string]$InstallPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$installFull = [System.IO.Path]::GetFullPath($InstallPath).TrimEnd("\")

function Normalize-PathEntry {
    param([string]$Value)
    return $Value.Trim().TrimEnd("\").ToLowerInvariant()
}

function Update-MachinePath {
    param([bool]$Add)
    $current = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $entries = New-Object System.Collections.Generic.List[string]
    foreach ($entry in @($current -split ";")) {
        $clean = $entry.Trim()
        if (-not $clean) { continue }
        if ((Normalize-PathEntry $clean) -eq (Normalize-PathEntry $installFull)) { continue }
        $entries.Add($clean)
    }
    if ($Add) { $entries.Insert(0, $installFull) }
    [Environment]::SetEnvironmentVariable("Path", ($entries -join ";"), "Machine")
}

function Remove-ManagedProfileBlocks {
    $documents = [Environment]::GetFolderPath("MyDocuments")
    if (-not $documents) { return }
    $profiles = @(
        (Join-Path $documents "WindowsPowerShell\Microsoft.PowerShell_profile.ps1"),
        (Join-Path $documents "PowerShell\Microsoft.PowerShell_profile.ps1")
    )
    $pattern = '(?s)\s*# BEGIN BAGO MANAGED BLOCK.*?# END BAGO MANAGED BLOCK\s*'
    foreach ($profile in $profiles) {
        if (-not (Test-Path -LiteralPath $profile)) { continue }
        $content = Get-Content -LiteralPath $profile -Raw
        $updated = [regex]::Replace($content, $pattern, "`r`n").Trim()
        Set-Content -LiteralPath $profile -Value $(if ($updated) { $updated + "`r`n" } else { "" }) -Encoding UTF8
    }
}

function Remove-InstalledRoles {
    if (-not $env:LOCALAPPDATA) { return }
    $selectionPath = Join-Path $env:LOCALAPPDATA "BAGO\install_selection.json"
    if (-not (Test-Path -LiteralPath $selectionPath)) { return }
    try {
        $selection = Get-Content -LiteralPath $selectionPath -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($name in @("active", "launch")) {
            $role = $selection.roles.PSObject.Properties[$name]
            if ($role -and (Normalize-PathEntry ([string]$role.Value.path)) -eq (Normalize-PathEntry $installFull)) {
                $selection.roles.PSObject.Properties.Remove($name)
            }
        }
        $selection.updated_at = (Get-Date).ToUniversalTime().ToString("o")
        $json = $selection | ConvertTo-Json -Depth 8
        [System.IO.File]::WriteAllText($selectionPath, $json + "`n", [System.Text.UTF8Encoding]::new($false))
    } catch {
        Write-Warning "No se pudo actualizar install_selection.json: $($_.Exception.Message)"
    }
}

if ($Action -eq "Install") {
    Update-MachinePath -Add $true
} else {
    Update-MachinePath -Add $false
    Remove-ManagedProfileBlocks
    Remove-InstalledRoles
}

[ordered]@{ ok = $true; action = $Action; install_path = $installFull } | ConvertTo-Json -Compress
