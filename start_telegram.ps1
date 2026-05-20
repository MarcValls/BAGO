# start_telegram.ps1 — Inicia el bot de Telegram de BAGO
# Usa la API BAGO en puerto 11435

$token = "8519892399:AAHTKzfu_VyLUSpJ-iNjmSn9RcgFOsddeKA"
$env:TELEGRAM_BOT_TOKEN = $token
$env:BAGO_API_URL = "http://127.0.0.1:11435"
$env:PYTHONPATH = "C:\Users\AMTEC_Terminal_1º\BAGO\.bago\tools"

Write-Host "🤖 Iniciando bot de Telegram..." -ForegroundColor Green
Write-Host "   Token: $token" -ForegroundColor Gray
Write-Host "   API BAGO: $($env:BAGO_API_URL)" -ForegroundColor Gray
Write-Host "   PYTHONPATH: $($env:PYTHONPATH)" -ForegroundColor Gray
Write-Host ""
Write-Host "Comandos disponibles:" -ForegroundColor Yellow
Write-Host "   /start   - Presentación" -ForegroundColor White
Write-Host "   /status  - Estado de providers" -ForegroundColor White
Write-Host "   /model   - Cambiar modelo" -ForegroundColor White
Write-Host "   /help    - Ayuda" -ForegroundColor White
Write-Host "   (texto)  - Chat con BAGO" -ForegroundColor White
Write-Host ""

python -m bago.api.services.telegram_bot
