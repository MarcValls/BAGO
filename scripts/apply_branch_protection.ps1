#!/usr/bin/env pwsh
param(
    [string]$Owner = "MarcValls",
    [string]$Repo = "BAGO"
)

$ErrorActionPreference = "Stop"

function Set-BranchProtection {
    param(
        [string]$Branch
    )

    $payload = @{
        required_status_checks           = @{
            strict   = $true
            contexts = @("Branch Flow Guard / branch-flow-guard")
        }
        enforce_admins                   = $true
        required_pull_request_reviews    = @{
            dismiss_stale_reviews           = $true
            require_code_owner_reviews      = $false
            required_approving_review_count = 0
            require_last_push_approval      = $false
        }
        restrictions                     = $null
        required_linear_history          = $true
        allow_force_pushes               = $false
        allow_deletions                  = $false
        block_creations                  = $true
        required_conversation_resolution = $true
        lock_branch                      = $false
        allow_fork_syncing               = $false
    } | ConvertTo-Json -Depth 10 -Compress

    $endpoint = "repos/$Owner/$Repo/branches/$Branch/protection"
    Write-Output "Aplicando protección a $Branch..."
    $null = $payload | gh api -X PUT $endpoint --input -
}

foreach ($branch in @("main", "windows", "android")) {
    Set-BranchProtection -Branch $branch
}

Write-Output "Protección aplicada en main/windows/android."
