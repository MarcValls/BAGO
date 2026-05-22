# TonConnect en BAGO Miniapp

Conexión de wallet TON sin pegar address manual. Estilo mini-apps de trading de Telegram.

## Cómo funciona

1. Usuario abre BAGO Miniapp dentro de Telegram (botón "BAGO Dashboard" del bot).
2. Tab **Cartera** → botón **🔗 Conectar TON**.
3. TonConnect abre modal con wallets disponibles (Tonkeeper, MyTonWallet, etc.).
4. Usuario aprueba en su wallet → BAGO recibe la address automáticamente.
5. La address se guarda en `notify_config.json` (mismo destino que `/airdrop set`).
6. Reescaneo de airdrops automático.

## Endpoints añadidos al server

| Método | Ruta | Cuerpo | Acción |
|---|---|---|---|
| `GET`  | `/tonconnect-manifest.json` | — | Manifest con URL dinámica (Host header → ngrok) |
| `GET`  | `/api/wallet/status`        | — | `{ok, address, connected}` |
| `POST` | `/api/wallet/connect`       | `{address, ton_proof?}` | `set_ton_address(address)` |
| `POST` | `/api/wallet/disconnect`    | — | Borra `wallet.ton_address` |

## Pasos manuales pendientes

1. **Verificación `ton_proof`** (opcional). Implementación actual acepta cualquier address que el SDK reporte. Para airdrop scanning (read-only) **no es crítico** — leer balance público de cualquier address no daña a nadie. Si se quiere prueba criptográfica de control:
   - Implementar `verify_ton_proof()` en backend.
   - Aceptar `connect` solo si la firma valida contra `address` + `domain` + `payload` + `timestamp`.
   - Spec: https://docs.ton.org/develop/dapps/ton-connect/sign

2. **Editar manifest** (`.bago/tools/miniapp/tonconnect-manifest.json`):
   - `name`, `termsOfUseUrl`, `privacyPolicyUrl` ya están con BAGO.
   - El campo `url` se sobreescribe dinámicamente desde el `Host` header (cubre ngrok).

3. **Lanzar miniapp con HTTPS público**:
   ```bash
   bash .bago/tools/launch_miniapp.sh
   ```
   Esto arranca `bago_miniapp_server.py` + ngrok y registra la URL pública en el bot.

## Limitación conocida

- **ngrok-free interpone una página de warning** (ERR_NGROK_6024) para User-Agents de navegador, lo que rompe el fetch del manifest si lo servimos desde ngrok. **Solución actual:** servir el manifest desde **GitHub raw** (`https://raw.githubusercontent.com/MarcValls/BAGO/main/.bago/tools/miniapp/tonconnect-manifest.json`). HTTPS estable, sin warning, sin auth.
- **Trade-off:** cuando ngrok asigne URL nueva (al reiniciar `launch_miniapp.sh`), hay que **actualizar el campo `url` del manifest del repo y push**. El campo `url` se usa como identidad de la dApp en TonConnect (algunas wallets lo muestran al usuario). No coincidir con el dominio donde corre la app no rompe la conexión, pero es buena higiene mantenerlo sincronizado.
- **Solución estable a medio plazo:** migrar de ngrok-free a `cloudflared tunnel` (URL custom estable gratis) o ngrok plan pago (custom domain).
- `set_ton_address()` escribe a `notify_config.json`. Si el bot está corriendo, lee fresh cada `/airdrop`. No hay invalidación de caché entre miniapp y bot — están sincronizados a través del fichero.
