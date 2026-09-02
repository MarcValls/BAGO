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
$WorkpackManifestPath = Join-Path (Split-Path -Parent $Workpack) "manifest.json"
$ExpectedRepository = "MarcValls/BAGO"
$ExpectedPlanSchema = "1.1"

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' is not available in PATH."
    }
}

function Invoke-Checked([scriptblock]$Command, [string]$What) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$What failed with exit code $LASTEXITCODE" }
}

function Assert-ObjectProperty($Object, [string]$Name, [string]$Path) {
    if ($null -eq $Object) { throw "Missing required plan object: $Path" }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property -or $null -eq $property.Value) {
        throw "Missing required plan property: $Path.$Name"
    }
    if ($property.Value -is [string] -and [string]::IsNullOrWhiteSpace([string]$property.Value)) {
        throw "Required plan property is blank: $Path.$Name"
    }
}

function Assert-PlanContract($PlanObject) {
    Assert-ObjectProperty $PlanObject "schema_version" "plan"
    Assert-ObjectProperty $PlanObject "base_branch" "plan"
    Assert-ObjectProperty $PlanObject "execution_policy" "plan"
    Assert-ObjectProperty $PlanObject "fronts" "plan"

    if ([string]$PlanObject.schema_version -ne $ExpectedPlanSchema) {
        throw "Unsupported remediation plan schema '$($PlanObject.schema_version)'; expected '$ExpectedPlanSchema'"
    }

    $policy = $PlanObject.execution_policy
    foreach ($name in @(
        "mode",
        "implementation_task",
        "verification_task",
        "close_only_on_verified",
        "auto_merge_only_after_ci",
        "self_certification_forbidden",
        "failure_policy",
        "evidence_required",
        "required_pr_workflows"
    )) {
        Assert-ObjectProperty $policy $name "plan.execution_policy"
    }

    if ([string]$policy.mode -ne "sequential_dependency_safe") {
        throw "Unsupported execution mode '$($policy.mode)'"
    }
    if ($policy.close_only_on_verified -ne $true) {
        throw "Plan must keep close_only_on_verified=true"
    }
    if ($policy.auto_merge_only_after_ci -ne $true) {
        throw "Plan must keep auto_merge_only_after_ci=true"
    }
    if ($policy.self_certification_forbidden -ne $true) {
        throw "Plan must keep self_certification_forbidden=true"
    }
    if ([string]$policy.failure_policy -ne "stop_and_block") {
        throw "Plan must keep failure_policy=stop_and_block"
    }
    if ($policy.evidence_required -ne $true) {
        throw "Plan must keep evidence_required=true"
    }

    foreach ($taskProperty in @("implementation_task", "verification_task")) {
        $taskId = [string]$policy.$taskProperty
        if ($taskId -notmatch '^[A-Za-z0-9._-]+$') {
            throw "Unsafe task id in plan.execution_policy.$taskProperty: '$taskId'"
        }
    }
    if ([string]$policy.implementation_task -eq [string]$policy.verification_task) {
        throw "Implementation and verification tasks must be different"
    }

    $requiredWorkflows = @($policy.required_pr_workflows)
    if ($requiredWorkflows.Count -eq 0) {
        throw "plan.execution_policy.required_pr_workflows must contain at least one workflow"
    }
    foreach ($workflow in $requiredWorkflows) {
        if ([string]::IsNullOrWhiteSpace([string]$workflow)) {
            throw "plan.execution_policy.required_pr_workflows contains a blank workflow name"
        }
    }

    $fronts = @($PlanObject.fronts)
    if ($fronts.Count -ne 15) { throw "Schema $ExpectedPlanSchema requires exactly 15 remediation fronts" }
    $seen = @{}
    for ($index = 0; $index -lt $fronts.Count; $index++) {
        $front = $fronts[$index]
        Assert-ObjectProperty $front "id" "plan.fronts[]"
        Assert-ObjectProperty $front "priority" "plan.fronts[$($front.id)]"
        Assert-ObjectProperty $front "title" "plan.fronts[$($front.id)]"
        Assert-ObjectProperty $front "objective" "plan.fronts[$($front.id)]"
        Assert-ObjectProperty $front "acceptance" "plan.fronts[$($front.id)]"

        $expectedId = "F{0:D2}" -f ($index + 1)
        if ([string]$front.id -ne $expectedId) {
            throw "Remediation front order must be F01..F15; expected $expectedId at index $index but found '$($front.id)'"
        }
        if ([string]$front.id -notmatch '^F[0-9]{2}$') {
            throw "Unsafe remediation front id '$($front.id)'"
        }
        if ([string]$front.priority -notmatch '^P[0-3]$') {
            throw "Unsupported priority '$($front.priority)' for front '$($front.id)'"
        }
        if (@($front.acceptance).Count -eq 0) {
            throw "Front '$($front.id)' has no acceptance criteria"
        }
        foreach ($criterion in @($front.acceptance)) {
            if ([string]::IsNullOrWhiteSpace([string]$criterion)) {
                throw "Front '$($front.id)' contains a blank acceptance criterion"
            }
        }
        if ($seen.ContainsKey([string]$front.id)) {
            throw "Duplicate remediation front id '$($front.id)'"
        }
        $seen[[string]$front.id] = $true
    }
}

