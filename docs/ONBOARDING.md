# Onboarding BAGO

## Escenario de usuario nuevo

1. Encuentra BAGO en GitHub.
2. Lee que es, que puede hacer y como instalarlo.
3. Instala con el comando de su sistema operativo.
4. Abre una terminal nueva si el comando `bago` aun no esta en `PATH`.
5. Ejecuta `bago`.
6. BAGO detecta dispositivo BAGO, pendrive o modo sin pendrive.
7. BAGO define donde viven credenciales y conocimiento.
8. El usuario entra al chat o al menu.

## Politica sin pendrive

Si no hay dispositivo BAGO:

- BAGO recomienda crear uno.
- Como alternativa menos recomendada, ofrece un directorio local de credenciales.
- Si el usuario no acepta almacenamiento local, las credenciales son solo de sesion.

## Politica de repos

Recomendado:

- repo del framework o proyecto del usuario;
- repo separado `bago-knowledge`;
- subcarpetas curadas para compartir en comunidad.

Nunca sincronizar credenciales visibles a GitHub.
