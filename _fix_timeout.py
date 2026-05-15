text = open("bago.ps1","r",encoding="utf-8").read()

start = text.find("function Invoke-BagoPipeline {")
end = text.find("function Show-Status {")
block = text[start:end]

# Reemplazar WaitForExit() por WaitForExit(20000)
block = block.replace("$proc.WaitForExit()", "$proc.WaitForExit(20000)\n            if (-not $proc.HasExited) { $proc.Kill(); $out += \"`n[Timeout: proceso terminado]\" }")

text = text[:start] + block + text[end:]

open("bago.ps1","w",encoding="utf-8").write(text)
print("OK")
