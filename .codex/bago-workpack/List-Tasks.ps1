$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Manifest = Get-Content (Join-Path $Here "manifest.json") -Raw | ConvertFrom-Json
$Manifest.tasks |
    Select-Object id, title, agent, model, reasoning, sandbox |
    Format-Table -AutoSize
