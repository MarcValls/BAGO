# Probar con Start-Job en lugar de Process
$token = (Get-Content "$HOME\BAGO\.bago\config\github_token.txt" -Encoding UTF8 -Raw).Trim()
$ghPath = "$env:LOCALAPPDATA\Programs\GitHub CLI\gh.exe"
$job = Start-Job -ScriptBlock {
    param($gh, $tok)
    $env:GH_TOKEN = $tok
    & $gh copilot -p "hello from BAGO"
} -ArgumentList $ghPath, $token
Write-Host "Job started, waiting..."
$job | Wait-Job -Timeout 15
$output = Receive-Job -Job $job
Write-Host "Output:"
Write-Host $output
Remove-Job -Job $job
