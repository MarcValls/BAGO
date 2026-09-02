param(
    [string]$ServerName = "powerbi-modeling-mcp",
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[powerbi-mcp-auth] $Message"
}

if (-not (Get-Command copilot -ErrorAction SilentlyContinue)) {
    throw "GitHub Copilot CLI was not found in PATH. Install or expose the 'copilot' command before authenticating MCP servers."
}

$details = & copilot mcp get $ServerName 2>&1
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    $detailText = ($details | Out-String).Trim()
    throw "MCP server '$ServerName' is not configured for Copilot CLI. Run 'copilot mcp list' to inspect available servers. $detailText"
}

$detailsText = ($details | Out-String).Trim()
if ($detailsText -notmatch "Status:\s+Enabled") {
    throw "MCP server '$ServerName' is configured but not enabled. Enable it before authentication."
}

Write-Step "Found enabled MCP server '$ServerName'."
Write-Step $detailsText

if ($CheckOnly) {
    Write-Step "Check-only mode completed. No authentication flow was started."
    exit 0
}

Write-Step "Starting Copilot interactive MCP authentication flow."
Write-Step "If the CLI shows a browser/device prompt, complete it with the intended Microsoft/Fabric account."

& copilot -i "/mcp auth $ServerName"
exit $LASTEXITCODE
