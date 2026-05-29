# Manual de usuario BAGO

## Inicio

```bash
bago
```

El primer arranque detecta dispositivo BAGO, credenciales, modelos disponibles y matriz de routing.

## Credenciales

Orden recomendado:

1. Dispositivo BAGO: credenciales y estado privado viven en el pendrive.
2. Directorio local: alternativa menos recomendada si no usas pendrive.
3. Sesion: no guarda credenciales; tendras que logearte otra vez.

Comandos utiles:

```bash
bago portable detect
bago portable create E:
bago launch
```

Dentro del chat:

```text
/auth status
/login
/models
/routing
/status
```

## Knowledge

`bago-knowledge` es la memoria aprendida. Mantenla separada del framework.

Recomendado:

- un repo para tu framework/proyecto;
- otro repo para `bago-knowledge`;
- publicar solo subcarpetas curadas si quieres compartir conocimiento con la comunidad.

No guardes secretos en `bago-knowledge`.
