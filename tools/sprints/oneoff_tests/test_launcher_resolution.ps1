$ErrorActionPreference = 'Stop'
$userBago = Join-Path $env:USERPROFILE '.bago'
$selectionFile = Join-Path $userBago 'install_selection.json'

Write-Output "Selection file: $selectionFile"
Write-Output "Exists: $(Test-Path $selectionFile)"

if (Test-Path $selectionFile) {
    $selection = Get-Content -LiteralPath $selectionFile -Raw | ConvertFrom-Json
    Write-Output "Roles parsed: $($selection.roles | ConvertTo-Json -Compress)"
    foreach ($role in @('active','dev','launch')) {
        $entry = $selection.roles.$role
        if ($entry -and $entry.path) {
            $exists = Test-Path $entry.path
            Write-Output "  $role -> $($entry.path) [exists=$exists]"
        } else {
            Write-Output "  $role -> <missing in JSON>"
        }
    }
} else {
    Write-Output "NO selection file"
}

# Now invoke bago with --test to verify it reaches the right cli.py
Write-Output ""
Write-Output "--- bago --test ---"
& python "C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\bago_core\cli.py" --test 2>&1 | Out-String
