param(
    [string]$LabRoot = (Join-Path $PSScriptRoot '..\..\BAGO_AGENTIC_DATA_LAB'),
    [string]$JaegerQuery = 'http://localhost:16686'
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$LabRoot = (Resolve-Path $LabRoot).Path
$composeFile = Join-Path $LabRoot 'infra\observability\docker-compose.yml'
$validator = Join-Path $LabRoot 'scripts\run_l15_otel_live_validation.py'
$labPython = Join-Path $LabRoot '.venv\Scripts\python.exe'
$runDir = Join-Path $repoRoot '.run\agentic-data-lab-jaeger'
$receiptPath = Join-Path $runDir 'live-validation.json'
$warningsPath = Join-Path $runDir 'runtime-warnings.log'

foreach ($required in @($composeFile, $validator, $labPython)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required Agentic Data Lab component is missing: $required"
    }
}

New-Item -ItemType Directory -Path $runDir -Force | Out-Null

Write-Host "Starting the Agentic Data Lab Jaeger service from: $composeFile"
& docker compose -p bago-otel -f $composeFile up -d
if ($LASTEXITCODE -ne 0) {
    throw "Jaeger startup failed with exit code $LASTEXITCODE"
}

Write-Host 'Running the governed Bruma Market E2E trace and querying Jaeger.'
$output = & $labPython $validator --check --jaeger-query $JaegerQuery 2> $warningsPath
$exitCode = $LASTEXITCODE
$output | Set-Content -LiteralPath $receiptPath -Encoding utf8
$output | ForEach-Object { Write-Output $_ }
if (Test-Path -LiteralPath $warningsPath -PathType Leaf) {
    Get-Content -LiteralPath $warningsPath | ForEach-Object { Write-Warning $_ }
}

if ($exitCode -ne 0) {
    throw "Agentic Data Lab live validation failed with exit code $exitCode. Output: $receiptPath"
}

Write-Host "Live validation receipt: $receiptPath"
Write-Host "Jaeger UI: $JaegerQuery"
Write-Host 'Jaeger remains running so the trace can be inspected. Stop it with:'
Write-Host "docker compose -p bago-otel -f `"$composeFile`" down"
