# BAGO para desarrolladores

## Setup

```bash
git clone https://github.com/MarcValls/BAGO.git
cd BAGO
python -m pip install -e .
bago validate
```

En Windows tambien puedes usar:

```powershell
.\install-bago.cmd -TargetRoot C:\BAGO
```

## Reglas de estado

- El framework vive en el repo.
- El estado mutable vive fuera del repo o en `.bago/state/` segun contrato.
- Las credenciales viven en el dispositivo BAGO, en un directorio local aprobado o solo en sesion.
- `credentials.json`, `accounts.json`, `.bago/user/` y `bago-knowledge/` no se versionan.

## Validacion antes de PR

```bash
bago validate
bago smoke
python -m py_compile bago_core\launcher.py
```

## Knowledge

Mantén `bago-knowledge` como repo separado. Si compartes conocimiento, publica subcarpetas curadas y sin secretos.
