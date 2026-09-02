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
$VerdictModule = Join-Path $Here "VerificationVerdict.psm1"
$Workpack = Join-Path (Split-Path -Parent $Here) "bago-workpack\Run.ps1"
$ExpectedRepository = "MarcValls/BAGO"

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' is not available in PATH."
    }
}

function Invoke-Checked([scriptblock]$Command, [string]$What) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$What failed with exit code $LASTEXITCODE" }
}

function Get-AbsoluteGitDir([string]$RepositoryRoot) {
    $raw = (git rev-parse --git-dir | Out-String).Trim()
    if (-not $raw) { throw "Could not resolve Git directory" }
    if ([System.IO.Path]::IsPathRooted($raw)) { return $raw }
    return [System.IO.Path]::GetFullPath((Join-Path $RepositoryRoot $raw))
}

function Wait-ForRequiredWorkflowRuns([string]$CandidateSha, [object[]]$RequiredWorkflowNames) {
    for ($attempt = 0; $attempt -lt 1080; $attempt++) {
        $jsonText = (gh run list --repo $ExpectedRepository --commit $CandidateSha --event pull_request --limit 100 --json workflowName,status,conclusion,createdAt,url | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) { throw "Unable to enumerate workflow runs for exact candidate $CandidateSha" }

        $runs = @()
        if ($jsonText) { $runs = @($jsonText | ConvertFrom-Json) }
        $allPassed = $true

        foreach ($requiredName in @($RequiredWorkflowNames)) {
            $required = [string]$requiredName
            $matches = @($runs | Where-Object { $_.workflowName -eq $required })
            if ($matches.Count -eq 0) {
                $allPassed = $false
                continue
            }

            $latest = $matches | Sort-Object -Property createdAt -Descending | Select-Object -First 1
            if ($latest.status -eq "completed") {
                if ($latest.conclusion -ne "success") {
                    throw "Required PR workflow '$required' concluded '$($latest.conclusion)' for candidate $CandidateSha ($($latest.url))"
                }
            } else {
                $allPassed = $false
            }
        }

        if ($allPassed) { return }
        Start-Sleep -Seconds 5
    }

    $requiredText = (@($RequiredWorkflowNames) -join ", ")
    throw "Required PR workflows did not all reach success for candidate $CandidateSha: $requiredText"
}

function Wait-ForConfirmedMerge([int]$PrNumber, [string]$CandidateSha) {
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        $jsonText = (gh pr view $PrNumber --repo $ExpectedRepository --json state,mergedAt,mergeCommit,headRefOid | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) { throw "Unable to read PR state after merge request" }
        $view = $jsonText | ConvertFrom-Json

        if ($view.headRefOid -ne $CandidateSha) {
            throw "PR head moved while awaiting merge confirmation: expected $CandidateSha got $($view.headRefOid)"
        }

        if ($view.state -eq "MERGED" -and $view.mergedAt) {
            $mergeSha = $null
            if ($view.mergeCommit -and $view.mergeCommit.oid) { $mergeSha = $view.mergeCommit.oid }
            return $mergeSha
        }

        if ($view.state -eq "CLOSED") {
            throw "PR closed without confirmed merge"
        }

        Start-Sleep -Seconds 5
    }

    throw "Merge was requested but GitHub did not confirm MERGED state within the bounded polling window"
}

Require-Command git
Require-Command codex
Require-Command gh

$Repo = (Resolve-Path $RepoRoot).Path
if (-not (Test-Path (Join-Path $Repo ".git"))) { throw "RepoRoot is not a Git repository: $Repo" }
if (-not (Test-Path $PlanPath)) { throw "Missing remediation plan: $PlanPath" }
if (-not (Test-Path $VerdictModule)) { throw "Missing verification verdict module: $VerdictModule" }
if (-not (Test-Path $Workpack)) { throw "Missing BAGO workpack runner: $Workpack" }

Import-Module $VerdictModule -Force
$Plan = Get-Content $PlanPath -Raw | ConvertFrom-Json
$safeRunId = ($RunId -replace '[^A-Za-z0-9._-]+','-').Trim('-')
if (-not $safeRunId) { throw "RunId must contain at least one safe character" }

