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

- `tonconnect-manifest.json` debe servirse en HTTPS. En `localhost` el SDK falla. Por eso la dependencia de ngrok (ya integrado en `launch_miniapp.sh`).
- `set_ton_address()` escribe a `notify_config.json`. Si el bot está corriendo, lee fresh cada `/airdrop`. No hay invalidación de caché entre miniapp y bot — están sincronizados a través del fichero.
