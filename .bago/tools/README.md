# tools

Esta carpeta contiene utilidades ligeras para verificar que el pack no se rompe en sus puntos más sensibles.

## Herramientas incluidas

- `validate_manifest.py`:
  comprueba que las rutas declaradas en `pack.json` existen,
  que no escapan fuera del pack
  y que la declaración de `workflow_bootstrap_repo_first`
  está alineada con el manifiesto.
- `validate_state.py`:
  comprueba presencia y coherencia del estado estructurado,
  workflows declarados, sesión activa o cerrada,
  inventario, referencias cruzadas
  y forma estructural de sesiones, cambios y evidencias.
- `validate_pack.py`:
  ejecuta una verificación compuesta,
  compara `TREE.txt` con el árbol real,
  verifica `CHECKSUMS.sha256`,
  detecta referencias operativas heredadas a `2.1.x`
  fuera de migración
  y comprueba que la carpeta física de cada rol
  coincide con su `family`.
- `personality_panel.py`:
  panel de configuración para personalizar estilo de personalidad,
  idioma principal y vocabulario contextual del usuario
  (incluyendo términos de círculo pequeño con significado y ejemplo).
  Soporta flujo guiado con `--flow-vocab`, usado desde `./personality-flow`.
- `repo_context_guard.py`:
  detecta si `.bago/` está operando sobre un repo distinto al contexto anterior.
  Si hay `new` o `mismatch`, obliga a arrancar por `W1/repo-first`
  para evitar bucles de estado heredado.
- `bago_learning_audit.py`:
  audita la trazabilidad de aprendizaje por proyecto en `state/`
  (ideas por proyecto, sesiones con/si campo de proyecto,
  calidad del `knowledge_index` y warnings de indexación).

## Filosofía

Estas utilidades no sustituyen una auditoría humana completa,
pero sí evitan errores materiales repetitivos
y varias incoherencias canónicas de segundo nivel.

## Nota sobre checksums

`CHECKSUMS.sha256` cubre todos los archivos del pack
salvo el propio `CHECKSUMS.sha256`.
Esta exclusión es deliberada
para evitar la paradoja de autorreferencia.

## Nota específica de V2.2

Los validadores siguen centrados
en integridad canónica y coherencia del pack.
La capa repo-first y la fábrica de prompts
no cambian esa base; la hacen más usable.
Esta versión no valida semánticamente
un repositorio externo concreto:
valida que `.bago/` no se contradiga
mientras opera sobre él.

## Nota específica de V2.2.1

En esta release, los validadores además comprueban:

- coherencia entre `pack.json.version` y `state/global_state.json`,
- existencia del workflow repo-first y su declaración en el manifiesto,
- existencia de la sesión, cambio y evidencia de consolidación,
- ausencia de referencias operativas a `2.1.x` fuera de legado/migración,
- alineación entre `family` declarada en cada rol y su carpeta física bajo `roles/`.

## Herramientas de instalación (externas al pack)

Estas herramientas viven en el directorio padre de `.bago/`
y no forman parte del pack canónico, por lo que no están cubiertas
por `CHECKSUMS.sha256` ni por `TREE.txt`.
Se registran en `pack.json` bajo la clave `"installer"` a título informativo.

- `bago-make-installer.sh`:
  genera `BAGO_installer.sh` (macOS/Linux autocontenido)
  y `BAGO_installer_windows.zip` (paquete Windows).
  Ejecutar cada vez que se quiera redistribuir el pack.
- `bago-install.sh` / `bago-install.bat`:
  copia `.bago/` en un repositorio destino y valida la instalación.
  Disponible globalmente tras ejecutar el setup.
- `bago-setup.sh` / `bago-setup.bat`:
  registra el alias/comando `bago-install` de forma permanente en el PC.
  Ejecutar una sola vez por máquina.
- `BAGO_installer.sh`:
  instalador autocontenido para macOS/Linux.
  Único archivo a distribuir en entornos Unix.
- `BAGO_installer_windows.zip`:
  paquete para Windows. Extraer y ejecutar `install.bat`.
