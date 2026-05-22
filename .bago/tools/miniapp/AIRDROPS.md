# Airdrops en BAGO

## Modelo de seguridad

**Línea roja** (no negociable):
- BAGO **nunca** tiene la mnemonic ni la clave privada del usuario.
- BAGO **nunca** firma transacciones por el usuario.

**Lo que sí hace BAGO:**
1. Detecta airdrops elegibles consultando el endpoint público de cada protocolo.
2. Construye la transacción de claim (destino, amount, payload) — formato TonConnect.
3. La pasa al cliente, que la entrega a `tonConnectUI.sendTransaction()`.
4. La wallet del usuario (Telegram Wallet, Tonkeeper, MyTonWallet…) muestra el modal de confirmación.
5. **El usuario aprueba o rechaza en su wallet.** BAGO no participa en la firma.

**Recibir TON / jettons / NFTs:** no requiere acción ni firma. La address pública recibe automáticamente. BAGO solo escanea `/api/airdrops` y refleja el balance.

## Tipos de airdrop

- **passive**: el protocolo envía a tu address. No hay claim, llega solo. BAGO solo lo reporta.
- **active**: tienes que llamar a un método `claim()` del contrato del protocolo gastando un poco de gas (~0.05 TON). BAGO construye la TX, tú firmas.

## Catálogo

Fichero: `.bago/state/airdrop_protocols.json`

```json
{
  "schema_version": 1,
  "protocols": [
    {
      "id": "ejemplo_protocol",
      "name": "Ejemplo Protocol",
      "type": "active",
      "claim_contract": "EQA...",
      "claim_amount_ton": 0.05,
      "claim_payload_b64": "te6ccgEBAQEAAgAAAA==",
      "claim_comment": "claim",
      "eligibility_url": "https://api.ejemplo.tg/eligibility?address={address}",
      "eligibility_field": "amount",
      "info_url": "https://ejemplo.tg"
    }
  ]
}
```

Campos:
- `id` (req): slug único del protocolo.
- `name` (req): nombre legible.
- `type` (req): `"passive"` o `"active"`.
- `eligibility_url` (req): URL que devuelve JSON con elegibilidad. Usa `{address}` como placeholder.
- `eligibility_field` (opt, default `"amount"`): campo del JSON con el monto reclamable. > 0 = elegible.
- `info_url` (opt): página oficial del proyecto, link de "info ↗" en la UI.
- Solo para `type=active`:
  - `claim_contract` (req): address del contrato a llamar.
  - `claim_amount_ton` (req): TON a enviar (gas + amount). Típico 0.05.
  - `claim_payload_b64` (opt): body BOC en base64. Si falta, se usa `claim_comment`.
  - `claim_comment` (opt): comentario del mensaje (para protocolos que aceptan claim por comentario).

## Estado actual

Catálogo vacío (0 protocolos). Cuando aparezca un airdrop real:

1. Identificar:
   - URL de eligibilidad pública del proyecto.
   - Address del contrato de claim.
   - Formato del payload (la mayoría de proyectos publican el snippet exacto).
2. Editar `.bago/state/airdrop_protocols.json` añadiendo entrada al array.
3. Push.
4. La miniapp lo detecta automáticamente al refrescar.

## Endpoints

| Método | Ruta | Devuelve |
|---|---|---|
| `GET`  | `/api/airdrop/claimable` | `{ok, address, claimable: [...], protocols_known}` |
| `POST` | `/api/airdrop/claim` `{protocol_id}` | `{ok, transaction, protocol}` para TonConnect |

## UI

En panel **Cartera**:
- Si hay airdrops reclamables, aparece card "💰 Airdrops reclamables (N)".
- Para cada uno: nombre + amount + botón.
- `passive`: badge "esperando entrega" (BAGO no actúa).
- `active`: botón "💰 Reclamar" → modal confirm → TonConnect → wallet del usuario firma.
- **Si no hay reclamables, no se muestra nada.** Cero datos ficticios.

## Pendiente

- **Verificación on-chain post-claim**: detectar tx confirmada y notificar al usuario. Hoy: el usuario espera 12s y refresca manualmente.
- **Catálogo curado**: mantener `airdrop_protocols.json` actualizado con protocolos reales activos.
- **Aprendizaje**: cuando se detecta jetton no catalogado en la wallet, ofrecer "investigar" → si tiene página oficial con claim instructions, añadir entrada al catálogo.