function Assert-WorkpackTaskContract($Manifest, [string]$ImplementationTaskId, [string]$VerificationTaskId) {
    if ($null -eq $Manifest -or $null -eq $Manifest.PSObject.Properties["tasks"]) {
        throw "Workpack manifest is missing tasks"
    }

    $implementationMatches = @($Manifest.tasks | Where-Object { $_.id -eq $ImplementationTaskId })
    $verificationMatches = @($Manifest.tasks | Where-Object { $_.id -eq $VerificationTaskId })
    if ($implementationMatches.Count -ne 1) {
        throw "Implementation task '$ImplementationTaskId' must resolve exactly once in the workpack manifest"
    }
    if ($verificationMatches.Count -ne 1) {
        throw "Verification task '$VerificationTaskId' must resolve exactly once in the workpack manifest"
    }

    $implementation = $implementationMatches[0]
    $verification = $verificationMatches[0]
    if ([string]$implementation.sandbox -ne "workspace-write") {
        throw "Implementation task '$ImplementationTaskId' must use workspace-write sandbox"
    }
    if ([string]$implementation.agent -notmatch '^bago_.*_worker$') {
        throw "Implementation task '$ImplementationTaskId' must use a BAGO worker agent"
    }
    if ($implementation.requires_extra -ne $true) {
        throw "Implementation task '$ImplementationTaskId' must require explicit approved scope"
    }
    if ([string]$verification.sandbox -ne "read-only") {
        throw "Verification task '$VerificationTaskId' must use read-only sandbox"
    }
    if ([string]$verification.agent -ne "bago_final_verifier") {
        throw "Verification task '$VerificationTaskId' must use bago_final_verifier"
    }
    if ($verification.requires_extra -ne $true) {
        throw "Verification task '$VerificationTaskId' must require explicit verification target"
    }
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

function Wait-ForCompletePrChecks([int]$PrNumber) {
    # `gh pr checks` exits 8 while any check is still pending/queued and 1 when a
    # check has genuinely failed. Poll on exit code 8 only; any other nonzero
    # exit is a real failure and must not be waited out.
    for ($attempt = 0; $attempt -lt 1080; $attempt++) {
        gh pr checks $PrNumber --repo $ExpectedRepository | Out-Null
        $checksExit = $LASTEXITCODE
        if ($checksExit -eq 0) { return }
        if ($checksExit -ne 8) { throw "PR checks failed for pr=$PrNumber (gh pr checks exit code $checksExit)" }
        Start-Sleep -Seconds 5
    }

    throw "PR checks did not reach a complete state for pr=$PrNumber within the bounded polling window"
}

function Wait-ForConfirmedMerge([int]$PrNumber, [string]$CandidateSha, [string]$ExpectedBaseBranch) {
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        $jsonText = (gh pr view $PrNumber --repo $ExpectedRepository --json state,mergedAt,mergeCommit,headRefOid,baseRefName | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) { throw "Unable to read PR state after merge request" }
        $view = $jsonText | ConvertFrom-Json

        if ($view.headRefOid -ne $CandidateSha) {
            throw "PR head moved while awaiting merge confirmation: expected $CandidateSha got $($view.headRefOid)"
        }

        if ($view.baseRefName -cne $ExpectedBaseBranch) {
            throw "PR base branch moved while awaiting merge confirmation: expected $ExpectedBaseBranch got $($view.baseRefName)"
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
if (-not (Test-Path $WorkpackManifestPath)) { throw "Missing BAGO workpack manifest: $WorkpackManifestPath" }

Import-Module $VerdictModule -Force
$Plan = Get-Content $PlanPath -Raw | ConvertFrom-Json
Assert-PlanContract $Plan
$implementationTask = [string]$Plan.execution_policy.implementation_task
$verificationTask = [string]$Plan.execution_policy.verification_task
$requiredPrWorkflows = @($Plan.execution_policy.required_pr_workflows)
$WorkpackManifest = Get-Content $WorkpackManifestPath -Raw | ConvertFrom-Json
Assert-WorkpackTaskContract -Manifest $WorkpackManifest -ImplementationTaskId $implementationTask -VerificationTaskId $verificationTask

$safeRunId = ($RunId -replace '[^A-Za-z0-9._-]+','-').Trim('-')
if (-not $safeRunId) { throw "RunId must contain at least one safe character" }
if ($safeRunId -in @(".", "..")) { throw "RunId resolves to an unsafe physical path segment" }
if ($safeRunId.Length -gt 64) { throw "RunId is too long after sanitization; maximum physical length is 64 characters" }

Push-Location $Repo
try {
    Invoke-Checked { git fetch origin --prune } "git fetch"

    $originUrl = (git remote get-url origin | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw "Could not resolve origin URL" }
    # Anchor to the exact host and path so a lookalike domain such as
    # "evilgithub.com" (which merely contains "github.com" as a substring)
    # cannot be accepted as origin.
    if ($originUrl -notmatch '(?i)^(?:https://|ssh://git@|git@)?github\.com[:/]MarcValls/BAGO(?:\.git)?/?$') {
        throw "Refusing orchestration: origin is not $ExpectedRepository ($originUrl)"
    }

    Invoke-Checked { git check-ref-format --branch $($Plan.base_branch) | Out-Null } "base branch format validation"

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

    $gitDir = Get-AbsoluteGitDir $Repo
    $LedgerRoot = Join-Path $gitDir ("bago-remediation-runs\run-" + $safeRunId)
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
            run_id_safe = $safeRunId
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
        if (-not $slug) { $slug = $front.id.ToLowerInvariant() }
        $branch = "remediation/$($front.id.ToLowerInvariant())-$slug-$safeRunId"
        $worktree = Join-Path $WorktreeRoot $front.id
        $implementationRunId = "$safeRunId-$($front.id)-impl"
        $verificationRunId = "$safeRunId-$($front.id)-verify"

        Write-Host ""
        Write-Host "============================================================"
        Write-Host "$($front.id) [$($front.priority)] $($front.title)"
        Write-Host "============================================================"
        Write-Ledger $front "PREPARED" "starting front"

        try {
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
                Write-Host "DRY RUN: would invoke implementation task $implementationTask and verification task $verificationTask for $($front.id) on $branch"
                Write-Ledger $front "DRY_RUN" "base=$baseSha branch=$branch; no agent mutation executed"
                Invoke-Checked { git worktree remove --force $worktree } "remove dry-run worktree"
                git branch -D $branch 2>$null | Out-Null
                continue
            }

            & $Workpack -Task $implementationTask -RepoRoot $worktree -RunId $implementationRunId -Extra $extra
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
            & $Workpack -Task $verificationTask -RepoRoot $worktree -RunId $verificationRunId -Extra $verifyExtra
            if ($LASTEXITCODE -ne 0) { throw "verification agent failed" }

            $verifyReport = Join-Path (Split-Path -Parent $Workpack) ("reports\$verificationRunId\" + $verificationTask + ".md")
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
                Wait-ForCompletePrChecks -PrNumber $prNumber

                $headJson = (gh pr view $prNumber --repo $ExpectedRepository --json headRefOid,baseRefName | Out-String).Trim()
                if ($LASTEXITCODE -ne 0) { throw "could not resolve PR head after checks" }
                $prView = $headJson | ConvertFrom-Json
                $headNow = $prView.headRefOid
                if ($headNow -ne $candidateSha) { throw "PR head moved after preverification: expected $candidateSha got $headNow" }
                if ($prView.baseRefName -cne $Plan.base_branch) { throw "PR base branch moved: expected $($Plan.base_branch) got $($prView.baseRefName)" }

                Write-Ledger $front "VERIFIED" "pr=$prNumber candidate=$candidateSha; independent preverification plus required workflow runs and complete green PR checks"

                if ($NoMerge) {
                    $stoppedAtVerified = $front.id
                } else {
                    Invoke-Checked { gh pr merge $prNumber --repo $ExpectedRepository --squash --match-head-commit $candidateSha } "PR merge request"
                    $mergeSha = Wait-ForConfirmedMerge -PrNumber $prNumber -CandidateSha $candidateSha -ExpectedBaseBranch $Plan.base_branch
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
