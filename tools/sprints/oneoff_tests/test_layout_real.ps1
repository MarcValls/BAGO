$content = Get-Content 'C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\chat\boot_with_input.txt' -Encoding UTF8 -Raw
# Strip ANSI escape codes for readability
$content = [regex]::Replace($content, '\x1b\[[0-9;]*[a-zA-Z]', '')
$content = [regex]::Replace($content, '\x1b\[[0-9]*[a-zA-Z]', '')
$content = [regex]::Replace($content, '\x1b\[[\?]?[0-9;]*[a-zA-Z]', '')
$i = 0
foreach ($line in ($content -split "`n")) {
    $i++
    Write-Host ("{0,3} | {1}" -f $i, $line)
}
