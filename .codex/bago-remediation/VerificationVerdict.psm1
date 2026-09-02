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

    $verdictMatches = [regex]::Matches(
        $ReportText,
        '(?im)^\s*BAGO_VERDICT:\s*(PREVERIFIED|BLOCKED|FAILED)\s*$'
    )
    if ($verdictMatches.Count -ne 1) {
        throw "Verification report must contain exactly one machine verdict line: BAGO_VERDICT: PREVERIFIED|BLOCKED|FAILED"
    }

    $shaMatches = [regex]::Matches(
        $ReportText,
        '(?im)^\s*BAGO_CANDIDATE_SHA:\s*([0-9a-f]{40})\s*$'
    )
    if ($shaMatches.Count -ne 1) {
        throw "Verification report must contain exactly one BAGO_CANDIDATE_SHA line"
    }

    $reportedSha = $shaMatches[0].Groups[1].Value.ToLowerInvariant()
    $expectedSha = $ExpectedCandidateSha.ToLowerInvariant()
    if ($reportedSha -ne $expectedSha) {
        throw "Verification report candidate SHA mismatch: expected $expectedSha got $reportedSha"
    }

    return $verdictMatches[0].Groups[1].Value.ToUpperInvariant()
}

Export-ModuleMember -Function Get-BagoPreverificationVerdict
