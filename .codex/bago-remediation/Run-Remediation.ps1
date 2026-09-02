param(
    [string]$RepoRoot = ".",
    [string]$RunId = (Get-Date -Format "yyyyMMdd-HHmmss"),
    [string]$StartAt = "F01",
    [switch]$NoMerge,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$PlanPath = Join-Path $Here "remediation-plan.json"
$Workpack = Join-Path (Split-Path -Parent $Here) "bago-workpack\Run.ps1"

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' is not available in PATH."
    }
}

function Invoke-Checked([scriptblock]$Command, [string]$What) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$What failed with exit code $LASTEXITCODE" }
}

Require-Command git
Require-Command codex
Require-Command gh

$Repo = (Resolve-Path $RepoRoot).Path
if (-not (Test-Path (Join-Path $Repo ".git"))) { throw "RepoRoot is not a Git repository: $Repo" }
if (-not (Test-Path $PlanPath)) { throw "Missing remediation plan: $PlanPath" }
if (-not (Test-Path $Workpack)) { throw "Missing BAGO workpack runner: $Workpack" }

$Plan = Get-Content $PlanPath -Raw | ConvertFrom-Json

Push-Location $Repo
try {
    Invoke-Checked { git fetch origin --prune } "git fetch"
    $status = (git status --porcelain=v1 | Out-String).Trim()
    if ($status) { throw "Base worktree must be clean before orchestration. Commit/stash changes first." }

    $startIndex = 0
    for ($i = 0; $i -lt $Plan.fronts.Count; $i++) {
        if ($Plan.fronts[$i].id -eq $StartAt) { $startIndex = $i; break }
    }

    $RunRoot = Join-Path $Here ("runs\" + $RunId)
    New-Item -ItemType Directory -Force -Path $RunRoot | Out-Null
    $LedgerPath = Join-Path $RunRoot "ledger.jsonl"

    function Write-Ledger($front, [string]$state, [string]$detail) {
        $entry = [ordered]@{
            timestamp = (Get-Date).ToUniversalTime().ToString("o")
            run_id = $RunId
            front = $front.id
            priority = $front.priority
            state = $state
            detail = $detail
        }
        ($entry | ConvertTo-Json -Compress) | Add-Content -Path $LedgerPath -Encoding utf8
    }

    for ($i = $startIndex; $i -lt $Plan.fronts.Count; $i++) {
        $front = $Plan.fronts[$i]
        $slug = ($front.title.ToLowerInvariant() -replace '[^a-z0-9]+','-').Trim('-')
        if ($slug.Length -gt 42) { $slug = $slug.Substring(0,42).Trim('-') }
        $branch = "remediation/$($front.id.ToLowerInvariant())-$slug"
        $worktree = Join-Path $RunRoot $front.id

        Write-Host ""
        Write-Host "============================================================"
        Write-Host "$($front.id) [$($front.priority)] $($front.title)"
        Write-Host "============================================================"
        Write-Ledger $front "PREPARED" "starting front"

        Invoke-Checked { git fetch origin $($Plan.base_branch) } "fetch base"
        $baseSha = (git rev-parse "origin/$($Plan.base_branch)").Trim()

        if (Test-Path $worktree) {
            Invoke-Checked { git worktree remove --force $worktree } "remove stale worktree"
        }
        git branch -D $branch 2>$null | Out-Null
        Invoke-Checked { git worktree add -b $branch $worktree $baseSha } "create worktree"

        $acceptance = ($front.acceptance | ForEach-Object { "- $_" }) -join "`n"
        $extra = @"
APPROVED_REMEDIATION_FRONT
ID: $($front.id)
Priority: $($front.priority)
Title: $($front.title)
Objective: $($front.objective)

Acceptance criteria:
$acceptance

Execution rules:
- Inspect current code before editing; do not implement from remembered repository state.
- Make the smallest coherent production change that satisfies this front.
- Preserve BAGO authority boundaries and BAGOx overlay rules.
- Add or update falsification/regression tests for each material invariant.
- Run the repository-defined relevant checks before declaring execution complete.
- Do not self-certify. Leave the result EXECUTED; independent verification follows.
- If the front is too broad for one safe PR, implement the smallest dependency-safe slice that makes measurable progress and explicitly return BLOCKED with the remaining decomposition instead of claiming success.
"@

        if ($DryRun) {
            Write-Host "DRY RUN: would invoke implementation and verifier for $($front.id) on $branch"
            Write-Ledger $front "DRY_RUN" "no mutation executed"
            Invoke-Checked { git worktree remove --force $worktree } "remove dry-run worktree"
            continue
        }

        try {
            & $Workpack -Task "20-implement-approved-pr" -RepoRoot $worktree -RunId "$RunId-$($front.id)-impl" -Extra $extra
            if ($LASTEXITCODE -ne 0) { throw "implementation agent failed" }

            Push-Location $worktree
            try {
                $changed = (git status --porcelain=v1 | Out-String).Trim()
                if (-not $changed) { throw "implementation produced no repository changes" }
                Invoke-Checked { git add -A } "git add"
                Invoke-Checked { git commit -m "fix($($front.id.ToLowerInvariant())): $($front.title)" } "git commit"
                $candidateSha = (git rev-parse HEAD).Trim()
            }
            finally { Pop-Location }

            Write-Ledger $front "EXECUTED" "candidate=$candidateSha"

            $verifyExtra = @"
INDEPENDENT_VERIFICATION_TARGET
Front: $($front.id) - $($front.title)
Candidate SHA: $candidateSha
Objective: $($front.objective)
Acceptance criteria:
$acceptance

Verification rules:
- Read-only certification: do not modify files.
- Verify the exact candidate SHA and inspect the diff against its base.
- Re-run relevant repository-defined tests/checks and targeted falsification tests.
- Return VERIFIED only if every acceptance criterion is demonstrated by evidence.
- Return BLOCKED or FAILED on missing evidence, skipped relevant tests, regression, stale authority, or unverifiable claims.
"@
            & $Workpack -Task "22-verify-change" -RepoRoot $worktree -RunId "$RunId-$($front.id)-verify" -Extra $verifyExtra
            if ($LASTEXITCODE -ne 0) { throw "verification agent failed" }

            $verifyReport = Join-Path (Split-Path -Parent $Workpack) "reports\$RunId-$($front.id)-verify\22-verify-change.md"
            if (-not (Test-Path $verifyReport)) { throw "verification report missing: $verifyReport" }
            $reportText = Get-Content $verifyReport -Raw
            if ($reportText -notmatch '(?im)^.*\bVERIFIED\b') {
                throw "independent verifier did not return VERIFIED"
            }
            if ($reportText -match '(?im)\b(BLOCKED|FAILED|CRIT_FAIL|NOT_VERIFIED)\b') {
                throw "independent verifier reported a blocking/failure state"
            }

            Push-Location $worktree
            try {
                Invoke-Checked { git push -u origin $branch } "git push"
                $existing = (gh pr list --repo MarcValls/BAGO --head $branch --state open --json number --jq '.[0].number' | Out-String).Trim()
                if ($existing) {
                    $prNumber = [int]$existing
                } else {
                    $body = @"
Automated governed remediation for **$($front.id) — $($front.title)**.

Priority: **$($front.priority)**

Objective: $($front.objective)

Independent verification: **VERIFIED** for candidate `$candidateSha` before PR creation.

This PR must still pass repository CI for this exact head SHA. It must not be merged if the head moves without re-verification.
"@
                    $prNumberText = (gh pr create --repo MarcValls/BAGO --base $($Plan.base_branch) --head $branch --title "[$($front.id)] $($front.title)" --body $body | Out-String).Trim()
                    if ($prNumberText -match '/pull/(\d+)') { $prNumber = [int]$Matches[1] } else { throw "could not resolve created PR number" }
                }

                Write-Ledger $front "PR_OPEN" "pr=$prNumber candidate=$candidateSha"
                Invoke-Checked { gh pr checks $prNumber --repo MarcValls/BAGO --watch --fail-fast } "PR checks"

                $headNow = (gh pr view $prNumber --repo MarcValls/BAGO --json headRefOid --jq '.headRefOid' | Out-String).Trim()
                if ($headNow -ne $candidateSha) { throw "PR head moved after verification: expected $candidateSha got $headNow" }

                if (-not $NoMerge) {
                    Invoke-Checked { gh pr merge $prNumber --repo MarcValls/BAGO --squash --delete-branch } "PR merge"
                    Write-Ledger $front "VALIDATED" "merged PR=$prNumber after candidate-bound verification and CI"
                } else {
                    Write-Ledger $front "VERIFIED" "PR=$prNumber green; merge disabled by -NoMerge"
                }
            }
            finally { Pop-Location }

            Invoke-Checked { git worktree remove --force $worktree } "remove completed worktree"
        }
        catch {
            Write-Ledger $front "BLOCKED" $_.Exception.Message
            Write-Error "$($front.id) BLOCKED: $($_.Exception.Message)"
            throw "Orchestration stopped fail-closed at $($front.id). Resolve evidence/code and resume with -StartAt $($front.id)."
        }
    }

    Write-Host ""
    Write-Host "All selected remediation fronts completed under governed gates."
    Write-Host "Ledger: $LedgerPath"
}
finally {
    Pop-Location
}
