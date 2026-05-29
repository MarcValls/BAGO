# Security

## Credenciales

BAGO no debe guardar credenciales en el repositorio.

Orden recomendado:

1. Dispositivo BAGO.
2. Directorio local aprobado.
3. Credenciales solo de sesion.

Archivos bloqueados por `.gitignore`:

- `credentials.json`
- `accounts.json`
- `token_log.json`
- `.bago/user/`
- `bago-knowledge/`

## Reportar problemas

No abras issues publicos con tokens, logs privados o credenciales. Revoca cualquier credencial expuesta antes de compartir evidencias.
