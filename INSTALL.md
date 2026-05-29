# BAGO - Instalacion rapida

Version: 3.5.0b1

## Windows

```powershell
git clone https://github.com/MarcValls/BAGO.git
cd BAGO
.\install-bago.cmd
```

Ruta por defecto: `C:\Program Files\BAGO`.

Ruta personalizada:

```powershell
.\install-bago.cmd -TargetRoot C:\BAGO
```

Al terminar, abre una terminal nueva si `bago` no se reconoce.

## macOS / Linux

```bash
git clone https://github.com/MarcValls/BAGO.git
cd BAGO
./install-bago.sh
```

Ruta por defecto: `~/.local/share/bago`.

Ruta personalizada:

```bash
BAGO_TARGET_ROOT="$HOME/apps/bago" ./install-bago.sh
```

Si `bago` no aparece, abre una terminal nueva o añade `~/.local/bin` al `PATH`.

## Primer arranque

```bash
bago
```

BAGO comprueba:

- si hay un dispositivo BAGO conectado;
- si hay un pendrive disponible para convertirlo en dispositivo BAGO;
- donde guardar credenciales;
- si debe usar credenciales solo de sesion.

Orden recomendado:

1. Dispositivo BAGO en pendrive.
2. Directorio local de credenciales, solo si no usas pendrive.
3. Credenciales de sesion, sin persistencia.

Las credenciales no deben estar en el repo. El `.gitignore` excluye `credentials.json`, `accounts.json`, `.bago/user/` y `bago-knowledge/`.

## Validar

```bash
bago validate
bago portable detect
bago launch
```

## Knowledge

BAGO crea y usa `bago-knowledge` como memoria de aprendizaje. Recomendado:

- repo 1: tu framework/proyecto BAGO;
- repo 2: `bago-knowledge`, privado o publico segun lo que quieras compartir;
- compartir solo subcarpetas curadas de conocimiento con la comunidad BAGO.

Documentacion relacionada:

- [Manual de usuario](docs/USER_MANUAL.md)
- [Desarrolladores](docs/DEVELOPERS.md)
- [Sponsors](docs/SPONSORS.md)
- [Instalacion profunda](docs/INSTALL_DEEP.md)
