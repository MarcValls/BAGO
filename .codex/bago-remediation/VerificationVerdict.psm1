Set-StrictMode -Version Latest

function Get-BagoPreverificationVerdict {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$ReportText,

        [Parameter(Mandatory=$true)]
        [ValidatePattern('^[0-9a-fA-F]{40}$')]
        [string]$ExpectedCandidateSha
    )

    $nonEmptyLines = @(
        ($ReportText -split '\r?\n') |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ }
    )
    if ($nonEmptyLines.Count -lt 1) {
        throw "Verification report is empty"
    }

    $taskVerdict = $nonEmptyLines[0].ToUpperInvariant()
    if ($taskVerdict -notin @("PASS", "FAIL", "BLOCKED")) {
        throw "Verification report must begin with the workpack verdict PASS, FAIL, or BLOCKED"
    }

    $verdictMatches = [regex]::Matches(
        $ReportText,
        '(?im)^\s*BAGO_VERDICT:\s*(PREVERIFIED|BLOCKED|FAILED)\s*$'
    )
    if ($verdictMatches.Count -ne 1) {
        throw "Verification report must contain exactly one machine verdict line: BAGO_VERDICT: PREVERIFIED|BLOCKED|FAILED"
    }
    $machineVerdict = $verdictMatches[0].Groups[1].Value.ToUpperInvariant()

    $expectedMachineVerdict = switch ($taskVerdict) {
        "PASS" { "PREVERIFIED" }
        "FAIL" { "FAILED" }
        "BLOCKED" { "BLOCKED" }
        default { throw "Unreachable task verdict" }
    }
    if ($machineVerdict -ne $expectedMachineVerdict) {
        throw "Verification verdict mismatch: task=$taskVerdict machine=$machineVerdict expected=$expectedMachineVerdict"
    }

    $shaMatches = [regex]::Matches(
        $ReportText,
        '(?im)^\s*BAGO_CANDIDATE_SHA:\s*([0-9a-fA-F]{40})\s*$'
    )
    if ($shaMatches.Count -ne 1) {
        throw "Verification report must contain exactly one BAGO_CANDIDATE_SHA line"
    }

    $reportedSha = $shaMatches[0].Groups[1].Value.ToLowerInvariant()
    $expectedSha = $ExpectedCandidateSha.ToLowerInvariant()
    if ($reportedSha -ne $expectedSha) {
        throw "Verification report candidate SHA mismatch: expected $expectedSha got $reportedSha"
    }

    return $machineVerdict
}

Export-ModuleMember -Function Get-BagoPreverificationVerdict
