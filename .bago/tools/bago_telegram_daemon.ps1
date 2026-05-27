$token = $env:BAGO_TELEGRAM_TOKEN
if (-not $token) {
    Write-Error "FATAL: BAGO_TELEGRAM_TOKEN no definido"
    exit 1
}
$api = "https://api.telegram.org/bot$token"
$bagoDir = "$env:USERPROFILE\BAGO"
$logFile = "$env:USERPROFILE\.bago\state\logs\telegram_ps_daemon.log"
New-Item -ItemType Directory -Path (Split-Path $logFile) -Force | Out-Null

function Write-Log($msg) {
    $line = "[{0:HH:mm:ss}] {1}" -f (Get-Date), $msg
    Add-Content $logFile $line -Encoding UTF8
    Write-Host $line
}

Write-Log "START"

$offset = 0
while ($true) {
    try {
        $r = Invoke-WebRequest -Uri "$api/getUpdates?offset=$offset&limit=5" -UseBasicParsing -TimeoutSec 30
        $data = $r.Content | ConvertFrom-Json
        if (-not $data.ok) {
            Write-Log "API_ERR"
            Start-Sleep -Seconds 5
            continue
        }
        foreach ($u in $data.result) {
            $offset = [math]::Max($offset, $u.update_id + 1)
            $msg = $u.message
            if (-not $msg) { continue }
            $text = $msg.text.Trim()
            $chat = $msg.chat.id
            $user = $msg.from.first_name
            Write-Log "MSG $user : $text"
            
            # Ejecutar BAGO
            $ps1 = "$bagoDir\bago.ps1"
            try {
                $result = powershell -ExecutionPolicy Bypass -File $ps1 $text 2>&1
                $reply = ($result | Out-String).Trim()
                if ($reply.Length -gt 3500) { $reply = $reply.Substring(0, 3500) }
            } catch {
                $reply = "Error: $_"
            }
            
            # Responder
            try {
                $body = @{chat_id=$chat; text=$reply} | ConvertTo-Json
                Invoke-WebRequest -Uri "$api/sendMessage" -Method POST -Body $body -ContentType "application/json" -TimeoutSec 30 | Out-Null
                Write-Log "REPLIED"
            } catch {
                Write-Log "SEND_ERR: $_"
            }
        }
        Start-Sleep -Seconds 2
    } catch {
        Write-Log "ERR: $_"
        Start-Sleep -Seconds 5
    }
}
