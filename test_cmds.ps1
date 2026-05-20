$cmds = Get-Content cmd_list.txt
$results = @()
foreach ($cmd in $cmds) {
    $arg = '--help'
    $pinfo = New-Object System.Diagnostics.ProcessStartInfo
    $pinfo.FileName = 'C:\Python314\python.exe'
    $pinfo.Arguments = "bago $cmd $arg"
    $pinfo.RedirectStandardOutput = $true
    $pinfo.RedirectStandardError = $true
    $pinfo.UseShellExecute = $false
    $p = New-Object System.Diagnostics.Process
    $p.StartInfo = $pinfo
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $p.Start() | Out-Null
        if ($p.WaitForExit(6000)) {
            $ec = $p.ExitCode
        } else {
            $p.Kill()
            $ec = -1
        }
    } catch {
        $ec = -2
    }
    $sw.Stop()
    $results += [PSCustomObject]@{cmd=$cmd; code=$ec; ms=$sw.ElapsedMilliseconds}
    Write-Host "$cmd -> $ec ($($sw.ElapsedMilliseconds)ms)"
}
$results | Export-Csv results.csv -NoTypeInformation
Write-Host "DONE"
