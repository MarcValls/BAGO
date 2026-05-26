# BAGO Siembras

Una siembra es la huella minima de BAGO dentro de un proyecto externo. El PADRE conserva el framework completo; la SIEMBRA conserva solo el estado y las herramientas necesarias para trabajar en ese proyecto.

## Modelo

- PADRE: instalacion principal de BAGO, con comandos de framework, validacion, health, registry, releases y mantenimiento.
- SIEMBRA: carpeta `.bago/` local del proyecto, con `pack.json`, `state/`, `bago.db` y herramientas de scope `project` o `both`.
- Launcher local: script `bago` en el proyecto sembrado. Ejecuta comandos locales cuando son del proyecto y delega al PADRE los comandos de framework.

## Comandos

```powershell
python bago_core/launcher.py siembra create C:\ruta\proyecto
python bago_core/launcher.py siembra list
python bago_core/launcher.py siembra status
python bago_core/launcher.py siembra diff C:\ruta\proyecto
python bago_core/launcher.py siembra update C:\ruta\proyecto
python bago_core/launcher.py siembra sync
```

## Flujo recomendado

1. Crear la siembra desde el PADRE.
2. Entrar al repo externo.
3. Ejecutar `python bago start` o `python bago ideas` desde el proyecto.
4. Usar `BAGO_PADRE_PATH` si el proyecto se mueve o si `pack.json` apunta a otro PADRE.
5. Actualizar la siembra despues de releases del framework.

## Limites

- La siembra no copia herramientas de mantenimiento del framework.
- El estado del proyecto vive en su `.bago/state/`, no en el estado global del PADRE.
- Los comandos de framework requieren que el PADRE exista y sea accesible.