Push-Location $Repo
try {
    Invoke-Checked { git fetch origin --prune } "git fetch"

    $originUrl = (git remote get-url origin | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw "Could not resolve origin URL" }
    if ($originUrl -notmatch '(?i)github\.com[:/]MarcValls/BAGO(?:\.git)?$') {
        throw "Refusing orchestration: origin is not $ExpectedRepository ($originUrl)"
    }

    $status = (git status --porcelain=v1 | Out-String).Trim()
    if ($status) { throw "Base worktree must be clean before orchestration. Commit/stash changes first." }

    $startIndex = -1
    for ($i = 0; $i -lt $Plan.fronts.Count; $i++) {
        if ($Plan.fronts[$i].id -eq $StartAt) { $startIndex = $i; break }
    }
    if ($startIndex -lt 0) {
        $valid = ($Plan.fronts.id -join ", ")
        throw "Unknown StartAt '$StartAt'. Valid fronts: $valid"
    }

    $requiredPrWorkflows = @($Plan.execution_policy.required_pr_workflows)
    if ($requiredPrWorkflows.Count -eq 0) {
        throw "Remediation plan must declare at least one required_pr_workflows entry"
    }

    $gitDir = Get-AbsoluteGitDir $Repo
    $LedgerRoot = Join-Path $gitDir ("bago-remediation-runs\" + $safeRunId)
    if (Test-Path $LedgerRoot) {
        throw "RunId '$RunId' already has preserved evidence at $LedgerRoot. Use a new RunId."
    }
    New-Item -ItemType Directory -Force -Path $LedgerRoot | Out-Null
    $LedgerPath = Join-Path $LedgerRoot "ledger.jsonl"

    $WorktreeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("bago-remediation-" + $safeRunId)
    if (Test-Path $WorktreeRoot) {
        throw "Temporary worktree root already exists: $WorktreeRoot. Preserve/inspect it or use a new RunId."
    }
    New-Item -ItemType Directory -Force -Path $WorktreeRoot | Out-Null

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

    $stoppedAtVerified = $null

    for ($i = $startIndex; $i -lt $Plan.fronts.Count; $i++) {
        $front = $Plan.fronts[$i]
        $slug = ($front.title.ToLowerInvariant() -replace '[^a-z0-9]+','-').Trim('-')
        if ($slug.Length -gt 34) { $slug = $slug.Substring(0,34).Trim('-') }
        $branch = "remediation/$($front.id.ToLowerInvariant())-$slug-$safeRunId"
        $worktree = Join-Path $WorktreeRoot $front.id

        Write-Host ""
        Write-Host "============================================================"
        Write-Host "$($front.id) [$($front.priority)] $($front.title)"
        Write-Host "============================================================"
        Write-Ledger $front "PREPARED" "starting front"

        Invoke-Checked { git fetch origin $($Plan.base_branch) } "fetch base"
        $baseSha = (git rev-parse "origin/$($Plan.base_branch)" | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $baseSha) { throw "Could not resolve base SHA" }

        if (Test-Path $worktree) {
            throw "Worktree path already exists and will not be destroyed automatically: $worktree"
        }
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
            Write-Ledger $front "DRY_RUN" "base=$baseSha branch=$branch; no agent mutation executed"
            Invoke-Checked { git worktree remove --force $worktree } "remove dry-run worktree"
            git branch -D $branch 2>$null | Out-Null
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
                $candidateSha = (git rev-parse HEAD | Out-String).Trim()
                if ($LASTEXITCODE -ne 0 -or $candidateSha -notmatch '^[0-9a-f]{40}$') { throw "invalid candidate SHA" }
            }
            finally { Pop-Location }

            Write-Ledger $front "EXECUTED" "base=$baseSha candidate=$candidateSha branch=$branch"

            $verifyExtra = @"
INDEPENDENT_PREVERIFICATION_TARGET
Front: $($front.id) - $($front.title)
Candidate SHA: $candidateSha
Objective: $($front.objective)
Acceptance criteria:
$acceptance

Verification rules:
- Read-only certification: do not modify files or commits.
- Verify the exact candidate SHA and inspect the diff against base $baseSha.
- Re-run relevant repository-defined local tests/checks and targeted falsification tests.
- Acceptance items that explicitly require GitHub PR CI or a confirmed merge are DEFERRED_EXTERNAL gates owned by the supervisor after this pass; do not claim they have already happened.
- Preserve the workpack task contract: the first non-empty line must be exactly PASS, FAIL, or BLOCKED.
- Use PASS only when every non-deferred acceptance criterion is demonstrated by evidence and no blocking condition exists.
- Use FAIL or BLOCKED on missing local evidence, skipped relevant local tests, regression, stale authority, unverifiable claims, or candidate mismatch.
- End the report with exactly one candidate line and exactly one mapped machine verdict line:
  PASS    -> BAGO_VERDICT: PREVERIFIED
  FAIL    -> BAGO_VERDICT: FAILED
  BLOCKED -> BAGO_VERDICT: BLOCKED
  BAGO_CANDIDATE_SHA: $candidateSha
"@
            & $Workpack -Task "22-verify-change" -RepoRoot $worktree -RunId "$RunId-$($front.id)-verify" -Extra $verifyExtra
            if ($LASTEXITCODE -ne 0) { throw "verification agent failed" }

            $verifyReport = Join-Path (Split-Path -Parent $Workpack) "reports\$RunId-$($front.id)-verify\22-verify-change.md"
            if (-not (Test-Path $verifyReport)) { throw "verification report missing: $verifyReport" }
            $reportText = Get-Content $verifyReport -Raw
            $verdict = Get-BagoPreverificationVerdict -ReportText $reportText -ExpectedCandidateSha $candidateSha
            if ($verdict -ne "PREVERIFIED") {
                throw "independent verifier returned $verdict instead of PREVERIFIED"
            }

            Push-Location $worktree
            try {
                $headAfterVerify = (git rev-parse HEAD | Out-String).Trim()
                if ($headAfterVerify -ne $candidateSha) {
                    throw "candidate HEAD changed during read-only verification: expected $candidateSha got $headAfterVerify"
                }
                $dirtyAfterVerify = (git status --porcelain=v1 | Out-String).Trim()
                if ($dirtyAfterVerify) {
                    throw "read-only verification left tracked/untracked repository changes"
                }
            }
            finally { Pop-Location }

            Write-Ledger $front "PREVERIFIED" "candidate=$candidateSha report=$verifyReport"

            Push-Location $worktree
            try {
                Invoke-Checked { git push -u origin $branch } "git push"

                $listText = (gh pr list --repo $ExpectedRepository --head $branch --state open --json number | Out-String).Trim()
                if ($LASTEXITCODE -ne 0) { throw "could not query existing PR" }
                $existingList = @($listText | ConvertFrom-Json)
                if ($existingList.Count -gt 0) {
                    $prNumber = [int]$existingList[0].number
                } else {
                    $body = @"
Automated governed remediation for **$($front.id) — $($front.title)**.

Priority: **$($front.priority)**

Objective: $($front.objective)

Independent local preverification: **PREVERIFIED** for candidate `$candidateSha`.

Final VERIFIED state still requires every workflow named in the remediation execution policy to complete successfully for this exact SHA, followed by the complete PR check set. VALIDATED additionally requires GitHub to confirm the PR as merged. Any head movement invalidates this preverification.
"@
                    $prUrl = (gh pr create --repo $ExpectedRepository --base $($Plan.base_branch) --head $branch --title "[$($front.id)] $($front.title)" --body $body | Out-String).Trim()
                    if ($LASTEXITCODE -ne 0) { throw "PR creation failed" }
                    if ($prUrl -match '/pull/(\d+)') { $prNumber = [int]$Matches[1] } else { throw "could not resolve created PR number" }
                }

                Write-Ledger $front "PR_OPEN" "pr=$prNumber candidate=$candidateSha"
                Wait-ForRequiredWorkflowRuns -CandidateSha $candidateSha -RequiredWorkflowNames $requiredPrWorkflows
                Invoke-Checked { gh pr checks $prNumber --repo $ExpectedRepository } "complete PR checks"

                $headJson = (gh pr view $prNumber --repo $ExpectedRepository --json headRefOid | Out-String).Trim()
                if ($LASTEXITCODE -ne 0) { throw "could not resolve PR head after checks" }
                $headNow = ($headJson | ConvertFrom-Json).headRefOid
                if ($headNow -ne $candidateSha) { throw "PR head moved after preverification: expected $candidateSha got $headNow" }

                Write-Ledger $front "VERIFIED" "pr=$prNumber candidate=$candidateSha; independent preverification plus required workflow runs and complete green PR checks"

                if ($NoMerge) {
                    $stoppedAtVerified = $front.id
                } else {
                    Invoke-Checked { gh pr merge $prNumber --repo $ExpectedRepository --squash --match-head-commit $candidateSha } "PR merge request"
                    $mergeSha = Wait-ForConfirmedMerge -PrNumber $prNumber -CandidateSha $candidateSha
                    Write-Ledger $front "VALIDATED" "pr=$prNumber candidate=$candidateSha merge=$mergeSha; GitHub confirmed MERGED"
                }
            }
            finally { Pop-Location }

            Invoke-Checked { git worktree remove --force $worktree } "remove completed worktree"
            git branch -D $branch 2>$null | Out-Null

            if ($stoppedAtVerified) {
                Write-Host "NoMerge stops after VERIFIED front $stoppedAtVerified so the next front cannot be based on origin/main without this unmerged dependency."
                break
            }
        }
        catch {
            Write-Ledger $front "BLOCKED" ("worktree=$worktree branch=$branch; " + $_.Exception.Message)
            Write-Error "$($front.id) BLOCKED: $($_.Exception.Message)"
            throw "Orchestration stopped fail-closed at $($front.id). Evidence/worktree is preserved. Resolve the cause and resume with a new RunId and -StartAt $($front.id)."
        }
    }

    Write-Host ""
    if ($stoppedAtVerified) {
        Write-Host "Stopped safely at VERIFIED $stoppedAtVerified because -NoMerge was requested. Merge that PR before continuing dependent fronts."
    } else {
        Write-Host "All selected remediation fronts completed under governed gates."
    }
    Write-Host "Ledger: $LedgerPath"
}
finally {
    Pop-Location
}
