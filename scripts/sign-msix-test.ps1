[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$PackagePath,[Parameter(Mandatory=$true)][string]$CertificateThumbprint)
$ErrorActionPreference = 'Stop'
$package = (Resolve-Path $PackagePath).Path
$cert = Get-Item "Cert:\CurrentUser\My\$CertificateThumbprint" -ErrorAction Stop
if (-not $cert.HasPrivateKey) { throw 'The selected certificate does not have an accessible private key.' }
$archive = [System.IO.Compression.ZipFile]::OpenRead($package)
try {
    $entry = $archive.GetEntry('AppxManifest.xml')
    if (-not $entry) { throw 'MSIX AppxManifest.xml is missing.' }
    $reader = [System.IO.StreamReader]::new($entry.Open())
    try { [xml]$manifest = $reader.ReadToEnd() } finally { $reader.Dispose() }
    $ns = [System.Xml.XmlNamespaceManager]::new($manifest.NameTable)
    $ns.AddNamespace('f','http://schemas.microsoft.com/appx/manifest/foundation/windows10')
    $publisher = $manifest.SelectSingleNode('/f:Package/f:Identity',$ns).GetAttribute('Publisher')
    if ($cert.Subject -cne $publisher) { throw "Certificate subject does not match MSIX Publisher. Certificate='$($cert.Subject)' Publisher='$publisher'" }
} finally { $archive.Dispose() }
$signTool = Get-ChildItem 'C:\Program Files (x86)\Windows Kits\10\bin' -Filter SignTool.exe -Recurse | Where-Object FullName -match '\\x64\\SignTool.exe$' | Sort-Object FullName -Descending | Select-Object -First 1
if (-not $signTool) { throw 'Windows SDK SignTool.exe was not found.' }
& $signTool.FullName sign /fd SHA256 /a /sha1 $cert.Thumbprint $package
if ($LASTEXITCODE -ne 0) { throw "SignTool failed with $LASTEXITCODE" }
& $signTool.FullName verify /pa /v $package
if ($LASTEXITCODE -ne 0) { throw "SignTool verification failed with $LASTEXITCODE" }
Write-Warning 'This script is for local test signing only. It does not establish a trusted production publisher or package-deployment acceptance.'
