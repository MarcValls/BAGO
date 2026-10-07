$ErrorActionPreference = 'Stop'
$probeRoot = $PSScriptRoot
$providerKey = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Authentication\Credential Providers'
$providers = @(Get-ChildItem -LiteralPath $providerKey | ForEach-Object {
    $providerId = $_.PSChildName
    $serverKey = 'HKLM:\SOFTWARE\Classes\CLSID\' + $providerId + '\InprocServer32'
    $server = if (Test-Path -LiteralPath $serverKey) { (Get-Item -LiteralPath $serverKey).GetValue('') } else { $null }
    $resolvedServer = if ($server) { [Environment]::ExpandEnvironmentVariables($server) } else { $null }
    if ($resolvedServer -and -not [IO.Path]::IsPathRooted($resolvedServer)) {
        $resolvedServer = Join-Path $env:WINDIR ('System32\' + $resolvedServer)
    }
    $present = $resolvedServer -and (Test-Path -LiteralPath $resolvedServer)
    $signature = if ($present) { Get-AuthenticodeSignature -LiteralPath $resolvedServer } else { $null }
    [ordered]@{ clsid = $providerId; name = $_.GetValue(''); server = $resolvedServer;
        exists = [bool]$present; sha256 = if ($present) { (Get-FileHash -LiteralPath $resolvedServer -Algorithm SHA256).Hash } else { $null };
        signature_status = if ($signature) { $signature.Status.ToString() } else { $null };
        signer = if ($signature -and $signature.SignerCertificate) { $signature.SignerCertificate.Subject } else { $null }
    }
})
$apis = @('credui.dll', 'secur32.dll', 'advapi32.dll') | ForEach-Object {
    $apiPath = Join-Path $env:WINDIR ('System32\' + $_)
    $signature = Get-AuthenticodeSignature -LiteralPath $apiPath
    [ordered]@{ path = $apiPath; sha256 = (Get-FileHash -LiteralPath $apiPath -Algorithm SHA256).Hash;
        signature_status = $signature.Status.ToString(); signer = $signature.SignerCertificate.Subject }
}
$inventory = [ordered]@{ utc = [DateTime]::UtcNow.ToString('o'); scope = 'REGISTERED_ONLY_NOT_SELECTED_PROVIDER';
    mutations_enabled = $false; selected_provider_verified = $false; providers = $providers; apis = @($apis) }
$inventory | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $probeRoot 'provider-inventory.json') -Encoding UTF8
Write-Output ('Registered providers: ' + $providers.Count)
