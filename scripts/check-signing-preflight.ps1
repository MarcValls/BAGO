[CmdletBinding()]
param(
    [string]$Repository = "MarcValls/BAGO",
    [string]$Environment = "release-signing"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Read-only preflight for the protected Authenticode signing environment.
# Verifies presence only; never prints secret values.

$requiredSecrets = @("AZURE_CLIENT_ID", "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID")
$requiredVariables = @("BAGO_SIGNING_ENDPOINT", "BAGO_SIGNING_ACCOUNT", "BAGO_SIGNING_PROFILE", "BAGO_SIGNING_PUBLISHER")

$failures = @()

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "gh CLI no está disponible; no se puede comprobar la configuración remota."
}

function Invoke-GhCapture {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    # A non-zero native exit code is expected for an absent environment or
    # insufficient scope. Capture it so this preflight can return its
    # machine-readable fail-closed receipt instead of terminating early.
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = @(& gh @Arguments 2>&1 | ForEach-Object { $_.ToString() })
        return [pscustomobject]@{
            ExitCode = $LASTEXITCODE
            Output = $output
        }
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
}

$authStatus = Invoke-GhCapture -Arguments @("auth", "status")
if ($authStatus.ExitCode -ne 0) {
    $failures += "gh no está autenticado (gh auth login)."
}

$envExists = $false
if (-not $failures) {
    $environmentResult = Invoke-GhCapture -Arguments @("api", "repos/$Repository/environments/$Environment", "--jq", ".name")
    if ($environmentResult.ExitCode -eq 0) {
        $envExists = $true
    } else {
        $failures += "El entorno '$Environment' no existe en $Repository (créalo en Settings > Environments)."
    }
}

$envSecretNames = @()
$envVariableNames = @()
if ($envExists) {
    $secretsResult = Invoke-GhCapture -Arguments @("api", "repos/$Repository/environments/$Environment/secrets")
    if ($secretsResult.ExitCode -eq 0) {
        $envSecretNames = @((($secretsResult.Output -join "`n") | ConvertFrom-Json).secrets | ForEach-Object { $_.name })
    } else {
        $failures += "No se pudieron listar los secrets del entorno (¿scope repo suficiente?)."
    }
    $variablesResult = Invoke-GhCapture -Arguments @("api", "repos/$Repository/environments/$Environment/variables")
    if ($variablesResult.ExitCode -eq 0) {
        $envVariableNames = @((($variablesResult.Output -join "`n") | ConvertFrom-Json).variables | ForEach-Object { $_.name })
    } else {
        $failures += "No se pudieron listar las variables del entorno (¿scope repo suficiente?)."
    }

    # Environment-scoped values take priority; repository-level fallbacks also count.
    $repoSecrets = @()
    $repoSecretsResult = Invoke-GhCapture -Arguments @("secret", "list", "-R", $Repository)
    if ($repoSecretsResult.ExitCode -eq 0) {
        $repoSecrets = @($repoSecretsResult.Output | ForEach-Object { ($_ -split "\s+")[0] })
    }
    $repoVariables = @()
    $repoVariablesResult = Invoke-GhCapture -Arguments @("api", "repos/$Repository/actions/variables")
    if ($repoVariablesResult.ExitCode -eq 0) {
        $repoVariables = @((($repoVariablesResult.Output -join "`n") | ConvertFrom-Json).variables | ForEach-Object { $_.name })
    }

    foreach ($name in $requiredSecrets) {
        if ($envSecretNames -notcontains $name -and $repoSecrets -notcontains $name) {
            $failures += "Secret ausente: $name"
        }
    }
    foreach ($name in $requiredVariables) {
        if ($envVariableNames -notcontains $name -and $repoVariables -notcontains $name) {
            $failures += "Variable ausente: $name"
        }
    }
}

$result = [ordered]@{
    contract = "bago.signing-preflight.v1"
    repository = $Repository
    environment = $Environment
    environment_exists = $envExists
    required_secrets = $requiredSecrets
    required_variables = $requiredVariables
    failures = $failures
    ready = ($failures.Count -eq 0)
}
$result | ConvertTo-Json -Depth 4

if ($failures.Count -gt 0) {
    exit 1
}
exit 0
