$content = Get-Content 'C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\chat\boot_with_input.txt' -Encoding UTF8
$i = 0
foreach ($line in $content) {
    $i++
    Write-Host ("{0,3} | {1}" -f $i, $line)
}
