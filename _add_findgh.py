text = open("bago.ps1","r",encoding="utf-8").read()

find_gh = """function Find-Gh {
    $gh = Get-Command gh -ErrorAction SilentlyContinue
    if ($gh) { return $gh.Source }
    $known = @(
        (Join-Path $env:LOCALAPPDATA "Programs\GitHub CLI\gh.exe"),
        "C:\\Program Files\\GitHub CLI\\gh.exe"
    )
    foreach ($p in $known) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

"""

marker = "function Invoke-BagoPipeline {"
if marker in text and "function Find-Gh" not in text:
    text = text.replace(marker, find_gh + marker)
    print("[OK] Find-Gh agregado")
else:
    print("[SKIP]")

open("bago.ps1","w",encoding="utf-8").write(text)
print("Done")
